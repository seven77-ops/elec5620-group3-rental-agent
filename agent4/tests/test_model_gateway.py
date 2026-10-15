from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from aftercare_agent.contracts import ROOT, load_json
from aftercare_agent.errors import AftercareError
from aftercare_agent.store import AftercareAgent


class ModelGatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.agent = AftercareAgent(Path(self.tmp.name) / 'case.sqlite3')
        for filename in ['01-create.json', '07-open_bond.json', '08-activate_bond.json']:
            command = load_json(ROOT / 'data/demo/requests' / filename)
            command['expected_version'] = 0 if filename.startswith('01') else self.agent.get('aftercare-demo-1', 'demo-tenant')['version']
            self.agent.submit(command)
        self.command = load_json(ROOT / 'data/demo/requests/09-request_draft.json')
        self.command.update(expected_version=3, request_id='model-draft')
        self.command['payload'] = {'use_model': True, 'allow_external_ai': True}

    def case(self):
        return self.agent.get('aftercare-demo-1', 'demo-tenant')

    def fails(self, code, gateway):
        self.agent.gateway = gateway
        before = self.case()
        with self.assertRaises(AftercareError) as context:
            self.agent.submit(self.command)
        self.assertEqual(context.exception.code, code)
        self.assertEqual(before, self.case())

    def test_valid_model_only_selects_evidence_bound_statements(self):
        self.agent.gateway = lambda context: {'statement_ids': [s['id'] for s in context['catalogue']], 'closing': 'itemisation'}
        response = self.agent.submit(self.command)
        draft = response['result']['draft']
        self.assertEqual(draft['mode'], 'constrained_model')
        self.assertEqual(response['case']['bond']['state'], 'AwaitingOutcome')
        self.assertIn('history:entry-1', draft['source_refs'])
        self.assertEqual(draft['delivery_status'], 'prepared_not_sent')

    def test_unknown_model_statement_remains_unpublished(self):
        self.fails('model_invalid', lambda context: {'statement_ids': ['invented-refund-guarantee'], 'closing': 'itemisation'})

    def test_missing_mandatory_statement_remains_unpublished(self):
        self.fails('model_invalid', lambda context: {'statement_ids': [], 'closing': 'itemisation'})

    def test_duplicate_statements_and_unexpected_prose_rejected(self):
        self.fails('model_invalid', lambda context: {'statement_ids': ['update-1', 'update-1'], 'closing': 'itemisation'})
        self.fails('model_invalid', lambda context: {'statement_ids': ['update-1'], 'closing': 'itemisation', 'text': 'guaranteed refund'})

    def test_malformed_selection_rejected(self):
        for candidate in [None, [], {'statement_ids': 'update-1', 'closing': 'itemisation'},
                          {'statement_ids': [{}], 'closing': 'itemisation'},
                          {'statement_ids': ['update-1'], 'closing': 'accept_deduction'}]:
            with self.subTest(candidate=candidate):
                self.fails('model_invalid', lambda context: candidate)

    def test_timeout_rolls_back_entire_draft_command(self):
        def timeout(_):
            raise TimeoutError('simulated')
        self.fails('model_unavailable', timeout)

    def test_explicit_consent_is_required_before_gateway_call(self):
        self.command['payload']['allow_external_ai'] = False
        def unexpected(_):
            self.fail('Provider must not be called without consent')
        self.fails('consent_required', unexpected)

    def test_no_model_setting_means_no_network_call(self):
        self.command['payload']['use_model'] = False
        def unexpected(_):
            self.fail('Offline mode must not call the provider')
        self.agent.gateway = unexpected
        self.assertEqual(self.agent.submit(self.command)['result']['draft']['mode'], 'template')

    def test_review_gate_precedes_any_model_call(self):
        update = load_json(ROOT / 'data/demo/requests/10-bond_update.json')
        update.update(expected_version=3, request_id='new-dispute')
        self.agent.submit(update)
        self.command['expected_version'] = 4
        def unexpected(_):
            self.fail('Provider must not receive a blocked case')
        self.fails('review_required', unexpected)
