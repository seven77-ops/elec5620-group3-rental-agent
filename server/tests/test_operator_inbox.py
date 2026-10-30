"""Submitted reviews and decisions remain discoverable across cases and restarts."""
import copy
import tempfile
import unittest

from fastapi.testclient import TestClient


class OperatorInboxTests(unittest.TestCase):
    def setUp(self):
        from server.tests.legacy_app import create_app
        self.create_app = create_app
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = TestClient(create_app(runtime_dir=self.temp.name, operator_key='inbox-test'))
        self.headers = {'X-Operator-Key': 'inbox-test'}
        self.templates = self.client.get('/api/v1/aftercare/template-commands').json()
        self.config = self.client.get('/api/v1/demo-config').json()

    def command(self, cid, version, operation, payload, key=None):
        response = self.client.post('/api/v1/aftercare/commands', json={
            'case_id': cid, 'request_id': f'{operation}-{version}',
            'expected_version': version, 'operation': operation, 'payload': payload,
        }, headers=key or {})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def dispute(self, address):
        cid = self.client.post('/api/v1/cases', json={}).json()['case_id']
        tenancy = dict(self.config['tenancy_template'], address=address, confirmed=True, baseline_evidence_refs=[])
        created = self.command(cid, 0, 'create', {'tenancy': tenancy, 'evidence': []})
        opened = self.command(cid, created['version'], 'open_bond', {
            'bond_reference': 'TEST-RBO', 'deposit_evidence_ref': None})
        entry = copy.deepcopy(self.templates['activate_bond'])
        entry['entry']['evidence_refs'] = []
        entry['entry']['claims'] = [{'claim_id': 'cleaning', 'amount_cents': 18000,
            'reason': 'Cleaning deduction disputed', 'disputed': True, 'evidence_refs': []}]
        active = self.command(cid, opened['version'], 'activate_bond', entry)
        return cid, active

    def inbox(self, client=None):
        response = (client or self.client).get('/api/v1/operator/reviews', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['items']

    def test_inbox_requires_operator_key(self):
        self.assertEqual(self.client.get('/api/v1/operator/reviews').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/operator/reviews',
            headers={'X-Operator-Key': 'wrong'}).status_code, 403)

    def test_submissions_from_different_cases_are_visible_and_read_only(self):
        one, active = self.dispute('1 Inbox Test Street')
        two, _ = self.dispute('2 Inbox Test Street')
        before = self.client.get(f"/api/v1/aftercare/cases/{active['case_id']}").json()
        items = self.inbox()
        self.assertEqual({i['case_id'] for i in items}, {one, two})
        self.assertEqual({i['status'] for i in items}, {'open'})
        self.assertEqual({i['address'] for i in items}, {'1 Inbox Test Street', '2 Inbox Test Street'})
        self.assertTrue(all(i['claims'][0]['amount_cents'] == 18000 for i in items))
        self.assertEqual(self.client.get(f"/api/v1/aftercare/cases/{active['case_id']}").json(), before)

    def test_hold_and_release_preserve_history_and_only_unlock_guidance(self):
        cid, active = self.dispute('3 Inbox Test Street')
        review_id = active['case']['reviews'][0]['review_id']
        held = self.command(cid, active['version'], 'operator_decision', {
            'review_id': review_id, 'decision': 'hold', 'note': 'Awaiting exit inspection report',
            'gate_resolved': False}, self.headers)
        item = self.inbox()[0]
        self.assertEqual(item['status'], 'open')
        self.assertEqual(item['decisions'][0]['decision'], 'hold')
        released = self.command(cid, held['version'], 'operator_decision', {
            'review_id': review_id, 'decision': 'release', 'note': 'Documents checked; factual inquiry may proceed',
            'gate_resolved': True}, self.headers)
        restarted = TestClient(self.create_app(runtime_dir=self.temp.name, operator_key='inbox-test'))
        item = self.inbox(restarted)[0]
        self.assertEqual(item['status'], 'released')
        self.assertEqual([d['decision'] for d in item['decisions']], ['hold', 'release'])
        self.assertEqual(item['version'], released['version'])
        self.assertEqual(released['case']['bond']['state'], 'AwaitingOutcome')
        self.assertEqual(released['case']['bond']['claims'][0]['classification'], 'reported_claim')
        self.assertIsNone(released['case']['bond']['outcome'])


if __name__ == '__main__':
    unittest.main()
