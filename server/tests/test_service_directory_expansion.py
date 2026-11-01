"""The added Sydney companies remain usable from both chat and saved service records."""
import tempfile
import unittest
from urllib.parse import urlsplit
from fastapi.testclient import TestClient
from server.app.living.catalog import ProviderCatalog
from server.app.main import create_app
from server.tests.test_assistant_api import IntentProvider


class ServiceDirectoryExpansionTests(unittest.TestCase):
    def test_twelve_distinct_sydney_providers_per_service_keep_original_ids(self):
        rows=ProviderCatalog().directory()['providers']
        for category in ('removalist','cleaner'):
            selected=[p for p in rows if category in p['categories']]
            self.assertEqual(len(selected),12)
            self.assertEqual(len({urlsplit(p['website']).hostname.removeprefix('www.') for p in selected}),12)
            for p in selected:
                self.assertTrue('Sydney' in p['coverage'] or '悉尼' in p['coverage'])
                self.assertTrue(p['notes']);self.assertTrue(p['contact_url'].startswith('https://'))
                self.assertEqual(urlsplit(p['website']).hostname.removeprefix('www.'),urlsplit(p['source_url']).hostname.removeprefix('www.'))
        ids={p['id'] for p in rows}
        self.assertTrue({'two-men-and-a-truck','grace','kent','simply-maid','fantastic-cleaners','calibre-cleaning'}<=ids)
        self.assertNotIn('minimovers',ids)

    def test_chat_uses_all_current_companies_and_new_provider_quotes_survive_reload(self):
        with tempfile.TemporaryDirectory() as runtime:
            model=IntentProvider();client=TestClient(create_app(runtime_dir=runtime,ai_provider=model))
            cid=client.post('/api/v1/cases',json={}).json()['case_id'];root=f'/api/v1/cases/{cid}'
            for topic,category in [('moving','removalist'),('cleaning','cleaner')]:
                model.result={'intent':'living_services','topic':topic,'service_action':'recommend'}
                c=client.post(root+'/assistant/conversations',json={}).json()
                response=client.post(root+'/assistant/conversations/'+c['conversation_id']+'/messages',json={
                    'request_id':'more-'+topic,'expected_revision':0,'message':'多推荐一些搬家公司' if topic=='moving' else '多推荐一些退租清洁公司','allow_external_ai':True})
                self.assertEqual(response.status_code,200,response.text)
                providers=response.json()['messages'][-1]['providers'];self.assertEqual(len(providers),12)
                self.assertTrue(all(category in p['categories'] for p in providers))
            value=client.post(root+'/living-services/bookings',json={
                'request_id':'record-quote','expected_version':0,'confirmed':True,
                'values':{'provider_id':'men-that-move','service_date':None,'quote_amount':250,'status':'considering','notes':'用户自行记录的报价'}})
            self.assertEqual(value.status_code,200,value.text)
            fresh=TestClient(create_app(runtime_dir=runtime,ai_provider=model))
            saved=fresh.get(root+'/living-services').json()['bookings']
            self.assertEqual(saved[0]['provider_id'],'men-that-move')
            self.assertEqual(saved[0]['status'],'considering')
            self.assertEqual(saved[0]['quote_amount'],250)
