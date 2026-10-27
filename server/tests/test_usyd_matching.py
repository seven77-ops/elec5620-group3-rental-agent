"""Personalized arrival/day/transfers cannot be replaced by a reference commute."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import tempfile,unittest
from server.app.commute.usyd import DESTINATION
from server.app.commute.planner import arrival_for
from server.app.commute.matching import matching_for_case
from server.app.commute.snapshot import observation
from server.app.adapters.services import Services
from server.app.adapters.real_agent2 import RealProfilesAdapter
from server.app.settings import Settings
from server.app.common import now


class CompleteCommuteConstraintTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ctx=Services(Settings(runtime_dir=self.temp.name));self.adapter=RealProfilesAdapter(self.ctx)
        self.case=self.adapter.create_case({});self.cid=self.case['case_id']
        self.row=next(r for r in self.ctx.settings.catalog.matching({}) if r['usyd_commute']['origin'])
        self.criteria={'arrival_time':'11:00','travel_day':'weekend','commute_max_minutes':30,'commute_mode':'public_transport'}
        self.arrival=arrival_for(self.criteria)
        self.filters={'usyd_mode':'public_transport','usyd_max_minutes':30,'usyd_arrival_time':'11:00','usyd_travel_day':'weekend','usyd_max_transfers':0}
        self.route={'listing_id':self.row['listing_id'],'status':'ok','duration_minutes':18,'transfers':0,
            'departure_at':(self.arrival-timedelta(minutes=18)).isoformat(),'arrival_at':self.arrival.isoformat(),
            'transit_modes':['bus'],'source_url':'https://opendata.transport.nsw.gov.au/dataset/trip-planner-apis'}

    def save(self,**changes):
        saved={'case_id':self.cid,'created_at':now(),'catalog_fingerprint':self.ctx.settings.catalog.fingerprint,
            'message':{'commute_recommendation':{'destination':DESTINATION,'criteria':self.criteria,'routes':[self.route]}}}
        saved.update(changes)
        with self.ctx.repo.transaction() as db:self.ctx.repo.put(db,'assistant_commute_report',self.cid,saved)

    def test_weekend_eleven_zero_transfers_has_no_weekday_nine_fallback(self):
        self.assertEqual(matching_for_case(self.ctx,self.cid,self.filters),[])
        self.route['transfers']=1;self.save()
        self.assertEqual(matching_for_case(self.ctx,self.cid,self.filters),[])
        self.route['transfers']=0;self.save()
        rows=matching_for_case(self.ctx,self.cid,self.filters)
        self.assertEqual([r['listing_id'] for r in rows],[self.row['listing_id']])
        self.assertEqual(rows[0]['usyd_commute']['modes']['public_transport']['transfers'],0)
        self.assertEqual(rows[0]['usyd_commute']['modes']['public_transport']['reference_arrival_at'],self.arrival.isoformat())

    def test_expired_and_other_campus_or_wrong_mode_cannot_authorize_saved_results(self):
        self.save(created_at=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat())
        self.assertEqual(matching_for_case(self.ctx,self.cid,self.filters),[])
        self.save();self.assertEqual(matching_for_case(self.ctx,self.cid,{**self.filters,'usyd_mode':'train'}),[])
        self.save(message={'commute_recommendation':{'destination':{'id':'camden'},'criteria':self.criteria,'routes':[self.route]}})
        self.assertEqual(matching_for_case(self.ctx,self.cid,self.filters),[])

    def test_new_report_cannot_renew_an_old_route_or_its_evidence_timestamp(self):
        original=(datetime.now(timezone.utc)-timedelta(minutes=40)).isoformat()
        self.route['queried_at']=original
        self.save()
        self.assertEqual(matching_for_case(self.ctx,self.cid,self.filters),[])
        original=(datetime.now(timezone.utc)-timedelta(minutes=20)).isoformat()
        self.route['queried_at']=original
        self.save()
        rows=matching_for_case(self.ctx,self.cid,self.filters)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['usyd_commute']['modes']['public_transport']['queried_at'],original)

    def test_reference_route_cannot_ignore_zero_transfers(self):
        catalog=self.ctx.settings.catalog
        rows=catalog.matching({'usyd_mode':'public_transport','usyd_max_minutes':30,'usyd_max_transfers':0})
        self.assertTrue(rows)
        self.assertTrue(all(r['usyd_commute']['modes']['public_transport']['transfers']==0 for r in rows))

    def test_road_observation_uses_its_own_expiry(self):
        r=deepcopy(self.row);r['usyd_commute']['modes']['drive']['queried_at']='2000-01-01T00:00:00Z'
        self.assertIsNone(observation(r,'drive'))

    def test_standalone_evaluation_does_not_reuse_or_save_expired_commute_evidence(self):
        import time
        from server.app.common import ApiError
        profile={**self.case['draft']['profile'],'budget':{'currency':'AUD','period':'week','scope':'whole_property','maximum':100000},
                 'student_commute':{'mode':'public_transport','maximum_minutes':30,'arrival_time':'11:00','travel_day':'weekend','max_transfers':0}}
        case=self.adapter.draft(self.cid,{'expected_revision':1,'profile':profile})
        self.adapter.confirm(self.cid,{'draft_revision':case['draft']['revision'],'fingerprint':case['draft']['fingerprint'],
            'review_token':case['agent1']['review_token']})
        self.save();start=time.monotonic()
        first=self.adapter.evaluation(self.cid,{'request_id':'fresh-real-transaction','confirmation_version':1})
        self.assertLess(time.monotonic()-start,3)
        self.assertEqual(first['report']['counts']['input'],1)
        self.save(created_at=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat())
        second=self.adapter.evaluation(self.cid,{'request_id':'after-expiry-new-request','confirmation_version':1})
        self.assertEqual(second['report']['counts']['input'],0)
        self.assertNotEqual(first['run_id'],second['run_id'])
        with self.assertRaises(ApiError) as error:
            self.adapter.select(self.cid,{'request_id':'do-not-authorize-expired','run_id':first['run_id'],
                'listing_id':self.row['listing_id'],'confirmed':True})
        self.assertEqual(error.exception.code,'stale_evaluation')

    def test_search_filters_update_conversation_slots(self):
        from server.app.assistant.dialogue import merge_brief
        brief=merge_brief({'rental_brief':{'commute_mode':'walk','commute_max_minutes':40}},
            {'intent':'search','filters':{'usyd_mode':'bus','usyd_max_minutes':20,'usyd_arrival_time':'10:00','usyd_max_transfers':0}})
        self.assertEqual(brief['commute_mode'],'bus');self.assertEqual(brief['commute_max_minutes'],20)
        self.assertEqual(brief['arrival_time'],'10:00');self.assertEqual(brief['max_transfers'],0)
