"""Behavioral acceptance tests for report UC01/UC02 and Agent2 integration."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preference_agent.bridge import AGENT2, evaluate
from preference_agent.cli import ConversationUI, export_case
from preference_agent.fields import flatten
from preference_agent.handover import HandoverService, LocalSupervisor
from preference_agent.llm import ExtractionError, LLMService, ManualOnly
from preference_agent.service import PreferenceAgent
from preference_agent.store import Store, ConflictError, dumps


class Reply:
    def __init__(self, value):
        self.value = value

    def extractRequirements(self, *args):
        if isinstance(self.value, Exception):
            raise self.value
        return deepcopy(self.value)


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / 'state.sqlite3'
        self.store = Store(self.db_path)
        self.agent = PreferenceAgent(self.store, ManualOnly())
        self.case = self.agent.startCollection()['case_id']
        self.values = flatten(json.loads((AGENT2 / 'data/demo/profiles/commute.json').read_text(encoding="utf-8-sig")))
        self.dataset = json.loads((AGENT2 / 'data/demo/listings.json').read_text(encoding="utf-8-sig"))
        self.handover = HandoverService(self.store)

    def confirm(self, values=None):
        self.agent.setFields(self.case, values or self.values)
        review = self.agent.reviewDraft(self.case)
        self.assertTrue(review['valid'], review['errors'])
        return self.agent.confirmProfile(self.case, review['confirmation_token'], 'TEST_ACTOR')

    def test_missing_budget_period_blocks_confirmation_and_search(self):
        values = deepcopy(self.values)
        del values['budget.period']
        result = self.agent.setFields(self.case, values)
        self.assertIn('budget.period', '\n'.join(result['errors']))
        self.assertNotIn('confirmation_token', self.agent.reviewDraft(self.case))
        with self.assertRaises(ValueError):
            self.handover.submitConfirmed(self.case, self.dataset)

    def test_multiturn_extraction_and_correction_with_evidence(self):
        self.agent.llm = Reply({'updates': [{'field': 'budget.preferred', 'value': 450, 'evidence': '450'}], 'issues': []})
        self.agent.processMessage(self.case, 'My preferred budget is 450')
        self.agent.llm = Reply({'updates': [{'field': 'budget.preferred', 'value': 480, 'evidence': '480'}], 'issues': []})
        self.agent.processMessage(self.case, 'Change it to 480')
        s = self.agent.showDraft(self.case)
        self.assertEqual(s['draft']['values']['budget.preferred'], 480)
        self.assertEqual(s['draft']['revision'], 2)
        self.assertEqual(s['latest_version'], 0)

    def test_model_error_preserves_draft_and_invalidates_review(self):
        self.agent.setFields(self.case, self.values)
        self.agent.reviewDraft(self.case)
        before = self.agent.showDraft(self.case)['draft']
        self.agent.llm = Reply(ExtractionError('simulated timeout'))
        result = self.agent.processMessage(self.case, 'change my budget')
        self.assertEqual(result['state'], 'ProcessingError')
        self.assertEqual(self.agent.showDraft(self.case)['draft'], before)
        self.assertIsNone(self.agent.showDraft(self.case)['review'])

    def test_malformed_or_protected_model_output_is_atomic(self):
        before = self.agent.showDraft(self.case)['draft']
        for bad in [
            {'updates': [{'field': 'budget.maximum', 'value': 500, 'evidence': '500'},
                         {'field': 'profile_version', 'value': 99, 'evidence': '500'}], 'issues': []},
            {'updates': [], 'issues': [], 'confirmed': True},
            {'updates': [{'field': 'budget.maximum', 'value': 500, 'evidence': 'invented'}], 'issues': []}]:
            with self.subTest(bad=bad):
                self.agent.llm = Reply(bad)
                self.assertEqual(self.agent.processMessage(self.case, '500')['state'], 'ProcessingError')
                self.assertEqual(self.agent.showDraft(self.case)['draft'], before)

    def test_undecided_required_value_is_not_invented(self):
        self.agent.setFields(self.case, self.values)
        self.agent.setFields(self.case, {'budget.maximum': None, 'preferred_locations': None})
        r = self.agent.reviewDraft(self.case)
        self.assertFalse(r['valid'])
        self.assertIsNone(r['draft']['values']['budget.maximum'])

    def test_unspecified_optional_information_does_not_block(self):
        values = {**self.values, 'preferred_locations': None, 'additional_requirements': None}
        self.assertEqual(self.confirm(values)['profileVersion'], 1)

    def test_cross_field_conflicts_are_blocked(self):
        cases = [
            {'budget.maximum': 10}, {'commute.maximum_minutes': 1},
            {'move_in_window.to': '2026-01-01'},
            {'soft_preferences': {'private_bedroom': 1}},
            {'rental_mode': 'shared_room'},
            {'weights.commute': 0, 'weights.cost': 0, 'weights.housing': 0, 'weights.amenities': 0}]
        for changes in cases:
            with self.subTest(changes=changes):
                self.agent.setFields(self.case, {**self.values, **changes})
                self.assertFalse(self.agent.reviewDraft(self.case)['valid'])

    def test_manual_bad_type_and_nonfinite_are_atomic(self):
        before = self.agent.showDraft(self.case)['draft']
        for v in [True, -1, float('nan'), float('inf'), '500']:
            with self.subTest(value=v), self.assertRaises(ValueError):
                self.agent.setFields(self.case, {'budget.maximum': v})
        self.assertEqual(self.agent.showDraft(self.case)['draft'], before)

    def test_issue_stays_until_explicit_field_correction(self):
        self.agent.setFields(self.case, self.values)
        self.agent.llm = Reply({'updates': [], 'issues': [
            {'field': 'budget.maximum', 'message': '500 or 600?', 'evidence': '500 or 600'}]})
        self.agent.processMessage(self.case, '500 or 600')
        self.assertFalse(self.agent.reviewDraft(self.case)['valid'])
        self.agent.setFields(self.case, {'budget.maximum': 600})
        self.assertTrue(self.agent.reviewDraft(self.case)['valid'])

    def test_monthly_conversion_is_reviewed_and_original_preserved(self):
        values = {**self.values, 'budget.period': 'month', 'budget.preferred': 1950, 'budget.maximum': 2600}
        record = self.confirm(values)
        self.assertAlmostEqual(record['profile']['budget']['preferred'], 450)
        self.assertAlmostEqual(record['profile']['budget']['maximum'], 600)
        self.assertEqual(record['draftSnapshot']['values']['budget.period'], 'month')

    def test_unsupported_hard_requirement_not_silently_dropped(self):
        self.agent.setFields(self.case, {**self.values, 'preferred_locations': ['Newtown'], 'location_priority': 'hard'})
        self.assertFalse(self.agent.reviewDraft(self.case)['valid'])
        self.agent.setFields(self.case, {'location_priority': 'soft'})
        review = self.agent.reviewDraft(self.case)
        self.assertTrue(review['valid'])
        self.assertTrue(any('Location preferences' in warning for warning in review['warnings']))
        record = self.agent.confirmProfile(self.case, review['confirmation_token'], 'TEST_ACTOR')
        self.assertEqual(record['draftSnapshot']['values']['preferred_locations'], ['Newtown'])
        self.assertNotIn('preferred_locations', record['profile'])

    def test_unsupported_extra_requires_priority_and_blocks_hard(self):
        for priority in ['hard', 'unspecified']:
            self.agent.setFields(self.case, {**self.values, 'additional_requirements': [{'text': 'pets allowed', 'priority': priority}]})
            self.assertFalse(self.agent.reviewDraft(self.case)['valid'])

    def test_stale_review_and_duplicate_confirmation_rejected(self):
        self.agent.setFields(self.case, self.values)
        old = self.agent.reviewDraft(self.case)['confirmation_token']
        self.agent.setFields(self.case, {'budget.maximum': 600})
        with self.assertRaises(ValueError):
            self.agent.confirmProfile(self.case, old, 'TEST_ACTOR')
        new = self.agent.reviewDraft(self.case)['confirmation_token']
        self.agent.confirmProfile(self.case, new, 'TEST_ACTOR')
        with self.assertRaises(ValueError):
            self.agent.confirmProfile(self.case, new, 'TEST_ACTOR')

    def test_draft_mutation_preserves_confirmed_version_and_requires_reconfirm(self):
        original = self.confirm()
        self.agent.setFields(self.case, {'budget.maximum': 600})
        self.assertEqual(self.store.profile(self.case, 1), original)
        draft = self.agent.showDraft(self.case)['draft']
        self.assertEqual(draft['based_on_profile_version'], 1)
        self.assertNotEqual(draft['draft_id'], original['sourceDraftId'])
        with self.assertRaises(ValueError):
            self.handover.submitConfirmed(self.case, self.dataset)
        token = self.agent.reviewDraft(self.case)['confirmation_token']
        updated = self.agent.confirmProfile(self.case, token, 'TEST_ACTOR')
        self.assertEqual(updated['profileVersion'], 2)
        self.assertEqual(updated['searchId'], original['searchId'])

    def test_failed_llm_after_confirmation_still_forks_on_correction(self):
        original = self.confirm()
        self.agent.llm = Reply(ExtractionError('timeout'))
        self.agent.processMessage(self.case, 'new request')
        with self.assertRaises(ValueError):
            self.agent.reviewDraft(self.case)
        self.agent.setFields(self.case, {'budget.maximum': 600})
        self.assertEqual(self.agent.showDraft(self.case)['draft']['based_on_profile_version'], 1)
        self.assertEqual(self.store.profile(self.case, 1), original)

    def test_saving_failure_rolls_back_profile_and_session(self):
        self.agent.setFields(self.case, self.values)
        token = self.agent.reviewDraft(self.case)['confirmation_token']
        with patch.object(self.store, 'save', side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError):
                self.agent.confirmProfile(self.case, token, 'TEST_ACTOR')
        with self.assertRaises(ValueError):
            self.store.profile(self.case, 1)
        self.assertEqual(self.agent.showDraft(self.case)['latest_version'], 0)
        self.assertEqual(self.agent.confirmProfile(self.case, token, 'TEST_ACTOR')['profileVersion'], 1)

    def test_database_prevents_profile_update_and_survives_reopen(self):
        original = self.confirm()
        with self.assertRaises(sqlite3.IntegrityError), self.store.transaction() as db:
            db.execute('UPDATE profiles SET payload=? WHERE case_id=?', ('{}', self.case))
        reopened = Store(self.db_path)
        self.assertEqual(reopened.profile(self.case, 1), original)

    def test_optimistic_session_conflict(self):
        first, serial = self.store.load(self.case)
        self.agent.setFields(self.case, {'occupants': 1})
        with self.assertRaises(ConflictError):
            self.store.save(first, serial)

    def test_actual_agent2_integration_and_idempotent_retry(self):
        self.confirm()
        calls = []
        def engine(p, d):
            calls.append(1)
            return evaluate(p, d)
        handover = HandoverService(self.store, LocalSupervisor(self.store, engine))
        first = handover.submitConfirmed(self.case, self.dataset)
        second = handover.submitConfirmed(self.case, self.dataset)
        third = handover.reconcileRetry(first['task_id'])
        self.assertEqual(first['status'], 'completed')
        self.assertEqual(first['report']['counts'], {'input': 30, 'eligible': 15, 'pending': 9, 'excluded': 5, 'duplicates': 1})
        self.assertEqual(first, second)
        self.assertEqual(second, third)
        self.assertEqual(len(calls), 1)

    def test_acceptance_is_persisted_before_evaluation(self):
        self.confirm()
        def engine(p, d):
            task_id = self.agent.showDraft(self.case)['latest_task_id']
            task = self.store.task(task_id)
            self.assertEqual(task['status'], 'accepted')
            self.assertIsNotNone(task['accepted_at'])
            self.assertIsNone(task['report'])
            return evaluate(p, d)
        h = HandoverService(self.store, LocalSupervisor(self.store, engine))
        self.assertEqual(h.submitConfirmed(self.case, self.dataset)['status'], 'completed')

    def test_evaluation_failure_is_not_no_match_and_retry_preserves_identity(self):
        self.confirm()
        def fail(p, d):
            raise RuntimeError('simulated evaluator outage')
        h = HandoverService(self.store, LocalSupervisor(self.store, fail))
        task = h.submitConfirmed(self.case, self.dataset)
        self.assertEqual(task['status'], 'failed')
        with self.assertRaises(ValueError):
            self.agent.reviseAfterNoMatch(self.case, task['task_id'], accept=True)
        retried = self.handover.reconcileRetry(task['task_id'])
        self.assertEqual(retried['task_id'], task['task_id'])
        self.assertEqual(retried['status'], 'completed')
        self.assertEqual(retried['attempts'], 2)

    def test_lost_reply_reconciles_persisted_completed_result(self):
        self.confirm()
        receiver = LocalSupervisor(self.store)
        class LostReply:
            def routeTask(inner, task_id):
                receiver.routeTask(task_id)
                raise TimeoutError('reply lost')
        task = HandoverService(self.store, LostReply()).submitConfirmed(self.case, self.dataset)
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(self.handover.reconcileRetry(task['task_id'])['attempts'], 1)

    def test_unacknowledged_delivery_retained_and_retryable(self):
        self.confirm()
        class Unavailable:
            def routeTask(inner, task_id):
                raise ConnectionError('receiver unavailable')
        task = HandoverService(self.store, Unavailable()).submitConfirmed(self.case, self.dataset)
        self.assertEqual(task['status'], 'unverified')
        self.assertIsNone(task['accepted_at'])
        self.assertEqual(self.handover.reconcileRetry(task['task_id'])['status'], 'completed')

    def test_report_reference_mismatch_is_rejected(self):
        self.confirm()
        def bad_engine(p, d):
            report = evaluate(p, d)
            report['profile_version'] = 99
            return report
        task = HandoverService(self.store, LocalSupervisor(self.store, bad_engine)).submitConfirmed(self.case, self.dataset)
        self.assertEqual(task['status'], 'failed')
        self.assertIsNone(task['report'])

    def test_no_match_revision_requires_valid_current_feedback_and_preserves_profile(self):
        original = self.confirm({**self.values, 'budget.preferred': 1, 'budget.maximum': 1})
        task = self.handover.submitConfirmed(self.case, self.dataset)
        declined = self.agent.reviseAfterNoMatch(self.case, task['task_id'], accept=False)
        self.assertFalse(declined['revision_started'])
        self.assertEqual(self.agent.showDraft(self.case)['state'], 'Confirmed')
        accepted = self.agent.reviseAfterNoMatch(self.case, task['task_id'], accept=True)
        self.assertTrue(accepted['revision_started'])
        self.assertGreater(accepted['pending_count'], 0)
        self.assertEqual(self.store.profile(self.case, 1), original)
        with self.assertRaises(ValueError):
            self.handover.reconcileRetry(task['task_id'])
        self.agent.setFields(self.case, {'budget.maximum': 550, 'budget.preferred': 450})
        token = self.agent.reviewDraft(self.case)['confirmation_token']
        self.agent.confirmProfile(self.case, token, 'TEST_ACTOR')
        with self.assertRaises(ValueError):
            self.agent.reviseAfterNoMatch(self.case, task['task_id'], accept=True)

    def test_empty_dataset_does_not_invent_reasons(self):
        self.confirm()
        dataset = {**self.dataset, 'listings': []}
        task = self.handover.submitConfirmed(self.case, dataset)
        feedback = self.agent.reviseAfterNoMatch(self.case, task['task_id'])
        self.assertEqual(feedback['failed_check_counts'], {})
        self.assertIn('unknown', feedback['explanation'])

    def test_tampered_feedback_not_used_to_justify_revision(self):
        self.confirm({**self.values, 'budget.preferred': 1, 'budget.maximum': 1})
        task = self.handover.submitConfirmed(self.case, self.dataset)
        task['report']['as_of'] = '2026-10-01T10:00:00+10:00'
        with self.store.transaction() as db:
            self.store.save_task(task, db)
        with self.assertRaises(ValueError):
            self.agent.reviseAfterNoMatch(self.case, task['task_id'], accept=True)

    def test_cancel_blocks_collect_confirm_and_retry(self):
        self.confirm()
        task = self.handover.submitConfirmed(self.case, self.dataset)
        self.agent.cancel(self.case)
        with self.assertRaises(ValueError):
            self.agent.setFields(self.case, {'budget.maximum': 600})
        with self.assertRaises(ValueError):
            self.agent.reviewDraft(self.case)
        with self.assertRaises(ValueError):
            self.handover.reconcileRetry(task['task_id'])

    def test_cli_review_confirm_search_and_export(self):
        ui = ConversationUI(self.agent, self.handover, self.case, 'TEST_ACTOR')
        ui.execute('/load examples/demo-draft.json')
        review = json.loads(ui.execute('/review'))
        ui.execute('/confirm ' + review['confirmation_token'])
        task = json.loads(ui.execute('/search'))
        self.assertEqual(task['status'], 'completed')
        folder = Path(self.temp.name) / 'export'
        export_case(self.store, self.case, folder)
        self.assertTrue((folder / 'recommendations.md').is_file())
        self.assertEqual(json.loads((folder / 'rental-profile.json').read_text(encoding="utf-8-sig"))['profile_version'], 1)
        with self.assertRaises(FileExistsError):
            export_case(self.store, self.case, folder)


class LLMTransportTests(unittest.TestCase):
    def service(self, transport):
        return LLMService('https://example.test/v1', 'test-model', 'dummy-test-secret', transport)

    def test_request_and_valid_json_response(self):
        captured = []
        def transport(payload):
            captured.append(payload)
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"updates": [], "issues": []}'}}]}
        result = self.service(transport).extractRequirements('hello', {'values': {}}, [])
        self.assertEqual(result, {'updates': [], 'issues': []})
        self.assertEqual(captured[0]['response_format'], {'type': 'json_object'})
        self.assertNotIn('dummy-test-secret', dumps(captured))

    def test_truncated_malformed_refusal_and_nonfinite_response(self):
        for reason, content in [('length', '{}'), ('stop', 'not json'), ('stop', None), ('stop', '{"value":NaN}')]:
            def transport(payload):
                return {'choices': [{'finish_reason': reason, 'message': {'content': content}}]}
            with self.subTest(reason=reason, content=content), self.assertRaises(ExtractionError):
                self.service(transport).extractRequirements('hello', {}, [])

    def test_network_timeout_has_actionable_error(self):
        def fail(payload):
            raise TimeoutError('secret must not appear')
        with self.assertRaisesRegex(ExtractionError, 'timed out') as cm:
            self.service(fail).extractRequirements('hello', {}, [])
        self.assertNotIn('secret', str(cm.exception))

    def test_missing_configuration_does_not_pretend_to_extract(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ExtractionError):
                LLMService().extractRequirements('budget 500', {}, [])


if __name__ == '__main__':
    unittest.main()
