"""Commute facts must be verified, bounded, consented and independent of case writes."""
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import httpx

from server.app.common import ApiError

BASE = 'https://portal.spatial.nsw.gov.au/server/rest/services/'
ADDRESS = BASE + 'NSW_Geocoded_Addressing_Theme_multiCRS/MapServer/1'
UNIVERSITY = BASE + 'NSW_FOI_Education_Facilities_multiCRS/MapServer/5'


def features(*rows):
    return {'spatialReference': {'wkid': 4326}, 'features': list(rows)}


def address(identifier=1, label='20 PYRMONT BRIDGE ROAD CAMPERDOWN', x=151.177, y=-33.889):
    return {'attributes': {'OBJECTID': identifier, 'address': label, 'addresspointtype': 1,
                           'addresspointuncertainty': None}, 'geometry': {'x': x, 'y': y}}


def destination():
    return {'id': 'nsw:university:2', 'label': 'UNIVERSITY OF SYDNEY', 'latitude': -33.887,
            'longitude': 151.188, 'precision': 'official_poi_point_not_entrance', 'source_url': UNIVERSITY + '/2'}


def row(i=1, suburb='Camperdown', rent=600):
    return {'listing_id': f'domain:{i}', 'record_id': f'domain:{i}', 'address': '10/20 Pyrmont Bridge Road, '+suburb,
            'suburb': suburb, 'postcode': '2050', 'weekly_rent': rent, 'rent_scope': None,
            'bedrooms': 2, 'bathrooms': 1, 'car_spaces': 0, 'source_url': f'https://www.domain.com.au/real-{i}'}


class LocationsTests(unittest.TestCase):
    def resolver(self, responder):
        from server.app.commute.locations import LocationResolver
        return LocationResolver(transport=httpx.MockTransport(responder))

    def test_search_is_bounded_fixed_host_and_source_backed(self):
        sent=[]
        def respond(r):
            sent.append(r)
            return httpx.Response(200, json=features(address()))
        result=self.resolver(respond).search('20 Pyrmont Bridge Road, Camperdown', limit=2)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['latitude'],-33.889)
        self.assertIn('address',result[0]['precision'])
        self.assertTrue(result[0]['source_url'].startswith(ADDRESS))
        self.assertEqual(sent[0].url.host,'portal.spatial.nsw.gov.au')
        self.assertEqual(sent[0].url.params['outSR'],'4326')
        self.assertLessEqual(int(sent[0].url.params['resultRecordCount']),10)
        with self.assertRaises(ApiError): self.resolver(respond).search('x',limit=100)

    def test_search_preserves_ambiguous_campuses_and_precise_poi_disclosure(self):
        def respond(r):
            if 'Education' in r.url.path:
                return httpx.Response(200,json=features(*[
                    {'attributes':{'OBJECTID':i,'generalname':'UNIVERSITY OF SYDNEY', 'alternativelabel':label,
                                   'planimetricaccuracy':10},'geometry':{'x':151+i/1000,'y':-33.8}}
                    for i,label in [(1,'CAMPERDOWN'),(2,'CAMDEN')]]))
            return httpx.Response(200,json=features())
        items=self.resolver(respond).search('University of Sydney')
        self.assertEqual(len(items),2)
        self.assertNotEqual(items[0]['id'],items[1]['id'])
        self.assertIn('CAMPERDOWN',items[0]['label'])
        self.assertTrue(all('not_entrance' in item['precision'] for item in items))

    def test_listing_matches_building_address_and_caches_without_changing_row(self):
        calls=[]
        def respond(r):
            calls.append(r)
            return httpx.Response(200,json=features(address()))
        resolver=self.resolver(respond); listing=row(); before=deepcopy(listing)
        result=resolver.listing(listing)
        self.assertIsNotNone(result)
        self.assertEqual(result['precision'],'official_address_point_not_unit_entrance')
        self.assertEqual(resolver.listing(listing),result)
        self.assertEqual(len(calls),1)
        self.assertEqual(listing,before)

    def test_unrelated_first_result_suburb_centroid_and_ambiguity_never_geocode_listing(self):
        for response in [features(address(label='20 OTHER ROAD CAMPERDOWN')),
                         features(address(label='20 PYRMONT BRIDGE ROAD NEWTOWN')),
                         features(address(),address(2,x=151.2)),
                         features({'attributes':{'OBJECTID':3,'address':'CAMPERDOWN'},'geometry':{'x':151.18,'y':-33.89}})]:
            with self.subTest(response=response):
                resolver=self.resolver(lambda r: httpx.Response(200,json=response))
                self.assertIsNone(resolver.listing(row()))

    def test_malformed_upstream_and_out_of_nsw_coordinates_never_invent_a_point(self):
        for response in [{'features':'bad'},features(address(x=0)),features(address(x=float('nan'))),
                         {'error':{'message':'private internal error'}}]:
            def respond(r):
                # Explicit malformed bytes permit NaN protocol testing without httpx JSON encoding.
                import json
                return httpx.Response(200,content=json.dumps(response).encode())
            with self.subTest(response=response), self.assertRaises(ApiError):
                self.resolver(respond).search('20 Pyrmont Bridge Road Camperdown')

    def test_input_is_not_sql_and_public_errors_do_not_leak_upstream_text(self):
        sent=[]
        def respond(r):
            sent.append(r)
            return httpx.Response(503,text='secret stack')
        with self.assertRaises(ApiError) as error:
            self.resolver(respond).search("O'Connell Street")
        self.assertNotIn('secret',error.exception.message)
        self.assertNotIn("O'CONNELL",sent[0].url.params['where'].replace("O''CONNELL",''))


class Catalog:
    def __init__(self,rows): self.rows=rows; self.last_filters=None; self.fingerprint='unchanged'
    def filters(self,values):return {k:deepcopy(v) for k,v in values.items() if v is not None}
    def matching(self,filters):
        self.last_filters=filters
        return [deepcopy(r) for r in self.rows if
                (not filters.get('suburb') or r['suburb']==filters['suburb']) and
                all(r[key[4:]]>=value for key,value in filters.items() if key.startswith('min_')) and
                r['weekly_rent']<=filters.get('max_weekly_rent',float('inf'))]


class Resolver:
    def __init__(self): self.calls=[]; self.missing=set()
    def listing(self,r):
        self.calls.append(r['listing_id'])
        return None if r['listing_id'] in self.missing else dict(destination(),precision='official_address_point_not_unit_entrance')


class Provider:
    def __init__(self): self.calls=[]; self.configured=True; self.durations={}; self.error=False
    def public_config(self): return {'tfnsw':{'configured':self.configured}}
    def trips(self,body):
        self.calls.append(body)
        if self.error: raise ApiError(502,'data_invalid_response','服务错误')
        duration=self.durations.get(len(self.calls),25)
        arrival=datetime.fromisoformat(body['arrival_at'])
        return {'journeys':[{'duration_minutes':duration,'walking_minutes':5,'transfers':1,
                            'departure_at':(arrival-timedelta(minutes=duration or 15)).isoformat(),
                            'arrival_at':arrival.isoformat()}], 'limitations':['计划时刻'], 'queried_at':arrival.isoformat()}


class PlannerTests(unittest.TestCase):
    def setUp(self):
        from server.app.commute.planner import CommutePlanner
        self.catalog=Catalog([row()]); self.provider=Provider(); self.resolver=Resolver()
        self.ctx=SimpleNamespace(settings=SimpleNamespace(catalog=self.catalog),data_provider=self.provider,
                                 repo=SimpleNamespace(connection=SimpleNamespace(in_transaction=False)))
        self.planner=CommutePlanner(self.ctx,self.resolver)
        self.brief={'budget_amount':900,'budget_period':'week','budget_scope':'whole_property','min_bedrooms':1,
                    'arrival_time':'09:00','travel_day':'weekday','commute_max_minutes':40,'commute_hard_limit':True,
                    'commute_priority':'balanced','commute_mode':'public_transport','max_transfers':2}

    def prepare(self,**changes):
        return self.planner.prepare(dict(self.brief,**changes),destination(),allow_external=True)

    def test_no_consent_no_key_or_unsupported_mode_performs_no_location_or_trip_queries(self):
        result=self.planner.prepare(self.brief,destination())
        self.assertEqual(result['commute_recommendation']['status'],'unavailable')
        self.assertEqual(self.resolver.calls,[]); self.assertEqual(self.provider.calls,[])
        self.provider.configured=False
        report=self.prepare()['commute_recommendation']
        self.assertTrue(any('TFNSW_API_KEY' in x for x in report['limitations']))
        self.assertEqual(self.resolver.calls,[])
        self.provider.configured=True
        report=self.prepare(commute_mode='drive')['commute_recommendation']
        self.assertTrue(all(r['status']=='unsupported' for r in report['routes']))
        self.assertEqual(self.provider.calls,[])

    def test_filter_before_network_and_empty_matches_are_honest(self):
        self.catalog.rows=[row(rent=1000)]
        report=self.prepare()['commute_recommendation']
        self.assertEqual(report['total_matching'],0); self.assertEqual(report['evaluated_count'],0)
        self.assertEqual(self.resolver.calls,[])

    def test_bounded_round_robin_suburbs_and_preserves_total_matching_and_source(self):
        self.catalog.rows=[row(i,'Alpha',500+i) for i in range(1,21)]+[row(21,'Beta',750),row(22,'Gamma',800)]
        before=deepcopy(self.catalog.rows)
        result=self.prepare(); report=result['commute_recommendation']
        self.assertEqual(report['total_matching'],22); self.assertEqual(report['evaluated_count'],12)
        self.assertEqual(len(self.provider.calls),12)
        self.assertEqual({r['suburb'] for r in result['listings']},{'Alpha','Beta','Gamma'})
        self.assertEqual(self.catalog.rows,before); self.assertEqual(self.catalog.fingerprint,'unchanged')
        self.assertEqual(report['query_limit'],12)

    def test_next_matching_day_arrival_uses_sydney_and_future_date(self):
        from zoneinfo import ZoneInfo
        for day in ['weekday','weekend']:
            report=self.prepare(travel_day=day)['commute_recommendation']
            arrival=datetime.fromisoformat(self.provider.calls[-1]['arrival_at'])
            self.assertGreater(arrival,datetime.now(ZoneInfo('Australia/Sydney')))
            self.assertEqual(arrival.hour,9); self.assertEqual(arrival.minute,0)
            self.assertEqual(arrival.weekday()<5,day=='weekday')
            self.assertEqual(report['date'],arrival.date().isoformat())

    def test_no_arrival_uses_stored_transit_reference_without_inventing_time_or_transfers(self):
        from server.app.common import now
        from server.app.commute.planner import arrival_for
        from server.app.commute.usyd import DESTINATION
        brief={k:v for k,v in self.brief.items() if k not in ('arrival_time','travel_day')}
        baseline=arrival_for(self.brief).isoformat()
        observed={'status':'planned','duration_minutes':25,'transfers':1,'transit_modes':['bus'],
                  'queried_at':now(),'reference_arrival_at':baseline,
                  'source_url':'https://opendata.transport.nsw.gov.au/dataset/trip-planner-apis'}
        self.catalog.rows[0]['usyd_commute']={'origin':dict(DESTINATION),
            'modes':{'public_transport':observed,'bus':deepcopy(observed)}}
        before=deepcopy(brief)
        result=self.planner.prepare(brief,DESTINATION,allow_external=True)
        self.assertEqual([r['listing_id'] for r in result['listings']],['domain:1'])
        report=result['commute_recommendation']
        self.assertEqual(report['basis'],'scheduled_reference')
        self.assertNotIn('arrival_time',report['criteria'])
        self.assertEqual(report['arrival_time'],'')
        self.assertEqual(report['routes'][0]['transfers'],1)
        self.assertEqual(brief,before)
        for changes in ({'max_transfers':0},{'commute_max_minutes':20},{'commute_mode':'train'}):
            with self.subTest(changes=changes):
                result=self.planner.prepare({**brief,**changes},DESTINATION,allow_external=True)
                self.assertEqual(result['listings'],[])
        self.assertEqual(self.resolver.calls,[])
        self.assertEqual(self.provider.calls,[])

    def test_no_arrival_and_no_reference_returns_unavailable_without_asking_or_guessing(self):
        from server.app.commute.usyd import DESTINATION
        brief={k:v for k,v in self.brief.items() if k!='arrival_time'}
        result=self.planner.prepare(brief,DESTINATION,allow_external=True)
        self.assertEqual(result['listings'],[])
        self.assertEqual(result['commute_recommendation']['status'],'unavailable')
        self.assertIsNone(result['commute_recommendation']['routes'][0]['transfers'])
        self.assertEqual(self.provider.calls,[])

    def test_explicit_date_wrong_day_past_invalid_time_or_over_30_days_uses_no_provider(self):
        for change in [{'arrival_time':'25:00'},{'travel_day':'holiday'},{'travel_date':'2020-01-01'},
                       {'travel_date':(datetime.now()+timedelta(days=40)).date().isoformat()},
                       {'commute_max_minutes':0},{'max_transfers':6}]:
            with self.subTest(change=change),self.assertRaises(ApiError): self.prepare(**change)
        self.assertEqual(self.provider.calls,[])

    def test_route_total_is_provider_elapsed_including_wait_and_hard_unknown_excluded(self):
        self.provider.durations={1:None}
        result=self.prepare()
        route=result['commute_recommendation']['routes'][0]
        self.assertEqual(route['status'],'unavailable'); self.assertIsNone(route['duration_minutes'])
        self.assertEqual(result['listings'],[])
        self.provider.durations={2:45}
        result=self.prepare(); route=result['commute_recommendation']['routes'][0]
        self.assertEqual(route['duration_minutes'],45); self.assertEqual(route['status'],'over_limit')
        self.assertEqual(result['listings'],[])

    def test_unknown_transfer_count_cannot_satisfy_max_transfers(self):
        original=self.provider.trips
        def trips(body):
            response=original(body); response['journeys'][0]['transfers']=None; return response
        self.provider.trips=trips
        result=self.prepare()
        self.assertEqual(result['listings'],[])
        self.assertEqual(result['commute_recommendation']['routes'][0]['status'],'unavailable')

    def test_explicit_transfer_limit_keeps_global_fallbacks_pending_even_with_soft_time_limit(self):
        for fallback in ('missing_key','unsupported_mode','no_consent'):
            with self.subTest(fallback=fallback):
                self.provider.configured=fallback!='missing_key'
                brief=dict(self.brief,commute_hard_limit=False,max_transfers=0,
                           commute_mode='drive' if fallback=='unsupported_mode' else 'public_transport')
                result=self.planner.prepare(brief,destination(),allow_external=fallback!='no_consent')
                self.assertEqual(result['listings'],[])
                report=result['commute_recommendation']
                self.assertEqual([r['listing_id'] for r in report['pending_listings']],['domain:1'])
                self.assertIsNone(report['routes'][0]['transfers'])
        self.assertEqual(self.provider.calls,[])
        self.assertEqual(self.resolver.calls,[])

    def test_time_ceiling_never_accepts_unverified_housing_even_with_old_soft_flag(self):
        self.provider.configured=False
        brief=dict(self.brief,commute_hard_limit=False)
        brief.pop('max_transfers')
        result=self.planner.prepare(brief,destination(),allow_external=True)
        self.assertEqual(result['listings'],[])
        self.assertEqual([r['listing_id'] for r in result['commute_recommendation']['pending_listings']],['domain:1'])

    def test_missing_origin_and_provider_failure_remain_visible_and_partial(self):
        self.catalog.rows=[row(1),row(2)]; self.resolver.missing={'domain:1'}
        result=self.prepare(); report=result['commute_recommendation']
        self.assertEqual(report['status'],'partial'); self.assertEqual(len(result['listings']),1)
        self.assertEqual(report['areas'][0]['verified_route_count'],1)
        self.provider.error=True
        report=self.prepare()['commute_recommendation']
        self.assertEqual(report['status'],'unavailable')
        self.assertTrue(all(r['status']=='unavailable' for r in report['routes']))

    def test_rent_and_commute_ranking_are_facts_and_unknown_scope_never_divides(self):
        self.catalog.rows=[row(1,'Alpha',500),row(2,'Beta',800)]
        self.provider.durations={1:35,2:10}
        result=self.prepare(commute_priority='commute')
        self.assertEqual(result['listings'][0]['listing_id'],'domain:2')
        self.provider.durations={3:35,4:10}
        result=self.prepare(commute_priority='rent')
        self.assertEqual(result['listings'][0]['listing_id'],'domain:1')
        result=self.prepare(budget_scope='per_person',budget_amount=300,occupants=2)
        self.assertNotIn('max_weekly_rent',self.catalog.last_filters)
        self.assertTrue(any('计价' in s for s in result['commute_recommendation']['limitations']))

    def test_does_not_touch_repo_and_inputs_or_hold_transaction_for_external_queries(self):
        before=deepcopy(self.brief)
        self.prepare()
        self.assertEqual(self.brief,before)
        self.ctx.repo=SimpleNamespace(connection=SimpleNamespace(in_transaction=True))
        # Caller transaction must be rejected before geocoding or transport.
        count=len(self.provider.calls)
        with self.assertRaises(ApiError): self.prepare()
        self.assertEqual(len(self.provider.calls),count)

class ResolverResilienceTests(unittest.TestCase):
    resolver = LocationsTests.resolver
    def test_source_url_resolves_to_an_official_feature_query(self):
        resolver=self.resolver(lambda r:httpx.Response(200,json=features(address())))
        point=resolver.search('20 Pyrmont Bridge Road Camperdown')[0]
        from urllib.parse import urlsplit,parse_qs
        parsed=urlsplit(point['source_url'])
        self.assertTrue(parsed.path.endswith('/query'))
        self.assertEqual(parse_qs(parsed.query)['objectIds'],['1'])

    def test_one_poi_layer_outage_keeps_valid_official_choices_from_other_layers(self):
        def respond(request):
            if 'Education' in request.url.path:
                return httpx.Response(200,json=features({'attributes':{'OBJECTID':1,'generalname':'UNIVERSITY OF SYDNEY',
                    'alternativelabel':None},'geometry':{'x':151.18,'y':-33.88}}))
            return httpx.Response(503,text='unavailable')
        result=self.resolver(respond).search('University of Sydney')
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['label'],'UNIVERSITY OF SYDNEY')


class PlannerDeadlineTests(unittest.TestCase):
    setUp = PlannerTests.setUp
    prepare = PlannerTests.prepare
    def test_exhausted_deadline_does_not_count_unqueried_rows_as_evaluated(self):
        self.catalog.rows=[row(1),row(2),row(3)]
        # Admission deadline established at 0; every worker sees deadline exceeded.
        with patch('server.app.commute.planner.monotonic',side_effect=[0,25,25,25]):
            report=self.prepare()['commute_recommendation']
        self.assertEqual(report['evaluated_count'],0)
        self.assertEqual(self.resolver.calls,[])
        self.assertTrue(all(r['status']=='unavailable' for r in report['routes']))

class ResolverQueryCoverageTests(unittest.TestCase):
    resolver = LocationsTests.resolver
    def test_full_street_address_uses_exact_query_to_avoid_expensive_statewide_scan(self):
        sent=[]
        def respond(r):
            sent.append(r); return httpx.Response(200,json=features(address()))
        self.resolver(respond).search('20 Pyrmont Bridge Road, Camperdown')
        self.assertEqual(sent[0].url.params['where'],"address = '20 PYRMONT BRIDGE ROAD CAMPERDOWN'")

    def test_station_results_are_not_crowded_out_by_general_buildings(self):
        def respond(r):
            if 'Transport' in r.url.path:
                return httpx.Response(200,json=features({'attributes':{'OBJECTID':9,'generalname':'REDFERN RAILWAY STATION'},
                                                       'geometry':{'x':151.198,'y':-33.89}}))
            if 'Education' in r.url.path: return httpx.Response(200,json=features())
            return httpx.Response(200,json=features(*[{'attributes':{'OBJECTID':i,'generalname':'REDFERN BUILDING '+str(i)},
                        'geometry':{'x':151.2,'y':-33.89}} for i in range(1,6)]))
        result=self.resolver(respond).search('Redfern')
        self.assertIn('nsw:station:9',[item['id'] for item in result])

class PlannerProviderIntegrationTests(unittest.TestCase):
    setUp = PlannerTests.setUp
    prepare = PlannerTests.prepare

    def test_reuses_real_provider_elapsed_duration_and_correct_local_arrival_query(self):
        from server.app.real_data.providers import DataProviders
        from zoneinfo import ZoneInfo
        requests=[]
        def respond(request):
            requests.append(request)
            planned=datetime.strptime(request.url.params['itdDate']+request.url.params['itdTime'],'%Y%m%d%H%M').replace(tzinfo=ZoneInfo('Australia/Sydney'))
            return httpx.Response(200,json={'journeys':[{'interchanges':1,'legs':[
                {'duration':300,'origin':{'departureTimePlanned':(planned-timedelta(minutes=20)).isoformat()},
                 'destination':{'arrivalTimePlanned':(planned-timedelta(minutes=15)).isoformat()},
                 'transportation':{'product':{'class':100}}},
                {'duration':600,'origin':{'departureTimePlanned':(planned-timedelta(minutes=10)).isoformat()},
                 'destination':{'arrivalTimePlanned':planned.isoformat()},'transportation':{'product':{'class':5}}}
            ]}]})
        self.ctx.data_provider=DataProviders(env={'TFNSW_API_KEY':'private-key'},transport=httpx.MockTransport(respond))
        report=self.prepare()['commute_recommendation']
        route=report['routes'][0]
        self.assertEqual(route['duration_minutes'],20)
        self.assertEqual(route['walking_minutes'],5)
        self.assertEqual(route['transfers'],1)
        self.assertEqual(requests[0].url.params['itdTime'],'0900')
        self.assertEqual(requests[0].url.params['depArrMacro'],'arr')
        self.assertNotIn('private-key',str(report))

class BulkLocationTests(unittest.TestCase):
    resolver = LocationsTests.resolver

    def test_bulk_exact_matches_are_bounded_reusable_and_preserve_listing_identity(self):
        sent=[]
        def respond(request):
            sent.append(request)
            return httpx.Response(200,json=features(address()))
        resolver=self.resolver(respond)
        rows=[row(i) for i in range(1,25)]
        result=resolver.prefetch(rows)
        self.assertEqual(len(result['points']),24)
        self.assertEqual(len(sent),1)  # Same building address is queried only once.
        self.assertIn('address IN (',sent[0].url.params['where'])
        self.assertEqual(result['points']['domain:1']['original_address'],rows[0]['address'])
        self.assertIsNotNone(resolver.listing(rows[0]))
        self.assertEqual(len(sent),1)

    def test_seeded_points_must_match_original_address_suburb_and_official_source(self):
        from server.app.commute.locations import LocationResolver
        resolver=self.resolver(lambda r:httpx.Response(200,json=features(address())))
        points=resolver.prefetch([row()])['points']
        seeded=LocationResolver(points=points,transport=httpx.MockTransport(lambda r: httpx.Response(200,json=features())))
        self.assertIsNotNone(seeded.cached_listing(row()))
        self.assertIsNone(seeded.cached_listing(dict(row(),address='99 Other Road, Camperdown')))
        bad=deepcopy(points);bad['domain:1']['source_url']='https://evil.example/x'
        seeded=LocationResolver(points=bad)
        self.assertIsNone(seeded.cached_listing(row()))

    def test_bulk_duplicate_and_wrong_street_are_not_accepted(self):
        for response in [features(address(),address(2,x=151.2)),features(address(label='20 OTHER ROAD CAMPERDOWN'))]:
            result=self.resolver(lambda r:httpx.Response(200,json=response)).prefetch([row()])
            self.assertEqual(result['points'],{})


class PlannerAreaAndGeographyTests(unittest.TestCase):
    setUp = PlannerTests.setUp
    prepare = PlannerTests.prepare

    def test_area_cards_are_bounded_and_unknown_routes_mark_housing_only(self):
        self.catalog.rows=[row(i,'Area'+str(i),500+i) for i in range(1,20)]
        self.provider.configured=False
        report=self.prepare()['commute_recommendation']
        self.assertLessEqual(len(report['areas']),5)
        self.assertTrue(all(any('仅房型' in text for text in area['tradeoffs']) for area in report['areas']))
        self.assertTrue(all(route['origin_precision']=='unknown' for route in report['routes']))

    def test_cached_actual_coordinates_prioritize_some_nearby_candidates_beyond_cheapest_suburbs(self):
        self.catalog.rows=[row(i,'Area'+str(i),500+i) for i in range(1,25)]
        def cached(r):
            return dict(destination(),latitude=-33.887 if r['listing_id']=='domain:24' else -34.5,
                        longitude=151.188,precision='official_address_point_not_unit_entrance')
        self.resolver.cached_listing=cached
        result=self.prepare()
        self.assertIn('domain:24',[r['listing_id'] for r in result['commute_recommendation']['routes']])
        self.assertEqual(len(self.provider.calls),12)

class ReviewLocationRegressions(unittest.TestCase):
    resolver = LocationsTests.resolver

    def test_campus_tokens_match_across_name_and_alternative_without_dropping_qualifier(self):
        sent=[]
        def respond(request):
            sent.append(request)
            if 'Education' not in request.url.path: return httpx.Response(200,json=features())
            where=request.url.params['where']
            if "'%UNIVERSITY OF SYDNEY CAMPERDOWN%'" in where:
                return httpx.Response(200,json=features())
            return httpx.Response(200,json=features(*[{'attributes':{'OBJECTID':i,
                'generalname':'UNIVERSITY OF SYDNEY','alternativelabel':campus},
                'geometry':{'x':151.18,'y':-33.88}} for i,campus in [(1,'CAMPERDOWN'),(2,'CAMDEN')]]))
        result=self.resolver(respond).search('University of Sydney Camperdown')
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['id'],'nsw:university:1')
        self.assertIn('CAMPERDOWN',result[0]['label'])
        self.assertTrue(all("'%CAMPERDOWN%'" in request.url.params['where'] for request in sent))


class ReviewRouteRegressions(unittest.TestCase):
    setUp = PlannerTests.setUp
    prepare = PlannerTests.prepare

    def test_late_wrong_date_naive_or_inconsistent_journeys_never_satisfy_arrival(self):
        original=self.provider.trips
        mutations=[
            lambda j,a:dict(j,departure_at=(a+timedelta(minutes=35)).isoformat(),arrival_at=(a+timedelta(hours=1)).isoformat()),
            lambda j,a:dict(j,departure_at=(a-timedelta(days=1,minutes=25)).isoformat(),arrival_at=(a-timedelta(days=1)).isoformat()),
            lambda j,a:dict(j,departure_at=(a-timedelta(minutes=25)).replace(tzinfo=None).isoformat(),arrival_at=a.replace(tzinfo=None).isoformat()),
            lambda j,a:dict(j,departure_at=(a-timedelta(minutes=45)).isoformat()),
            lambda j,a:dict(j,arrival_at='not-a-time'),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                def trips(body):
                    response=original(body);arrival=datetime.fromisoformat(body['arrival_at'])
                    response['journeys']=[mutate(response['journeys'][0],arrival)]
                    return response
                self.provider.trips=trips
                result=self.prepare()
                self.assertEqual(result['listings'],[])
                self.assertEqual(result['commute_recommendation']['routes'][0]['status'],'unavailable')
                self.assertIn('到达',result['commute_recommendation']['routes'][0]['reason'])

    def test_aware_utc_timestamps_on_requested_sydney_date_are_valid(self):
        from datetime import timezone
        original=self.provider.trips
        def trips(body):
            response=original(body)
            for key in ('departure_at','arrival_at'):
                response['journeys'][0][key]=datetime.fromisoformat(response['journeys'][0][key]).astimezone(timezone.utc).isoformat().replace('+00:00','Z')
            return response
        self.provider.trips=trips
        self.assertEqual(self.prepare()['commute_recommendation']['routes'][0]['status'],'ok')

    def test_each_route_including_no_key_has_an_actual_outbound_directions_url(self):
        from urllib.parse import urlsplit,parse_qs
        self.catalog.rows=[dict(row(),address='10/20 O\'Connell Street, Camperdown')]
        for configured in (False,True):
            self.provider.configured=configured
            route=self.prepare()['commute_recommendation']['routes'][0]
            parts=urlsplit(route['route_url']); query=parse_qs(parts.query)
            self.assertEqual(parts.scheme,'https');self.assertEqual(parts.netloc,'www.google.com')
            self.assertEqual(parts.path,'/maps/dir/')
            self.assertEqual(query['api'],['1']);self.assertEqual(query['travelmode'],['transit'])
            self.assertEqual(query['origin'],["10/20 O'Connell Street, Camperdown NSW 2050"])
            self.assertEqual(query['destination'],['-33.887,151.188'])
            self.assertIn('transport.nsw.gov.au',route['source_url'])

class ReviewChoiceIdentityRegressions(unittest.TestCase):
    resolver = LocationsTests.resolver

    def test_identical_campus_views_are_one_choice_and_word_fragments_are_not_name_tokens(self):
        def respond(request):
            if 'Transport' in request.url.path: return httpx.Response(200,json=features())
            return httpx.Response(200,json=features(*[
                {'attributes':{'OBJECTID':i,'generalname':label},'geometry':{'x':151.18,'y':-33.88}}
                for i,label in [(1,'UNIVERSITY OF SYDNEY CAMPERDOWN'),(2,'SYDNEY UNIVERSITY POST OFFICE')]]))
        result=self.resolver(respond).search('University of Sydney')
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['label'],'UNIVERSITY OF SYDNEY CAMPERDOWN')

class PendingListingRegressions(unittest.TestCase):
    setUp = PlannerTests.setUp
    prepare = PlannerTests.prepare

    def test_hard_limit_unknown_routes_keep_real_pending_details_without_primary_eligibility(self):
        self.catalog.rows=[dict(row(),photos=[{'url':'https://www.domain.com.au/photo.jpg'}])]
        before=deepcopy(self.catalog.rows)
        self.provider.configured=False
        result=self.prepare()
        report=result['commute_recommendation']
        self.assertEqual(result['listings'],[])
        self.assertEqual(result['actions'],[])
        self.assertEqual([r['listing_id'] for r in report['pending_listings']],['domain:1'])
        pending=report['pending_listings'][0]
        self.assertEqual(pending['address'],before[0]['address'])
        self.assertEqual(pending['photos'],before[0]['photos'])
        self.assertEqual(pending['source_url'],before[0]['source_url'])
        self.assertEqual(pending['commute_status'],'unavailable')
        self.assertIsNone(pending['commute_minutes'])
        self.assertNotIn('actions',pending)
        self.assertEqual(report['routes'][0]['status'],'unavailable')
        self.assertTrue(report['routes'][0]['route_url'])
        self.assertEqual(self.catalog.rows,before)
        self.assertEqual(self.catalog.fingerprint,'unchanged')

    def test_pending_are_bounded_excluded_from_primary_and_not_duplicated_when_verified(self):
        self.catalog.rows=[row(i) for i in range(1,25)]
        self.provider.durations={1:None,2:45}
        result=self.prepare()
        report=result['commute_recommendation']
        primary={r['listing_id'] for r in result['listings']}
        pending={r['listing_id'] for r in report['pending_listings']}
        self.assertEqual(len(primary),10)
        self.assertEqual(len(pending),2)
        self.assertFalse(primary & pending)
        self.provider.configured=False
        report=self.prepare()['commute_recommendation']
        self.assertEqual(len(report['pending_listings']),12)
