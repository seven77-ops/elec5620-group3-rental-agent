"""Approximate commute matching retains transfer and source-freshness checks."""
from copy import deepcopy
import tempfile,unittest
from server.app.commute.snapshot import observation
from server.app.adapters.services import Services
from server.app.adapters.real_agent2 import RealProfilesAdapter
from server.app.settings import Settings


class CompleteCommuteConstraintTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ctx=Services(Settings(runtime_dir=self.temp.name));self.adapter=RealProfilesAdapter(self.ctx)
        self.case=self.adapter.create_case({});self.cid=self.case['case_id']
        self.row=next(r for r in self.ctx.settings.catalog.matching({}) if r['usyd_commute']['origin'])

    def test_reference_route_cannot_ignore_zero_transfers(self):
        catalog=self.ctx.settings.catalog
        rows=catalog.matching({'usyd_mode':'public_transport','usyd_max_minutes':30,'usyd_max_transfers':0})
        self.assertTrue(rows)
        self.assertTrue(all(r['usyd_commute']['modes']['public_transport']['transfers']==0 for r in rows))

    def test_road_observation_uses_its_own_expiry(self):
        r=deepcopy(self.row);r['usyd_commute']['modes']['drive']['queried_at']='2000-01-01T00:00:00Z'
        self.assertIsNone(observation(r,'drive'))


    def test_search_filters_update_conversation_slots(self):
        from server.app.assistant.dialogue import merge_brief
        brief=merge_brief({'rental_brief':{'commute_mode':'walk','commute_max_minutes':40}},
            {'intent':'search','filters':{'usyd_mode':'bus','usyd_max_minutes':20,'usyd_arrival_time':'10:00','usyd_max_transfers':0}})
        self.assertEqual(brief['commute_mode'],'bus');self.assertEqual(brief['commute_max_minutes'],20)
        self.assertNotIn('arrival_time',brief);self.assertEqual(brief['max_transfers'],0)
