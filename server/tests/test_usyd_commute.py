"""USYD-only policy, whole-inventory annotations and strict commute eligibility."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from server.tests import test_commute_data as commute_harness


class StudentCommutePolicyTests(unittest.TestCase):
    def test_fixed_reference_is_main_campus_and_has_official_provenance(self):
        from server.app.commute.usyd import DESTINATION
        self.assertIn('Camperdown',DESTINATION['label'])
        self.assertIn('Fisher',DESTINATION['label'])
        self.assertAlmostEqual(DESTINATION['latitude'],-33.88630396441765,places=6)
        self.assertTrue(DESTINATION['source_url'].startswith('https://portal.spatial.nsw.gov.au/'))

    def test_never_asks_for_school_or_workplace_or_reuses_camden(self):
        from server.app.assistant import commute
        from server.app.commute.usyd import DESTINATION
        brief={'budget_amount':1200,'budget_period':'week','budget_scope':'whole_property',
            'min_bedrooms':1,'arrival_time':'10:00','commute_max_minutes':20,'commute_mode':'public_transport'}
        self.assertIsNone(commute.next_question(brief))
        legacy={'id':'camden','label':'THE UNIVERSITY OF SYDNEY CAMDEN CAMPUS','latitude':-34.03,'longitude':150.66}
        with patch.object(commute,'plan_routes',return_value={'listings':[]}) as plan:
            answer,options=commute.prepare(SimpleNamespace(),{'commute_destination_options':[legacy]},brief,{},'继续',True)
        self.assertEqual(plan.call_args.args[2],DESTINATION)
        self.assertEqual(brief['destination_id'],DESTINATION['id'])
        self.assertEqual(options,[])

    def test_modes_remain_distinct_in_public_transport_legs(self):
        from server.app.commute.usyd import transit_kind
        self.assertEqual(transit_kind({'product':{'class':1,'name':'Train'}}),'train')
        self.assertEqual(transit_kind({'product':{'class':0,'name':'Metro'}}),'metro')
        self.assertEqual(transit_kind({'product':{'class':5,'name':'Bus'}}),'bus')
        self.assertIsNone(transit_kind({'product':{'class':100,'name':'Footpath'}}))
        self.assertIsNone(transit_kind({'product':{'class':999,'name':'Unknown'}}))


class DefaultCeilingTests(unittest.TestCase):
    setUp=commute_harness.PlannerTests.setUp
    prepare=commute_harness.PlannerTests.prepare
    def test_plain_maximum_excludes_over_limit_and_unknown_even_without_hard_flag(self):
        result=self.prepare(commute_max_minutes=20,commute_hard_limit=False)
        self.assertEqual(result['listings'],[])
        self.assertEqual(result['commute_recommendation']['areas'],[])
        self.assertTrue(result['commute_recommendation']['pending_listings'])


if __name__=='__main__':unittest.main()

class StoredUsydDataTests(unittest.TestCase):
    def test_every_listing_has_source_checked_mode_records_and_twenty_means_twenty(self):
        from server.app.real_data.catalog import RealCatalog
        from server.app.commute.usyd import MODES,DESTINATION
        catalog=RealCatalog()
        self.assertIsNotNone(catalog.commutes)
        self.assertEqual(len(catalog.commutes['records']),1000)
        for row in catalog.matching({}):
            record=row['usyd_commute']
            self.assertEqual(set(record['modes']),set(MODES))
            self.assertEqual(record['destination'],DESTINATION)
            if record['origin'] is None:
                self.assertTrue(all(r['duration_minutes'] is None for r in record['modes'].values()))
        for mode in MODES:
            for row in catalog.matching({'usyd_mode':mode,'usyd_max_minutes':20}):
                precise=row['usyd_commute']['modes'][mode]['duration_minutes']
                if precise is not None:
                    self.assertLessEqual(precise,20)
                    self.assertIsNotNone(row['usyd_commute']['origin'])
                else:
                    self.assertLessEqual(row['usyd_commute']['estimates'][mode]['upper_minutes'],20)
                    self.assertIsNone(row['usyd_commute']['origin'])
        # Rhodes is never described as a ten-minute walk to this actual campus point.
        for row in catalog.matching({'suburb':'Rhodes'}):
            route=row['usyd_commute']['modes']['walk']
            if route['duration_minutes'] is not None:self.assertGreater(route['duration_minutes'],60)

    def test_wrong_campus_profile_and_car_as_walk_sidecars_are_rejected(self):
        import json,tempfile
        from pathlib import Path
        from server.app.real_data.catalog import RealCatalog
        from server.app.commute.snapshot import load_snapshot
        catalog=RealCatalog();data=deepcopy(catalog.commutes)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data.json'
            corrupt=deepcopy(data);corrupt['destination']['label']='USYD Camden'
            path.write_text(json.dumps(corrupt));self.assertIsNone(load_snapshot(catalog,path))
            corrupt=deepcopy(data);corrupt['catalog_fingerprint']='old inventory'
            path.write_text(json.dumps(corrupt));self.assertIsNone(load_snapshot(catalog,path))
            corrupt=deepcopy(data)
            record=next(r for r in corrupt['records'].values() if r['modes']['walk']['duration_minutes'] is not None)
            record['modes']['walk']['source_url']='https://routing.openstreetmap.de/routed-car/'
            path.write_text(json.dumps(corrupt));self.assertIsNone(load_snapshot(catalog,path))

    def test_range_location_is_disclosed_and_does_not_accept_another_street(self):
        from server.app.commute.locations import is_listed_range_endpoint
        row={'address':'6/95-97 Annandale Street, Annandale','suburb':'Annandale'}
        self.assertTrue(is_listed_range_endpoint(row,{'label':'95 ANNANDALE STREET ANNANDALE'}))
        for label in ('96 ANNANDALE STREET ANNANDALE','95 GEORGE STREET ANNANDALE','95 ANNANDALE STREET RHODES'):
            self.assertFalse(is_listed_range_endpoint(row,{'label':label}))

    def test_chat_needs_confirmation_carries_commute_through_agent1_and_recommendation_report(self):
        import tempfile
        from fastapi.testclient import TestClient
        from server.app.main import create_app
        with tempfile.TemporaryDirectory() as tmp:
            client=TestClient(create_app(runtime_dir=tmp))
            case=client.post('/api/v1/cases',json={}).json();root='/api/v1/cases/'+case['case_id']
            c=client.post(root+'/assistant/conversations',json={}).json()
            brief={'suburb':None,'budget_amount':1200,'budget_period':'week','budget_scope':'whole_property',
                'rental_mode':'whole_property','min_bedrooms':1,'min_bathrooms':0,'min_car_spaces':0,'occupants':1,
                'commute_mode':'walk','commute_max_minutes':20}
            proposed=client.post(root+'/assistant/conversations/'+c['conversation_id']+'/proposals',json={
                'request_id':'walk-20','expected_revision':0,'expected_profile_fingerprint':case['draft']['fingerprint'],'brief':brief})
            self.assertEqual(proposed.status_code,200,proposed.text)
            self.assertIn('20',' '.join(proposed.json()['summary']))
            result=client.post(root+'/assistant/proposals/'+proposed.json()['proposal_id']+'/apply',json={'request_id':'apply','confirmed':True})
            self.assertEqual(result.status_code,200,result.text)
            saved=result.json()['case'];profile=saved['confirmations'][-1]['profile']
            self.assertEqual(profile['student_commute'],{'mode':'walk','maximum_minutes':20})
            context=client.get(root+'/recommendation-context').json()
            self.assertEqual(context['filters']['usyd_mode'],'walk');self.assertEqual(context['filters']['usyd_max_minutes'],20)
            report=client.get('/api/v1/evaluations/'+saved['evaluations'][-1]['run_id']).json()['report']
            self.assertGreater(len(report['recommendations']),0)
            for row in report['recommendations']:
                annotation=row['usyd_commute'];minutes=annotation['modes']['walk']['duration_minutes']
                self.assertLessEqual(minutes if minutes is not None else annotation['estimates']['walk']['upper_minutes'],20)
