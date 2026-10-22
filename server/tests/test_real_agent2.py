import copy
import json
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from server.app.main import create_app


class RealAgent2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = TestClient(create_app(runtime_dir=self.temp.name))
        self.case = self.client.post('/api/v1/cases', json={}).json()
        self.cid = self.case['case_id']

    def confirm(self):
        c = self.case
        self.case = self.client.post(f'/api/v1/cases/{self.cid}/profile-confirmations', json={
            'draft_revision': c['draft']['revision'], 'fingerprint': c['draft']['fingerprint'],
            'review_token': c['agent1']['review_token']}).json()

    def evaluate(self, request='evaluate', filters=None):
        body = {'request_id': request, 'confirmation_version': 1}
        if filters is not None: body['filters'] = filters
        return self.client.post(f'/api/v1/cases/{self.cid}/evaluations', json=body)

    def test_default_catalogue_is_500_real_ads_with_four_facts(self):
        self.assertEqual(self.client.get('/api/v1/health').json()['mode'], 'real_listings')
        r = self.client.get('/api/v1/listings?page_size=100').json()
        self.assertEqual(r['total'], 500)
        self.assertEqual(r['catalog']['suburb_count'], 71)
        self.assertEqual(len(r['items']), 100)
        for item in r['items']:
            self.assertTrue(item['listing_id'].startswith('domain:'))
            for key in ('bedrooms', 'bathrooms', 'car_spaces', 'weekly_rent'):
                self.assertIsNotNone(item[key])
            self.assertIsNone(item['commute_minutes'])
            self.assertIsNone(item['rent_scope'])
        next_page = self.client.get('/api/v1/listings?page=2&page_size=100').json()
        self.assertFalse({x['listing_id'] for x in r['items']} & {x['listing_id'] for x in next_page['items']})

    def test_filters_and_validation_and_empty_state(self):
        rows = self.client.get('/api/v1/listings?suburb=Rhodes&min_bedrooms=2&min_bathrooms=2&min_car_spaces=1&max_weekly_rent=1500&sort=rent_asc').json()
        self.assertGreater(rows['total'], 0)
        for row in rows['items']:
            self.assertEqual(row['suburb'], 'Rhodes')
            self.assertGreaterEqual(row['bedrooms'], 2)
            self.assertGreaterEqual(row['bathrooms'], 2)
            self.assertLessEqual(row['weekly_rent'], 1500)
        self.assertEqual(self.client.get('/api/v1/listings?max_weekly_rent=1').json()['total'], 0)
        for query in ('page=0', 'page_size=1000', 'min_bedrooms=-1', 'sort=unknown', 'max_weekly_rent=nan', 'suburb=imaginary'):
            self.assertEqual(self.client.get('/api/v1/listings?'+query).status_code, 422, query)

    def test_zero_bedroom_studios_count_as_one_open_plan_space(self):
        source = json.loads(Path('agent2/data/real/listings.json').read_text())
        studios = [r for r in source if r['bedrooms'] == 0]
        self.assertEqual(len(studios), 5)
        one_plus = self.client.get('/api/v1/listings?min_bedrooms=1&page_size=100').json()
        self.assertEqual(one_plus['total'], 500)
        for raw in studios:
            item = self.client.get('/api/v1/listings/'+raw['record_id']).json()
            self.assertEqual(item['bedrooms'], 1)
            self.assertEqual(item['advertised_bedrooms'], 0)
            self.assertEqual(item['bedroom_count_basis'], 'open_plan_as_one')
            self.assertEqual(item['bedroom_label'], '1（开放式）')
        two_plus = self.client.get('/api/v1/listings?min_bedrooms=2&page_size=100').json()
        self.assertFalse({r['listing_id'] for r in two_plus['items']} & {r['record_id'] for r in studios})
        self.confirm()
        run = self.evaluate(filters={'suburb':'Annandale','min_bedrooms':1}).json()
        item = next(r for r in run['report']['pending_confirmation'] if r['listing_id']==studios[0]['record_id'])
        self.assertEqual(item['bedrooms'],1)
        self.assertEqual(item['evidence_refs']['bedrooms']['source_value'],0)
        self.assertIn('开放式', self.client.get(f'/api/v1/evaluations/{run["run_id"]}/export?format=markdown').text)
        self.assertEqual(json.loads(Path('agent2/data/real/listings.json').read_text()), source)

    def test_evaluation_selection_retry_and_real_contract_boundary(self):
        self.assertEqual(self.evaluate().status_code, 409)
        self.confirm()
        response = self.evaluate(filters={'suburb': 'Rhodes'})
        self.assertEqual(response.status_code, 200, response.text)
        run = response.json()
        self.assertEqual(run['report']['data_mode'], 'real_listings')
        self.assertEqual(run['report']['eligible'], [])
        self.assertGreater(len(run['report']['recommendations']), 0)
        item = run['report']['recommendations'][0]
        self.assertIsNone(item['score'])
        self.assertEqual(item['status'], 'pending')
        self.assertEqual(self.evaluate(filters={'suburb':'Rhodes'}).json(), run)
        self.assertEqual(self.evaluate(filters={'suburb':'Newtown'}).status_code, 409)
        body = {'request_id': 'choose', 'run_id': run['run_id'], 'listing_id': item['listing_id'], 'confirmed': True}
        selection = self.client.post(f'/api/v1/cases/{self.cid}/selections', json=body)
        self.assertEqual(selection.status_code, 200, selection.text)
        saved = selection.json()
        self.assertTrue(saved['requires_verification'])
        self.assertFalse(saved['contract_ready'])
        self.assertIsNone(saved['listing_snapshot']['rent_scope'])
        self.assertEqual(self.client.post(f'/api/v1/cases/{self.cid}/selections', json=body).json(), saved)
        consent = self.client.post(f'/api/v1/cases/{self.cid}/contract-consents', json={'confirmed':True})
        self.assertEqual(consent.status_code, 200, consent.text)
        self.assertTrue(consent.json()['active'])
        self.assertEqual(self.client.get(f'/api/v1/cases/{self.cid}').json()['selection'], saved)
        self.assertEqual(self.client.get(f'/api/v1/evaluations/{run["run_id"]}/export?format=markdown').status_code, 200)
        fresh = TestClient(create_app(runtime_dir=self.temp.name))
        self.assertEqual(fresh.get(f'/api/v1/cases/{self.cid}').json()['selection'], saved)

    def test_selection_is_bound_to_run_and_profile_and_source(self):
        self.confirm()
        run = self.evaluate(filters={'suburb':'Rhodes'}).json()
        body = {'request_id':'choose','run_id':run['run_id'],'listing_id':'DEMO-006','confirmed':True}
        self.assertEqual(self.client.post(f'/api/v1/cases/{self.cid}/selections', json=body).status_code, 409)
        other = self.client.post('/api/v1/cases', json={}).json()
        self.assertEqual(self.client.post(f'/api/v1/cases/{other["case_id"]}/selections', json=body).status_code, 409)
        profile = copy.deepcopy(self.case['draft']['profile']); profile['weights']['cost'] += 1
        self.client.post(f'/api/v1/cases/{self.cid}/profile-drafts',json={'expected_revision':1,'profile':profile})
        body['listing_id'] = run['report']['recommendations'][0]['listing_id']
        self.assertEqual(self.client.post(f'/api/v1/cases/{self.cid}/selections', json=body).status_code, 409)

    def test_catalogue_rejects_missing_corrupt_or_simulated_input(self):
        from server.app.real_data.catalog import RealCatalog
        with self.assertRaises((ValueError, FileNotFoundError)):
            RealCatalog(Path(self.temp.name) / 'missing.json')
        bad = Path(self.temp.name) / 'bad.json'; bad.write_text('[{"listing_id":"DEMO-006"}]')
        with self.assertRaises(ValueError): RealCatalog(bad)
        source = json.loads(Path('agent2/data/real/listings.json').read_text())
        source[0]['address'] = 'Car Space/162 Ross Street, Forest Lodge'
        bad.write_text(json.dumps(source))
        with self.assertRaises(ValueError): RealCatalog(bad)

    def test_real_run_does_not_call_legacy_ai_explainer(self):
        self.confirm(); run = self.evaluate().json()
        result = self.client.post(f'/api/v1/evaluations/{run["run_id"]}/ai-explanations', json={'request_id':'ai','allow_external_ai':True})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.json()['error']['code'], 'real_ai_not_supported')

    def test_reactivating_an_existing_report_updates_latest_without_mutating_it(self):
        self.confirm()
        first = self.evaluate('first', {'suburb':'Rhodes'}).json()
        second = self.evaluate('second', {'suburb':'Newtown'}).json()
        again = self.evaluate('again', {'suburb':'Rhodes'}).json()
        self.assertEqual(again, first)
        state = self.client.get(f'/api/v1/cases/{self.cid}').json()
        self.assertEqual(state['evaluations'][-1]['run_id'], first['run_id'])
        self.assertNotEqual(first['run_id'], second['run_id'])

    def save_profile(self, **changes):
        profile = copy.deepcopy(self.case['draft']['profile'])
        profile.update(changes)
        r = self.client.post(f'/api/v1/cases/{self.cid}/profile-drafts', json={
            'expected_revision':self.case['draft']['revision'], 'profile':profile})
        self.assertEqual(r.status_code, 200, r.text)
        self.case = r.json()

    def test_confirmed_budget_drives_report_instead_of_all_500(self):
        self.confirm()
        run = self.evaluate().json()['report']
        self.assertEqual(run['filters']['max_weekly_rent'], 550)
        self.assertEqual(run['filter_source'], 'confirmed_profile')
        self.assertGreater(run['counts']['input'], 0)
        self.assertLess(run['counts']['input'], 500)
        self.assertTrue(all(r['weekly_rent'] <= 550 for r in run['pending_confirmation']))
        self.assertTrue(any('计价' in note for note in run['unverified_preferences']))

    def test_housing_preferences_survive_agent1_confirmation_and_filter_results(self):
        budget = {**self.case['draft']['profile']['budget'], 'maximum':1500}
        self.save_profile(budget=budget, housing_preferences={'suburb':'Rhodes',
            'min_bedrooms':2, 'min_bathrooms':2, 'min_car_spaces':1})
        self.confirm()
        profile = self.case['confirmations'][-1]['profile']
        self.assertEqual(profile['housing_preferences']['suburb'], 'Rhodes')
        report = self.evaluate().json()['report']
        self.assertEqual(report['filters'], {'suburb':'Rhodes','min_bedrooms':2,
            'min_bathrooms':2,'min_car_spaces':1,'max_weekly_rent':1500,'sort':'rent_asc'})
        self.assertGreater(report['counts']['input'], 0)
        for r in report['pending_confirmation']:
            self.assertEqual(r['suburb'], 'Rhodes')
            self.assertGreaterEqual(r['bedrooms'],2)
            self.assertGreaterEqual(r['bathrooms'],2)
            self.assertGreaterEqual(r['car_spaces'],1)
        context = self.client.get(f'/api/v1/cases/{self.cid}/recommendation-context').json()
        self.assertEqual(context['filters'],report['filters'])
        self.assertEqual(context['profile_version'],1)

    def test_strict_scope_does_not_divide_unknown_advertised_rent(self):
        self.save_profile(occupants=2, housing_preferences={'budget_match_mode':'matching_scope'})
        self.confirm()
        report = self.evaluate().json()['report']
        self.assertNotIn('max_weekly_rent',report['filters'])
        self.assertEqual(report['counts']['input'],500)
        self.assertTrue(report['unverified_preferences'])

    def test_manual_report_records_overrides_instead_of_claiming_profile_match(self):
        self.confirm()
        report = self.evaluate(filters={'max_weekly_rent':1500}).json()['report']
        self.assertEqual(report['filter_source'],'manual')
        self.assertEqual(report['profile_filters']['max_weekly_rent'],550)
        self.assertEqual(report['filters']['max_weekly_rent'],1500)

    def test_unconfirmed_context_never_uses_draft_as_confirmed_conditions(self):
        r = self.client.get(f'/api/v1/cases/{self.cid}/recommendation-context')
        self.assertEqual(r.status_code,200,r.text)
        self.assertIsNone(r.json()['profile_version'])
        self.assertEqual(r.json()['filters'],{'sort':'rent_asc'})
