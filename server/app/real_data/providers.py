"""Official, fixed-host data requests with bounded transport and redacted errors."""
import asyncio
from datetime import datetime, timedelta, timezone
import os
import re
from zoneinfo import ZoneInfo
import httpx
from ..ai.provider import run_transport, strict_json
from ..common import ApiError, now, require, shape
from .intake import coordinates, instant
from .market import numeric

DOMAIN_DOC = 'https://developer.domain.com.au/docs/latest/apis/pkg_agents_listings/'
TFNSW_DOC = 'https://opendata.transport.nsw.gov.au/dataset/trip-planner-apis'


class DataProviders:
    def __init__(self, env=None, transport=None):
        env = os.environ if env is None else env
        self.domain_key = env.get('DOMAIN_API_KEY', '').strip()
        self.domain_approved = env.get('DOMAIN_USE_APPROVED', '').lower() in ('1', 'true')
        self.tfnsw_key = env.get('TFNSW_API_KEY', '').strip()
        self.transport, self.timeout = transport, 12

    def public_config(self):
        return {'domain': {'configured': bool(self.domain_key and self.domain_approved),
                           'key_present': bool(self.domain_key), 'use_approved': self.domain_approved,
                           'documentation': DOMAIN_DOC},
                'tfnsw': {'configured': bool(self.tfnsw_key), 'documentation': TFNSW_DOC}}

    def request(self, method, url, headers, **kwargs):
        response_limit=kwargs.pop('response_limit',1_000_000)
        async def fetch():
            async with asyncio.timeout(self.timeout):
                async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout,
                                            follow_redirects=False, trust_env=False) as client:
                    async with client.stream(method, url, headers=headers, **kwargs) as response:
                        require(response.status_code == 200, 502, 'data_provider_error',
                                'The data service request failed. Check permissions, quota or service status.')
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            require(len(content) + len(chunk) <= response_limit, 502, 'data_response_too_large', 'The data response exceeds the size limit.')
                            content.extend(chunk)
                        return strict_json(bytes(content).decode('utf-8'))
        try:
            return run_transport(fetch(), self.timeout)
        except ApiError:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise ApiError(504, 'data_timeout', 'The data query timed out and was not automatically retried.') from None
        except httpx.HTTPError:
            raise ApiError(502, 'data_connection_error', 'The data service is temporarily unreachable.') from None
        except (ValueError, TypeError, UnicodeError):
            raise ApiError(502, 'data_invalid_response', 'The data service response format could not be validated.') from None

    def gate(self, provider, allow_external):
        require(allow_external is True, 422, 'external_query_required', 'Confirm sending this query to the data service first.')
        require(self.public_config()[provider]['configured'], 503, 'data_not_configured',
                'This data endpoint or its permitted purpose is not configured. Follow the setup instructions and restart.')

    def search(self, body: dict):
        shape(body, ('postcode', 'maximum_weekly_rent', 'allow_external'))
        require(body['postcode'] in ('2008', '2037', '2042', '2050'), 422, 'invalid_input', 'Search is limited to the listed postcodes near USYD.')
        require(numeric(body['maximum_weekly_rent'], 1, 100_000), 422, 'invalid_input', 'Maximum weekly rent must be a valid positive amount.')
        self.gate('domain', body['allow_external'])
        data = self.request('POST', 'https://api.domain.com.au/v1/listings/residential/_search',
                            {'X-Api-Key': self.domain_key, 'Accept': 'application/json'}, json={
                                'listingType': 'Rent', 'pageSize': 20, 'pageNumber': 1,
                                'maxPrice': body['maximum_weekly_rent'],
                                'locations': [{'state': 'NSW', 'postCode': body['postcode'], 'includeSurroundingSuburbs': False}]})
        try:
            if not isinstance(data, list) or len(data) > 20:
                raise ValueError()
            items = []
            for wrapper in data:
                if not isinstance(wrapper, dict) or wrapper.get('type') != 'PropertyListing':
                    raise ValueError()
                row = wrapper['listing']
                if row.get('listingType') != 'Rent' or type(row['id']) is not int or row['id'] <= 0:
                    raise ValueError()
                prop, price = row['propertyDetails'], row.get('priceDetails', {})
                if not isinstance(prop, dict) or not isinstance(price, dict):
                    raise ValueError()
                def text(value):
                    if value is not None and (not isinstance(value, str) or len(value) > 1500):
                        raise ValueError()
                    return value
                slug = row.get('listingSlug')
                url = 'https://www.domain.com.au/' + slug if isinstance(slug, str) and re.fullmatch(r'[a-zA-Z0-9-]{1,250}', slug) else None
                lat, lon = prop.get('latitude'), prop.get('longitude')
                if not (numeric(lat, -90, 90) and numeric(lon, -180, 180)):
                    lat = lon = None
                beds = prop.get('bedrooms')
                items.append({'listing_id': str(row['id']), 'source_url': url,
                              'address': text(prop.get('displayableAddress')), 'advertised_price': text(price.get('displayPrice')),
                              'bedrooms': beds if numeric(beds, 0, 20) else None, 'latitude': lat, 'longitude': lon,
                              'evaluation_status': 'not_evaluated'})
            return {'provider': 'domain', 'queried_at': now(), 'query': body, 'items': items,
                    'limitations': ['Advertisements are unverified listings. Bills, move-in window, term and evidence have not been checked.', 'Queries only the first 20 results; no automatic pagination, advertisement saving or model call.']}
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ApiError(502, 'data_invalid_response', 'The listing response failed schema validation.') from None

    def trips(self, body: dict):
        shape(body, ('origin', 'destination', 'arrival_at', 'allow_external'))
        origin, destination = coordinates(body['origin']), coordinates(body['destination'])
        arrival = instant(body['arrival_at'])
        require(datetime.now(timezone.utc) < arrival <= datetime.now(timezone.utc) + timedelta(days=30),
                422, 'invalid_input', 'Choose an arrival time within the next 30 days. The provider timetable window may be shorter.')
        self.gate('tfnsw', body['allow_external'])
        local = arrival.astimezone(ZoneInfo('Australia/Sydney'))
        coord = lambda p: f"{p['longitude']:.7f}:{p['latitude']:.7f}:EPSG:4326"
        data = self.request('GET', 'https://api.transport.nsw.gov.au/v1/tp/trip',
                            {'Authorization': 'apikey ' + self.tfnsw_key, 'Accept': 'application/json'}, response_limit=8_000_000,params={
                                'outputFormat': 'rapidJSON', 'coordOutputFormat': 'EPSG:4326', 'depArrMacro': 'arr',
                                'itdDate': local.strftime('%Y%m%d'), 'itdTime': local.strftime('%H%M'),
                                'type_origin': 'coord', 'name_origin': coord(origin),
                                'type_destination': 'coord', 'name_destination': coord(destination),
                                'calcNumberOfTrips': 3, 'TfNSWTR': 'true'})
        try:
            if not isinstance(data, dict) or not isinstance(data.get('journeys'), list) or len(data['journeys']) > 30:
                raise ValueError()
            journeys = []
            for route in data['journeys'][:3]:
                legs = route['legs']
                if not isinstance(legs, list) or not 0 < len(legs) <= 100:
                    raise ValueError()
                duration, walking, names = 0, 0, []
                transit_modes=[]
                summary_legs=[]
                walking_known = True
                for leg in legs:
                    seconds = leg['duration']
                    if not numeric(seconds, 0, 604800):
                        raise ValueError()
                    duration += seconds
                    transport = leg.get('transportation', {})
                    product = transport.get('product', {})
                    if type(product.get('class')) is not int:
                        walking_known = False
                    if product.get('class') in (99,100):
                        walking += seconds
                    name = transport.get('name') or product.get('name')
                    if isinstance(name, str) and name not in names:
                        names.append(name[:160])
                    from ..commute.usyd import transit_kind
                    kind=transit_kind(transport)
                    if kind and kind not in transit_modes: transit_modes.append(kind)
                    summary_legs.append({'mode':kind or ('walk' if product.get('class')==100 else 'unknown'),
                        'service':name[:160] if isinstance(name,str) else None,'duration_minutes':round(seconds/60,2)})
                departure = legs[0].get('origin', {}).get('departureTimePlanned')
                arrives = legs[-1].get('destination', {}).get('arrivalTimePlanned')
                elapsed = None
                if departure is not None and arrives is not None:
                    elapsed = (instant(arrives) - instant(departure)).total_seconds()
                    if not duration <= elapsed <= 604800:
                        raise ValueError()
                transfers = route.get('interchanges')
                journeys.append({'duration_minutes': None if elapsed is None else round(elapsed / 60, 2),
                                 'leg_travel_minutes': round(duration / 60, 2), 'walking_minutes': round(walking / 60, 2) if walking_known else None,
                                 'transfers': transfers if type(transfers) is int and transfers >= 0 else None,
                                 'departure_at': departure, 'arrival_at': arrives, 'services': names,
                                 'transit_modes':transit_modes,'legs':summary_legs})
            return {'provider': 'tfnsw', 'queried_at': now(), 'query': body, 'journeys': journeys,
                    'limitations': ['Calculated from scheduled times; future punctuality and availability are not guaranteed.', 'Total duration includes transfers and waiting. It is not estimated when timetable data are missing.', 'Opal fares are excluded. Results are not written into formal recommendations or contract workflows.']}
        except (ValueError, TypeError, KeyError, AttributeError, ApiError):
            raise ApiError(502, 'data_invalid_response', 'The commute response failed schema or timetable checks.') from None
