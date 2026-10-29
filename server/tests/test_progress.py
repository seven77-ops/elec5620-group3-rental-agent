"""Case progress is read-only and follows each saved handoff."""
import copy
import tempfile
import unittest

from fastapi.testclient import TestClient


class ProgressTests(unittest.TestCase):
    def setUp(self):
        from server.tests.legacy_app import create_app
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = TestClient(create_app(runtime_dir=self.temp.name, operator_key='test-key'))
        self.cid = self.client.post('/api/v1/cases', json={}).json()['case_id']

    def steps(self):
        response = self.client.get(f'/api/v1/cases/{self.cid}/progress')
        self.assertEqual(response.status_code, 200, response.text)
        return {s['key']: s for s in response.json()['steps']}

    def test_new_case_starts_with_requirements_and_reading_changes_nothing(self):
        before = self.client.get(f'/api/v1/cases/{self.cid}').json()
        steps = self.steps()
        self.assertEqual(list(steps), ['requirements', 'listings', 'selection', 'contract', 'operator', 'aftercare'])
        self.assertEqual(steps['requirements']['status'], 'in_progress')
        self.assertEqual(steps['aftercare']['status'], 'not_started')
        self.assertEqual(self.client.get(f'/api/v1/cases/{self.cid}').json(), before)

    def test_aftercare_and_operator_queue_are_reported(self):
        config = self.client.get('/api/v1/demo-config').json()
        templates = self.client.get('/api/v1/aftercare/template-commands').json()
        payload = copy.deepcopy(templates['create'])
        payload['tenancy'] = dict(config['tenancy_template'], confirmed=True)
        version = 0
        for n, (operation, body) in enumerate([('create', payload), ('open_bond', templates['open_bond'])]):
            response = self.client.post('/api/v1/aftercare/commands', json={
                'case_id': self.cid, 'request_id': f'p-{n}', 'expected_version': version,
                'operation': operation, 'payload': body})
            self.assertEqual(response.status_code, 200, response.text)
            version = response.json()['version']
        entry = copy.deepcopy(templates['activate_bond'])
        entry['entry']['claims'] = [{'claim_id': 'c1', 'amount_cents': 18000, 'reason': 'Wall mark',
                                     'evidence_refs': [], 'disputed': True}]
        response = self.client.post('/api/v1/aftercare/commands', json={
            'case_id': self.cid, 'request_id': 'p-act', 'expected_version': version,
            'operation': 'activate_bond', 'payload': entry})
        self.assertEqual(response.status_code, 200, response.text)
        steps = self.steps()
        self.assertEqual(steps['aftercare']['status'], 'in_progress')
        self.assertIn('UnderReview', steps['aftercare']['summary'])
        self.assertEqual(steps['operator']['status'], 'waiting')

    def test_unknown_case_is_not_found(self):
        self.assertEqual(self.client.get('/api/v1/cases/rental-unknown/progress').status_code, 404)


if __name__ == '__main__':
    unittest.main()
