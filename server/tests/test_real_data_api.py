from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient


class RealDataApiTests(unittest.TestCase):
    def setUp(self):
        from server.app.main import create_app
        from server.app.real_data.providers import DataProviders
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = TestClient(create_app(runtime_dir=self.temp.name, data_provider=DataProviders(env={})))
        self.cid = self.client.post('/api/v1/cases', json={}).json()['case_id']
        self.path = f'/api/v1/cases/{self.cid}/real-listings'

    def body(self):
        return {'request_id': 'manual-1', 'listing': {
            'address': '1/20 Pyrmont Bridge Road, Camperdown', 'postcode': '2050',
            'source_url': 'https://www.domain.com.au/example-18374975',
            'observed_at': (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),
            'weekly_rent': 760, 'rent_scope': 'whole_property', 'bedrooms': 1}}

    def test_market_endpoint_real_values_with_real_catalogue_config(self):
        response = self.client.get('/api/v1/real-data/market?postcode=2050&bedrooms=1&rent_scope=whole_property&weekly_rent=760')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['benchmarks'][0]['median'], 805)
        self.assertEqual(self.client.get('/api/v1/health').json()['mode'], 'real_listings')
        self.assertEqual(self.client.get('/api/v1/real-data/config').json()['coverage']['postcodes'], ['2008','2037','2042','2050'])

    def test_manual_intake_durable_export_and_idempotent(self):
        body = self.body()
        response = self.client.post(self.path, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        self.assertEqual(saved['record_kind'], 'real_manual_unverified')
        self.assertEqual(saved['evaluation_status'], 'not_evaluated')
        self.assertIsNone(saved['bills_included'])
        self.assertEqual(saved['freshness'], 'within_24h')
        self.assertEqual(self.client.post(self.path, json=body).json(), saved)
        self.assertEqual(len(self.client.get(self.path).json()['items']), 1)
        from server.app.main import create_app
        restarted = TestClient(create_app(runtime_dir=self.temp.name))
        self.assertEqual(restarted.get(self.path).json()['items'], [saved])
        export = restarted.get(self.path+'/export')
        self.assertIn('attachment', export.headers['content-disposition'])
        self.assertEqual(export.json()['items'][0]['source_url'], body['listing']['source_url'])
        body['listing']['weekly_rent'] = 800
        self.assertEqual(self.client.post(self.path, json=body).status_code, 409)

    def test_stale_observation_not_refreshed_and_case_isolation(self):
        body = self.body()
        body['listing']['observed_at'] = (datetime.now(timezone.utc)-timedelta(days=3)).isoformat()
        saved = self.client.post(self.path, json=body).json()
        self.assertEqual(saved['freshness'], 'older_than_24h')
        self.assertEqual(saved['observed_at'], body['listing']['observed_at'])
        cid = self.client.post('/api/v1/cases', json={}).json()['case_id']
        self.assertEqual(self.client.get(f'/api/v1/cases/{cid}/real-listings').json()['items'], [])
        self.assertEqual(self.client.post('/api/v1/cases/no-such-case/real-listings', json=body).status_code, 404)

    def test_rejects_invalid_or_future_facts_no_partial_write(self):
        for changes in ({'weekly_rent': True}, {'weekly_rent': -1}, {'weekly_rent': 10 ** 400}, {'source_url': 'javascript:alert(1)'},
                        {'source_url': 'https://user:password@example.com/'}, {'latitude': -33.8},
                        {'observed_at': (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()},
                        {'bills_included': 'yes'}, {'data_kind': 'synthetic'}, {'bedrooms': True}):
            with self.subTest(changes=changes):
                body=self.body();body['listing'].update(changes)
                response=self.client.post(self.path,json=body)
                self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.client.get(self.path).json()['items'], [])

    def test_intake_bound_and_provider_missing_configuration(self):
        for i in range(30):
            body=self.body();body['request_id']=f'm-{i}'
            self.assertEqual(self.client.post(self.path,json=body).status_code,200)
        self.assertEqual(self.client.post(self.path,json=self.body()).status_code,409)
        response=self.client.post('/api/v1/real-data/domain-search',json={
            'postcode':'2050','maximum_weekly_rent':900,'allow_external':True})
        self.assertEqual(response.status_code,503,response.text)
        self.assertEqual(response.json()['error']['code'],'data_not_configured')

    def test_local_env_data_keys_are_allowlisted_not_frontend_secrets(self):
        from scripts.local_ai_env import load_ai_env
        path=Path(self.temp.name)/'.env'
        path.write_text('TFNSW_API_KEY=private\nDOMAIN_API_KEY=private2\nDOMAIN_USE_APPROVED=1\nVITE_DOMAIN_API_KEY=never\n')
        result=load_ai_env(path,{'TFNSW_API_KEY':'existing'})
        self.assertEqual(result['TFNSW_API_KEY'],'existing')
        self.assertEqual(result['DOMAIN_API_KEY'],'private2')
        self.assertNotIn('VITE_DOMAIN_API_KEY',result)
