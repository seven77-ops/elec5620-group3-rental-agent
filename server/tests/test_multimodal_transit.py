"""Actual transit alternatives remain distinct, fresh and constraint-qualified."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import unittest
from server.app.commute.usyd import DESTINATION
from server.app.common import now
from server.app.commute.snapshot import observation,public_record
from server.app.commute.matching import reference_matches
from server.app.commute.cached_plan import reference_answer
from server.tests.test_commute_data import Catalog

SOURCE='https://opendata.transport.nsw.gov.au/dataset/trip-planner-apis'


def planned(minutes=25,service='T1 + 412',modes=None,transfers=1):
    arrival=datetime.now(timezone.utc).replace(second=0,microsecond=0)
    modes=modes or ['train','bus']
    duration=minutes/len(modes)
    return {'status':'planned','duration_minutes':minutes,'walking_minutes':0,'transfers':transfers,
        'departure_at':(arrival-timedelta(minutes=minutes)).isoformat(),'arrival_at':arrival.isoformat(),
        'reference_arrival_at':(arrival+timedelta(minutes=5)).isoformat(),'queried_at':now(),'source_url':SOURCE,
        'services':[service],'transit_modes':modes,
        'legs':[{'mode':mode,'service':service,'duration_minutes':duration} for mode in modes]}


def home():
    mixed=planned();bus=planned(30,'412',['bus'],0)
    return {'listing_id':'home','address':'1 Example Street','suburb':'Camperdown','postcode':'2050',
        'weekly_rent':700,'bedrooms':2,'bathrooms':1,'car_spaces':0,
        'usyd_commute':{'listing_id':'home','origin':deepcopy(DESTINATION),
          'modes':{'public_transport':mixed,'train':deepcopy(mixed),'bus':bus,
                   'metro':{'status':'no_observed_option','duration_minutes':None}}}}


class TransitAlternativeTests(unittest.TestCase):
    def test_legacy_slots_expose_dedup_actual_options_without_mutating_input(self):
        row=home();before=deepcopy(row)
        data={'generated_at':now(),'records':{'home':row['usyd_commute']}}
        public=public_record(data,'home')
        self.assertEqual([r['duration_minutes'] for r in public['transit_options']],[25,30])
        self.assertEqual(public['transit_options'][0]['transit_modes'],['train','bus'])
        self.assertEqual(row,before)

    def test_distinct_same_duration_paths_stay_distinct_and_are_bounded(self):
        row=home();row['usyd_commute']['transit_options']=[planned(25,'another-train-bus')]+[planned(31+i,str(i),['bus'],0) for i in range(10)]
        options=public_record({'generated_at':now(),'records':{'home':row['usyd_commute']}},'home')['transit_options']
        self.assertEqual(len(options),6)
        self.assertEqual([r['duration_minutes'] for r in options[:2]],[25,25])
        self.assertNotEqual(options[0]['services'],options[1]['services'])

    def test_stale_invalid_timing_legs_and_source_alternatives_are_excluded(self):
        row=home();bad=[]
        for change in ({'queried_at':(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()},
                       {'duration_minutes':float('nan')},{'transfers':False},
                       {'source_url':'https://untrusted.example/route'},
                       {'departure_at':'2026-10-01T08:00:00'},
                       {'legs':[{'mode':'bus','duration_minutes':999,'service':'invalid'}]}):
            bad.append({**planned(20),**change})
        row['usyd_commute']['transit_options']=bad
        options=public_record({'generated_at':now(),'records':{'home':row['usyd_commute']}},'home')['transit_options']
        self.assertEqual([r['duration_minutes'] for r in options],[25,30])

    def test_fastest_eligible_actual_option_respects_transfers_and_ceiling(self):
        row=home();filters={'usyd_mode':'public_transport','usyd_max_minutes':30,'usyd_max_transfers':0}
        self.assertTrue(reference_matches(row,filters))
        self.assertFalse(reference_matches(row,{**filters,'usyd_max_minutes':29}))
        self.assertFalse(reference_matches(row,{**filters,'usyd_mode':'train'}))
        self.assertEqual(observation(row,'public_transport',max_transfers=0)['duration_minutes'],30)
        result=reference_answer(Catalog([row]),{'commute_mode':'public_transport','commute_max_minutes':30,'max_transfers':0},DESTINATION)
        self.assertEqual(result['listings'][0]['commute_minutes'],30)
        selected=result['listings'][0]['usyd_commute']['selected_transit_route']
        self.assertEqual((selected['mode'],selected['duration_minutes'],selected['transfers']),('public_transport',30,0))
        self.assertEqual(result['commute_recommendation']['routes'][0]['duration_minutes'],30)

    def test_selection_checks_eligible_alternatives_before_display_bound(self):
        row=home()
        row['usyd_commute']['transit_options']=[planned(15+i,str(i),['bus'],2) for i in range(6)]
        # The independently observed no-transfer slot remains usable even if six faster paths exist.
        selected=observation(row,'public_transport',max_transfers=0)
        self.assertIsNotNone(selected)
        self.assertEqual((selected['duration_minutes'],selected['transfers']),(30,0))

    def test_recent_personal_query_and_mode_bound_selected_route_take_precedence(self):
        row=home();personal=planned(35,'personal',['bus'],0)
        personal['basis']='scheduled_live_query'
        row['usyd_commute']['modes']['public_transport']=personal
        self.assertEqual(observation(row,'public_transport')['duration_minutes'],35)
        selected={**planned(32,'selected',['bus'],0),'mode':'public_transport'}
        row['usyd_commute']['selected_transit_route']=selected
        self.assertEqual(observation(row,'public_transport')['duration_minutes'],32)
        self.assertEqual(observation(row,'train')['duration_minutes'],25)

    def test_unknown_legacy_connection_is_retained_without_claiming_a_transport_mode(self):
        row=home();mixed=row['usyd_commute']['modes']['public_transport']
        mixed['legs'][0]['mode']='unknown'
        mixed['legs'][0]['service']=None
        row['usyd_commute']['modes']['train']={'status':'no_observed_option','duration_minutes':None}
        self.assertIsNotNone(observation(row,'public_transport'))
        self.assertEqual(observation(row,'public_transport')['legs'][0]['mode'],'unknown')

    def test_direct_catalog_filter_attaches_the_transfer_qualified_selected_route(self):
        from server.app.real_data.catalog import RealCatalog
        row=home();catalog=object.__new__(RealCatalog)
        catalog._rows={'home':{**row,'record_id':'home'}};catalog._photos={}
        catalog.commutes={'generated_at':now(),'records':{'home':row['usyd_commute']}}
        cards=catalog.matching({'usyd_mode':'public_transport','usyd_max_minutes':30,'usyd_max_transfers':0})
        self.assertEqual(len(cards),1)
        self.assertEqual(cards[0]['usyd_commute']['selected_transit_route']['duration_minutes'],30)
        self.assertEqual(cards[0]['commute_minutes'],30)
        self.assertEqual(cards[0]['recommendation_mode'],'public_transport')

    def test_reused_personal_query_does_not_publish_stale_alternatives(self):
        from server.app.commute.history import recent_routes
        route={**planned(),'listing_id':'home','status':'ok','basis':'scheduled_live_query'}
        route['transit_options']=[planned(30,'valid',['bus'],0),{**planned(20),'queried_at':'2000-01-01T00:00:00Z'}]
        brief={'commute_mode':'public_transport','commute_max_minutes':40}
        report={'destination':DESTINATION,'criteria':{**brief,'commute_hard_limit':True},
                'catalog_fingerprint':'test','queried_at':now(),'routes':[route]}
        reused=recent_routes([report],brief,DESTINATION,datetime.fromisoformat(route['reference_arrival_at']),{'home'},'test')
        self.assertEqual([r['duration_minutes'] for r in reused['home']['transit_options']],[30])

    def test_includes_train_does_not_mean_train_exclusively(self):
        row=home();self.assertTrue(reference_matches(row,{'usyd_mode':'train','usyd_max_minutes':25}))
        self.assertEqual(observation(row,'train')['transit_modes'],['train','bus'])

    def test_coarse_estimate_never_gains_actual_options_or_legs(self):
        row=home();row['usyd_commute']={'origin':None,'modes':{},'estimates':{'public_transport':{
            'status':'coarse_estimate','queried_at':now(),'lower_minutes':10,'upper_minutes':30,
            'reference_arrival_at':now(),'source_urls':[SOURCE]}}}
        result=reference_answer(Catalog([row]),{'commute_mode':'public_transport','commute_max_minutes':30},DESTINATION)
        card=result['listings'][0]
        self.assertFalse(card['usyd_commute'].get('transit_options'))
        self.assertNotIn('selected_transit_route',card['usyd_commute'])
        self.assertNotIn('legs',result['commute_recommendation']['routes'][0])


class HarvestAndSnapshotTests(unittest.TestCase):
    def test_live_query_rebuilds_null_snapshot_annotation_without_changing_catalogue(self):
        from server.app.commute.planner import CommutePlanner
        row=home();row['usyd_commute']=None;before=deepcopy(row)
        catalog=Catalog([row])
        def trips(body):
            arrival=datetime.fromisoformat(body['arrival_at'])
            route=planned(25,'412',['bus'],0)
            route.update(departure_at=(arrival-timedelta(minutes=25)).isoformat(),arrival_at=arrival.isoformat())
            return {'journeys':[route],'queried_at':now()}
        provider=SimpleNamespace(public_config=lambda:{'tfnsw':{'configured':True}},trips=trips)
        ctx=SimpleNamespace(settings=SimpleNamespace(catalog=catalog),data_provider=provider,
                            repo=SimpleNamespace(connection=SimpleNamespace(in_transaction=False)))
        resolver=SimpleNamespace(listing=lambda item:deepcopy(DESTINATION))
        brief={'commute_mode':'public_transport','commute_max_minutes':30,'max_transfers':0,
               'arrival_time':'09:00','travel_day':'weekday'}
        result=CommutePlanner(ctx,resolver).prepare(brief,DESTINATION,allow_external=True)
        self.assertEqual(len(result['listings']),1)
        annotation=result['listings'][0]['usyd_commute']
        self.assertEqual(annotation['destination'],DESTINATION)
        self.assertEqual(annotation['origin'],{**DESTINATION,'original_address':row['address'],'original_suburb':row['suburb']})
        self.assertTrue(annotation['generated_at'])
        self.assertEqual(annotation['reference_note'],DESTINATION['reference_note'])
        self.assertEqual(annotation['modes']['public_transport']['duration_minutes'],25)
        self.assertEqual(annotation['selected_transit_route']['transfers'],0)
        self.assertEqual(len(annotation['transit_options']),1)
        self.assertEqual(catalog.rows,[before])

    def test_future_harvest_retains_distinct_provider_journeys_and_legacy_slots(self):
        from tools.build_usyd_commutes import observations_for
        routes=[planned(),planned(),planned(25,'different'),planned(30,'single bus',['bus'],0)]
        # Make the first two exact physical duplicates; query metadata is deliberately irrelevant.
        routes[1]=deepcopy(routes[0])
        arrival=datetime.fromisoformat(routes[0]['reference_arrival_at'])
        slots,options=observations_for(routes,arrival,now())
        self.assertEqual([r['duration_minutes'] for r in options],[25,25,30])
        self.assertEqual(slots['train']['transit_modes'],['train','bus'])
        self.assertEqual(slots['metro']['status'],'no_observed_option')
        self.assertEqual(options[0]['legs'],routes[0]['legs'])

    def test_snapshot_additions_fail_closed_and_stale_options_are_not_published(self):
        import json,tempfile
        from pathlib import Path
        from server.app.real_data.catalog import RealCatalog
        from server.app.commute.snapshot import load_snapshot
        from server.app.commute.usyd import CAMPUS_FINGERPRINT
        catalog=RealCatalog()
        identifier=next(k for k,r in catalog.commutes['records'].items() if r.get('origin'))
        record=deepcopy(catalog.commutes['records'][identifier]);record['transit_options']=[planned()]
        bound=SimpleNamespace(_rows={identifier:catalog._rows[identifier]},fingerprint=catalog.fingerprint,path=catalog.path)
        data={'schema_version':'1.0','catalog_fingerprint':catalog.fingerprint,'campus_fingerprint':CAMPUS_FINGERPRINT,
              'destination':DESTINATION,'generated_at':now(),'records':{identifier:record}}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'routes.json';path.write_text(json.dumps(data))
            self.assertIsNotNone(load_snapshot(bound,path))
            for change in ({'source_url':'https://untrusted.example/'},{'duration_minutes':False},
                           {'legs':[{'mode':'drive','duration_minutes':25}]},{'queried_at':'2026-10-01T10:00:00'}):
                broken=deepcopy(data);broken['records'][identifier]['transit_options'][0].update(change)
                path.write_text(json.dumps(broken));self.assertIsNone(load_snapshot(bound,path))
            stale=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()
            data['records'][identifier]['transit_options'][0]['queried_at']=stale
            path.write_text(json.dumps(data));loaded=load_snapshot(bound,path)
            self.assertIsNotNone(loaded)
            self.assertTrue(all(r['queried_at']!=stale for r in public_record(loaded,identifier)['transit_options']))

    def test_live_planner_keeps_actual_alternatives_and_selects_with_transfer_limit(self):
        from server.app.commute.planner import CommutePlanner
        row=home();catalog=Catalog([row]);calls=[]
        def trips(body):
            calls.append(body);target=datetime.fromisoformat(body['arrival_at'])
            result=[]
            for duration,service,modes,transfers in [(20,'mixed',['train','bus'],1),(30,'412',['bus'],0),(30,'413',['bus'],0)]:
                r=planned(duration,service,modes,transfers)
                r.update(departure_at=(target-timedelta(minutes=duration)).isoformat(),arrival_at=target.isoformat())
                result.append(r)
            result+=[deepcopy(result[1]),{**deepcopy(result[0]),'duration_minutes':10}]
            return {'journeys':result,'queried_at':now()}
        provider=SimpleNamespace(public_config=lambda:{'tfnsw':{'configured':True}},trips=trips)
        ctx=SimpleNamespace(settings=SimpleNamespace(catalog=catalog),data_provider=provider,
                            repo=SimpleNamespace(connection=SimpleNamespace(in_transaction=False)))
        brief={'commute_mode':'public_transport','commute_max_minutes':30,'max_transfers':0,'arrival_time':'09:00','travel_day':'weekday'}
        answer=CommutePlanner(ctx,SimpleNamespace()).prepare(brief,DESTINATION,allow_external=True)
        self.assertEqual(len(calls),1)
        self.assertEqual(answer['listings'][0]['commute_minutes'],30)
        selected=answer['listings'][0]['usyd_commute']['selected_transit_route']
        self.assertEqual((selected['mode'],selected['transfers']),('public_transport',0))
        options=answer['listings'][0]['usyd_commute']['transit_options']
        self.assertEqual([r['duration_minutes'] for r in options],[20,30,30])
        self.assertEqual([r['services'][0] for r in options],['mixed','412','413'])
        self.assertTrue(all(r['legs'] for r in options))
