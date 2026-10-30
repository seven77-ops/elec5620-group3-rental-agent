import tempfile,unittest
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.tests.test_assistant_api import IntentProvider
from server.app.real_data.catalog import RealCatalog

class SoftIntegrationTests(unittest.TestCase):
    def test_preferences_rank_all_hard_matches_and_persist_then_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            p=IntentProvider();client=TestClient(create_app(runtime_dir=folder,ai_provider=p))
            case=client.post('/api/v1/cases',json={}).json();base='/api/v1/cases/'+case['case_id']+'/assistant/conversations'
            c=client.post(base,json={}).json();filters={'max_weekly_rent':900,'min_bedrooms':2,'min_bathrooms':1}
            p.result={'intent':'search','filters':filters}
            def send(text):
                nonlocal c
                r=client.post(base+'/'+c['conversation_id']+'/messages',json={'request_id':'turn-'+str(c['revision']),'expected_revision':c['revision'],'message':text,'allow_external_ai':True})
                self.assertEqual(r.status_code,200,r.text);c=r.json();return c['messages'][-1]
            first=send('Find homes under 900 per week, at least two bedrooms, shopping is important.')
            self.assertTrue(first.get('soft_preferences'))
            expected=RealCatalog().matching(filters)
            self.assertEqual({r['listing_id'] for r in first['listings']},{r['listing_id'] for r in expected})
            self.assertEqual(c['rental_brief']['lifestyle_priorities'],['shopping'])
            next_answer=send('Shopping no longer matters; prioritize parks.')
            self.assertEqual(c['rental_brief']['lifestyle_priorities'],['parks'])
            self.assertEqual({r['listing_id'] for r in next_answer['listings']},{r['listing_id'] for r in expected})
            cleared=send('No lifestyle preferences.')
            self.assertEqual(c['rental_brief']['lifestyle_priorities'],[])
            self.assertNotIn('soft_preferences',cleared)
            self.assertEqual([r['listing_id'] for r in cleared['listings']],[r['listing_id'] for r in expected])
