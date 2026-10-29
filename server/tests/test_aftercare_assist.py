"""Agent 4 web assistance: tenancy prefill, AI deduction reading and constrained model drafts."""
import copy
import tempfile
import unittest

from fastapi.testclient import TestClient

from server.app.ai.provider import ProviderError

MESSAGE = ('Hi, after the exit inspection on 21 October 2026 we will retain $180 for carpet cleaning '
           'and $95.50 to repair a wall mark. Please confirm.')


class Provider:
    """Test double for the shared provider; records every context it receives."""
    def __init__(self, configured=True):
        self.configured, self.calls, self.fail = configured, [], False
        self.extract = {'claims': [
            {'amount': 180, 'reason': 'carpet cleaning', 'quote': '$180 for carpet cleaning'},
            {'amount': 95.5, 'reason': 'wall mark repair', 'quote': '$95.50 to repair a wall mark'},
            {'amount': 400, 'reason': 'invented fee', 'quote': '$400 cleaning fee'},
            {'amount': 200, 'reason': 'wrong amount', 'quote': '$180 for carpet cleaning'}],
            'event_date': '2026-10-21', 'event_date_quote': 'exit inspection on 21 October 2026'}

    def public_config(self):
        return {'enabled': True, 'configured': self.configured, 'provider': 'test', 'model': 'test'}

    def call(self, context):
        self.calls.append(copy.deepcopy(context))
        meta = {'task': context['task'], 'provider': 'test', 'model': 'test', 'status': 'succeeded', 'duration_ms': 1}
        if self.fail or not self.configured:
            raise ProviderError('ai_timeout' if self.configured else 'ai_disabled', meta)
        if context['task'] == 'aftercare_deduction_extract':
            return copy.deepcopy(self.extract), meta
        if context['task'] == 'aftercare_draft_select':
            return {'statement_ids': [s['id'] for s in context['catalogue'] if s['mandatory']],
                    'closing': 'itemisation'}, meta
        raise AssertionError(context['task'])


class AftercareAssistTests(unittest.TestCase):
    def setUp(self):
        from server.tests.legacy_app import create_app
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.provider = Provider()
        self.app = create_app(runtime_dir=self.temp.name, operator_key='test-key', ai_provider=self.provider)
        self.client = TestClient(self.app)
        self.config = self.client.get('/api/v1/demo-config').json()
        self.templates = self.client.get('/api/v1/aftercare/template-commands').json()
        self.cid = self.client.post('/api/v1/cases', json={}).json()['case_id']
        self.version, self.n = 0, 0

    def command(self, operation, payload=None):
        self.n += 1
        response = self.client.post('/api/v1/aftercare/commands', json={
            'case_id': self.cid, 'request_id': f'assist-{self.n}', 'expected_version': self.version,
            'operation': operation, 'payload': copy.deepcopy(self.templates[operation] if payload is None else payload)})
        if response.status_code == 200:
            self.version = response.json()['version']
        return response

    def create(self):
        payload = copy.deepcopy(self.templates['create'])
        payload['tenancy'] = dict(self.config['tenancy_template'], confirmed=True)
        self.assertEqual(self.command('create', payload).status_code, 200)

    def awaiting_outcome(self):
        self.create()
        for operation in ('open_bond', 'activate_bond'):
            self.assertEqual(self.command(operation).status_code, 200)

    def test_prefill_without_sources_is_empty_and_read_only(self):
        result = self.client.get(f'/api/v1/cases/{self.cid}/aftercare/tenancy-prefill').json()
        self.assertEqual(result['values'], {})
        self.assertIsNone(result['source_ref'])
        self.assertTrue(result['warnings'])

    def test_prefill_prefers_contract_review_and_flags_address_conflict(self):
        from server.app.adapters.aftercare_assist import AftercareAssist
        services = next(r.endpoint.__self__.ctx for r in self.app.routes
                        if getattr(r, 'path', '') == '/api/v1/cases/{case_id}/aftercare/tenancy-prefill')
        with services.repo.transaction() as db:
            case = services.get(db, 'case', self.cid)
            case['selection'] = {'listing_id': 'L1', 'listing_snapshot': {'address': '8 Arundel Street, Forest Lodge', 'furnished': True}}
            case['reviews'] = [{'review_id': 'cr-1', 'version': 2, 'status': 'Awaiting Human Review'}]
            services.repo.put(db, 'case', self.cid, case)
            services.repo.put(db, 'review', 'cr-1', {'case_id': self.cid, 'review': {
                'review_id': 'cr-1', 'version': 2, 'status': 'Awaiting Human Review', 'fields': {
                    'address': {'value': '9 Other Street, Glebe NSW 2037', 'evidence': {'line': 4, 'quote': 'Address: 9 Other Street'}},
                    'end_date': {'value': '2027-11-30', 'evidence': {'line': 8, 'quote': 'End date: 2027-11-30'}},
                    'bond': {'value': 2000.0, 'evidence': {'line': 6, 'quote': 'Bond: $2000'}},
                    'rent_amount': {'value': None, 'evidence': None}}}})
        result = AftercareAssist(services).tenancy_prefill(self.cid)
        self.assertEqual(result['source_ref'], 'contract-review:cr-1@v2')
        self.assertEqual(result['values']['address']['value'], '9 Other Street, Glebe NSW 2037')
        self.assertEqual(result['values']['move_out_date']['value'], '2027-11-30')
        self.assertEqual(result['values']['bond_amount']['value'], 2000.0)
        self.assertTrue(result['values']['furnished']['value'])
        self.assertNotIn('rent_amount', result['values'])
        joined = ' '.join(result['warnings'])
        self.assertIn('不一致', joined)
        self.assertIn('Awaiting Human Review', joined)

    def test_extraction_keeps_only_quoted_claims_and_does_not_store_text(self):
        self.create()
        before = self.client.get(f'/api/v1/aftercare/cases/{self.client.get(f"/api/v1/cases/{self.cid}").json()["aftercare_case_id"]}').json()
        response = self.client.post(f'/api/v1/cases/{self.cid}/aftercare/deduction-extract',
                                    json={'allow_external_ai': True, 'message': MESSAGE})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual([(c['amount_cents'], c['reason']) for c in result['claims']],
                         [(18000, 'carpet cleaning'), (9550, 'wall mark repair')])
        self.assertEqual(result['rejected'], 2)
        self.assertEqual(result['event_date'], '2026-10-21')
        self.assertEqual(self.provider.calls[-1]['message'], MESSAGE)
        after = self.client.get(f'/api/v1/aftercare/cases/{before["case_id"]}').json()
        self.assertEqual(after, before, 'Extraction must not change the case')

    def test_extraction_requires_consent_case_and_working_ai(self):
        url = f'/api/v1/cases/{self.cid}/aftercare/deduction-extract'
        self.assertEqual(self.client.post(url, json={'allow_external_ai': True, 'message': MESSAGE}).json()['error']['code'],
                         'aftercare_required')
        self.create()
        self.assertEqual(self.client.post(url, json={'allow_external_ai': False, 'message': MESSAGE}).status_code, 422)
        self.assertEqual(self.client.post(url, json={'allow_external_ai': True, 'message': ' '}).status_code, 422)
        self.provider.fail = True
        failed = self.client.post(url, json={'allow_external_ai': True, 'message': MESSAGE})
        self.assertEqual((failed.status_code, failed.json()['error']['code']), (503, 'ai_unavailable'))

    def test_future_or_unquoted_event_dates_are_dropped(self):
        from server.app.adapters.aftercare_assist import checked_event_date
        from datetime import date
        today = date(2026, 11, 30)
        self.assertEqual(checked_event_date({'event_date': '2026-12-28', 'event_date_quote': 'on 28 December'}, 'on 28 December', today), (None, None))
        self.assertEqual(checked_event_date({'event_date': '2026-11-28', 'event_date_quote': 'not there'}, MESSAGE, today), (None, None))

    def test_model_draft_selects_only_catalogue_statements(self):
        self.awaiting_outcome()
        payload = {'use_model': True, 'allow_external_ai': True}
        response = self.command('request_draft', payload)
        self.assertEqual(response.status_code, 200, response.text)
        draft = response.json()['result']['draft']
        self.assertEqual(draft['mode'], 'constrained_model')
        self.assertEqual(draft['delivery_status'], 'prepared_not_sent')
        self.assertEqual(self.provider.calls[-1]['task'], 'aftercare_draft_select')

    def test_model_draft_needs_consent_and_configuration_and_fails_closed(self):
        self.awaiting_outcome()
        self.assertEqual(self.command('request_draft', {'use_model': True, 'allow_external_ai': False}).status_code, 422)
        self.provider.fail = True
        version = self.version
        failed = self.command('request_draft', {'use_model': True, 'allow_external_ai': True})
        self.assertEqual((failed.status_code, failed.json()['error']['code']), (503, 'model_unavailable'))
        self.assertEqual(self.version, version, 'A failed model draft saves nothing')
        self.provider.configured = False
        self.assertEqual(self.command('request_draft', {'use_model': True, 'allow_external_ai': True}).status_code, 503)
        self.assertEqual(self.command('request_draft', {'use_model': False, 'allow_external_ai': False}).status_code, 200)

    def test_empty_poll_through_web_keeps_version(self):
        self.create()
        self.assertEqual(self.command('reminder_preferences', {'enabled': True, 'follow_up_at': None}).status_code, 200)
        version = self.version
        polled = self.command('poll_reminders', {})
        self.assertEqual(polled.status_code, 200, polled.text)
        self.assertEqual(polled.json()['version'], version)


if __name__ == '__main__':
    unittest.main()
