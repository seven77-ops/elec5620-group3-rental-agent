import asyncio
import json
from datetime import datetime, timedelta, timezone
import unittest

import httpx

KEY = 'private-data-key'


def trip_request():
    return {'origin': {'latitude': -33.89, 'longitude': 151.18},
            'destination': {'latitude': -33.889, 'longitude': 151.19},
            'arrival_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            'allow_external': True}


def journey():
    return {'journeys': [{'interchanges': 0, 'legs': [
        {'duration': 300, 'origin': {'departureTimePlanned': '2026-10-22T21:00:00Z'},
         'destination': {'arrivalTimePlanned': '2026-10-22T21:05:00Z'},
         'transportation': {'product': {'class': 100, 'name': 'Footpath'}}},
        {'duration': 600, 'origin': {'departureTimePlanned': '2026-10-22T21:10:00Z'},
         'destination': {'arrivalTimePlanned': '2026-10-22T21:20:00Z'},
         'transportation': {'name': 'Bus 413', 'product': {'class': 5, 'name': 'Bus'}}}
    ]}]}


class RealProviderTests(unittest.TestCase):
    def provider(self, responder=None, **env):
        from server.app.real_data.providers import DataProviders
        return DataProviders(env=env, transport=httpx.MockTransport(responder) if responder else None)

    def test_missing_configuration_permission_and_consent_make_no_call(self):
        from server.app.common import ApiError
        calls = []
        p = self.provider(lambda r: calls.append(r), DOMAIN_API_KEY=KEY, TFNSW_API_KEY=KEY)
        self.assertFalse(p.public_config()['domain']['configured'])
        self.assertTrue(p.public_config()['tfnsw']['configured'])
        for run in (lambda: p.search({'postcode': '2050', 'maximum_weekly_rent': 900, 'allow_external': True}),
                    lambda: p.trips(dict(trip_request(), allow_external=False)),
                    lambda: self.provider().trips(trip_request())):
            with self.assertRaises(ApiError): run()
        self.assertEqual(calls, [])
        self.assertNotIn(KEY, str(p.public_config()))

    def test_domain_fixed_endpoint_filters_auth_and_minimal_public_fields(self):
        sent = []
        def respond(request):
            sent.append(request)
            return httpx.Response(200, json=[{'type': 'PropertyListing', 'listing': {
                'id': 18374975, 'listingType': 'Rent', 'listingSlug': 'sample-18374975',
                'priceDetails': {'displayPrice': '$760 per week'},
                'propertyDetails': {'displayableAddress': '1/20 Pyrmont Bridge Road', 'bedrooms': 1,
                    'postcode': '2050', 'latitude': -33.89, 'longitude': 151.18},
                'advertiser': {'secret_contact': 'not-exported'}}}])
        p = self.provider(respond, DOMAIN_API_KEY=KEY, DOMAIN_USE_APPROVED='1')
        result = p.search({'postcode': '2050', 'maximum_weekly_rent': 900, 'allow_external': True})
        request = sent[0]
        self.assertEqual(str(request.url), 'https://api.domain.com.au/v1/listings/residential/_search')
        self.assertEqual(request.headers['X-Api-Key'], KEY)
        body = json.loads(request.content)
        self.assertEqual((body['listingType'], body['pageSize'], body['maxPrice']), ('Rent', 20, 900))
        self.assertEqual(body['locations'][0]['postCode'], '2050')
        self.assertEqual(result['items'][0]['advertised_price'], '$760 per week')
        self.assertEqual(result['items'][0]['evaluation_status'], 'not_evaluated')
        self.assertNotIn('not-exported', str(result))
        self.assertNotIn(KEY, str(result))

    def test_domain_rejects_nonrental_or_malformed_response(self):
        from server.app.common import ApiError
        for data in ({}, [{'type': 'PropertyListing', 'listing': {'listingType': 'Sale'}}], [None]):
            with self.subTest(data=data), self.assertRaises(ApiError):
                self.provider(lambda r: httpx.Response(200, json=data), DOMAIN_API_KEY=KEY, DOMAIN_USE_APPROVED='true').search(
                    {'postcode': '2050', 'maximum_weekly_rent': 900, 'allow_external': True})

    def test_tfnsw_arrival_coordinates_and_waiting_are_preserved(self):
        sent = []
        def respond(request):
            sent.append(request)
            return httpx.Response(200, json=journey())
        body = trip_request()
        p = self.provider(respond, TFNSW_API_KEY=KEY)
        result = p.trips(body)
        request = sent[0]
        self.assertEqual(request.url.host, 'api.transport.nsw.gov.au')
        self.assertEqual(request.headers['Authorization'], 'apikey ' + KEY)
        self.assertEqual(request.url.params['depArrMacro'], 'arr')
        self.assertEqual(request.url.params['name_origin'], '151.18,-33.89:EPSG:4326')
        self.assertEqual(result['query'], body)
        route = result['journeys'][0]
        self.assertEqual(route['duration_minutes'], 20)
        self.assertEqual(route['leg_travel_minutes'], 15)
        self.assertEqual(route['walking_minutes'], 5)
        self.assertEqual(route['transfers'], 0)

    def test_empty_missing_timing_and_malformed_routes(self):
        from server.app.common import ApiError
        p = self.provider(lambda r: httpx.Response(200, json={'journeys': []}), TFNSW_API_KEY=KEY)
        self.assertEqual(p.trips(trip_request())['journeys'], [])
        data = journey()
        del data['journeys'][0]['legs'][0]['origin']['departureTimePlanned']
        result = self.provider(lambda r: httpx.Response(200, json=data), TFNSW_API_KEY=KEY).trips(trip_request())
        self.assertIsNone(result['journeys'][0]['duration_minutes'])
        for data in ({'error': 'secret'}, {'journeys': [None]}, {'journeys': [{'legs': []}]}):
            with self.subTest(data=data), self.assertRaises(ApiError):
                self.provider(lambda r: httpx.Response(200, json=data), TFNSW_API_KEY=KEY).trips(trip_request())

    def test_invalid_inputs_fail_before_network(self):
        from server.app.common import ApiError
        calls = []
        p = self.provider(lambda r: calls.append(r), TFNSW_API_KEY=KEY)
        for changes in ({'origin': {'latitude': True, 'longitude': 151}},
                        {'destination': {'latitude': -91, 'longitude': 151}},
                        {'arrival_at': '2020-01-01T09:00:00+11:00'},
                        {'arrival_at': '2026-10-22T09:00:00'}, {'url': 'http://localhost/private'}):
            with self.subTest(changes=changes), self.assertRaises(ApiError):
                p.trips(dict(trip_request(), **changes))
        self.assertEqual(calls, [])

    def test_transport_errors_are_bounded_and_redacted(self):
        from server.app.common import ApiError
        for response in (httpx.Response(401, text=KEY), httpx.Response(302, headers={'location': 'http://localhost/'}),
                         httpx.Response(200, content=b'x' * 1_000_001),
                         httpx.Response(200, content=b'{"journeys":[],"journeys":[]}')):
            with self.subTest(status=response.status_code), self.assertRaises(ApiError) as caught:
                self.provider(lambda r: response, TFNSW_API_KEY=KEY).trips(trip_request())
            self.assertNotIn(KEY, caught.exception.message)

    def test_total_deadline_covers_slow_body(self):
        from server.app.real_data.providers import DataProviders
        from server.app.common import ApiError
        class Slow(httpx.AsyncByteStream):
            async def __aiter__(self):
                for _ in range(10):
                    await asyncio.sleep(.3)
                    yield b' '
        p = DataProviders(env={'TFNSW_API_KEY': KEY}, transport=httpx.MockTransport(
            lambda r: httpx.Response(200, stream=Slow())))
        p.timeout = .1
        with self.assertRaises(ApiError) as caught:
            p.trips(trip_request())
        self.assertEqual(caught.exception.code, 'data_timeout')

    def test_unknown_walking_class_is_not_reported_as_zero(self):
        data = journey()
        del data['journeys'][0]['legs'][0]['transportation']['product']['class']
        result = self.provider(lambda r: httpx.Response(200, json=data), TFNSW_API_KEY=KEY).trips(trip_request())
        self.assertIsNone(result['journeys'][0]['walking_minutes'])

    def test_huge_integer_provider_response_remains_redacted(self):
        from server.app.common import ApiError
        data = journey()
        data['journeys'][0]['legs'][0]['duration'] = 10 ** 400
        with self.assertRaises(ApiError) as caught:
            self.provider(lambda r: httpx.Response(200, json=data), TFNSW_API_KEY=KEY).trips(trip_request())
        self.assertEqual(caught.exception.code, 'data_invalid_response')
