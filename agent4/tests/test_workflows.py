from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest

from aftercare_agent.contracts import ROOT, load_json, validate
from aftercare_agent.errors import AftercareError
from aftercare_agent.planner import due_on
from aftercare_agent.store import AftercareAgent

NOW = '2026-10-15T10:00:00+11:00'


class Workflows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.agent = AftercareAgent(Path(self.tmp.name) / 'cases.sqlite3', operator_ids={'demo-operator'})
        self.n = 0
        self.create = load_json(ROOT / 'data/demo/requests/01-create.json')
        self.agent.submit(self.create)

    def case(self):
        return self.agent.get('aftercare-demo-1', 'demo-tenant')

    def command(self, operation, payload, **overrides):
        self.n += 1
        return {'schema_version': '1.0', 'request_id': f'test-{self.n}', 'case_id': 'aftercare-demo-1',
                'actor_id': 'demo-tenant', 'actor_role': 'tenant', 'expected_version': self.case()['version'],
                'as_of': self.case()['updated_at'], 'operation': operation, 'payload': payload, **overrides}

    def run_op(self, operation, payload, **overrides):
        return self.agent.submit(self.command(operation, payload, **overrides))

    def error(self, code, function, *args):
        before = self.case()
        with self.assertRaises(AftercareError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(before, self.case(), 'A failed command must not change committed state')

    def plan(self):
        self.run_op('create_plan', {'move_out_date': '2026-10-31', 'schedule_confirmed': True})

    def entry(self, **changes):
        return {'text': 'Tenant reported update', 'occurred_at': NOW, 'evidence_refs': [],
                'tenant_confirmed': True, 'claims': [], 'conflicting_evidence': False, **changes}

    def active_bond(self):
        self.run_op('open_bond', {'bond_reference': 'DEMO-RBO', 'deposit_evidence_ref': None})
        self.run_op('activate_bond', {'entry': self.entry()})

    def disputed_bond(self):
        self.active_bond()
        self.run_op('bond_update', {'entry': self.entry(claims=[{'claim_id': 'C1', 'amount_cents': 18000,
                    'reason': 'Wall mark', 'evidence_refs': ['photo-1'], 'disputed': True}])})

    def decide(self, decision, resolved=False, **changes):
        return self.run_op('operator_decision', {'review_id': 'review-1', 'decision': decision,
                           'note': 'Synthetic operator decision', 'gate_resolved': resolved, **changes},
                           actor_id='demo-operator', actor_role='operator')

    def draft(self):
        return self.run_op('request_draft', {'use_model': False, 'allow_external_ai': False})

    def test_tailored_plan_inventory_and_practical_dates(self):
        self.plan()
        tasks = {t['task_id']: t for t in self.case()['plan']['tasks']}
        self.assertTrue({'clean-bedroom', 'clean-kitchen', 'clean-bathroom', 'carpet', 'inventory-desk', 'inventory-bed', 'keys'} <= set(tasks))
        self.assertNotIn('outdoor', tasks)
        self.assertEqual(tasks['keys']['due_at'], '2026-10-31T09:00:00+11:00')
        self.assertEqual(tasks['clean-bedroom']['baseline_refs'], ['baseline-1'])
        self.assertEqual(self.case()['plan']['notice_status'], 'unverified_no_legal_countdown')

    def test_unknown_property_stays_draft_until_corrected(self):
        tenancy = deepcopy(self.create['payload']['tenancy'])
        tenancy.update(rooms=None, inventory=None, source_version=2)
        self.run_op('revise_tenancy', {'tenancy': tenancy})
        self.error('needs_clarification', self.run_op, 'create_plan', {'move_out_date': '2026-10-31', 'schedule_confirmed': True})
        self.run_op('create_plan', {'move_out_date': '2026-10-31', 'schedule_confirmed': False})
        self.error('needs_clarification', self.run_op, 'confirm_plan', {'tenant_confirmed': True})
        corrected = deepcopy(self.create['payload']['tenancy'])
        corrected['source_version'] = 3
        self.run_op('revise_tenancy', {'tenancy': corrected})
        self.run_op('confirm_plan', {'tenant_confirmed': True})
        self.assertEqual(self.case()['plan']['state'], 'Active')

    def test_missing_baseline_is_visible_but_does_not_block(self):
        tenancy = deepcopy(self.create['payload']['tenancy'])
        tenancy.update(baseline_evidence_refs=[], source_version=2)
        self.run_op('revise_tenancy', {'tenancy': tenancy})
        self.plan()
        self.assertTrue(self.case()['plan']['evidence_gaps'])
        self.assertIn('baseline', [t['task_id'] for t in self.case()['plan']['tasks']])

    def test_proposed_and_confirmed_reschedule_preserves_done_and_evidence(self):
        self.plan()
        self.run_op('edit_task', {'task_id': 'clean-bedroom', 'status': 'done', 'evidence_refs': ['photo-1']})
        self.run_op('reminder_preferences', {'enabled': True, 'follow_up_at': None})
        previous = self.case()['plan']
        self.run_op('propose_date', {'move_out_date': '2026-11-02'})
        proposed = self.case()
        self.assertEqual(previous['tasks'], proposed['plan']['tasks'])
        self.assertTrue(all(r['state'] == 'suppressed' for r in proposed['reminders']))
        self.run_op('confirm_date', {'accepted': True})
        task = next(t for t in self.case()['plan']['tasks'] if t['task_id'] == 'clean-bedroom')
        self.assertEqual((task['status'], task['evidence_refs']), ('done', ['photo-1']))
        self.assertEqual(task['due_at'], '2026-10-31T09:00:00+11:00')
        self.assertEqual(len(self.case()['plan']['revisions']), 1)

    def test_rejected_date_restores_reminders_without_duplicate_ids(self):
        self.plan()
        self.run_op('reminder_preferences', {'enabled': True, 'follow_up_at': None})
        before = self.case()['reminders']
        self.run_op('propose_date', {'move_out_date': '2026-11-02'})
        self.run_op('confirm_date', {'accepted': False})
        self.assertEqual(before, self.case()['reminders'])

    def test_edit_task_title_date_and_evidence(self):
        self.plan()
        self.run_op('edit_task', {'task_id': 'keys', 'status': 'todo', 'evidence_refs': ['receipt-1'],
                                 'title': 'Arrange handover receipt', 'due_date': '2026-10-30'})
        task = next(t for t in self.case()['plan']['tasks'] if t['task_id'] == 'keys')
        self.assertEqual((task['offset_days'], task['title']), (-1, 'Arrange handover receipt'))

    def test_cancel_plan_suppresses_reminders_retains_evidence(self):
        self.plan()
        self.run_op('reminder_preferences', {'enabled': True, 'follow_up_at': None})
        self.run_op('cancel_plan', {'tenant_confirmed': True, 'reason': 'Tenant cancelled this plan'})
        self.assertEqual(self.case()['plan']['state'], 'Cancelled')
        self.assertTrue(all(r['state'] == 'suppressed' for r in self.case()['reminders']))
        self.assertTrue(self.case()['evidence'])

    def test_plan_conflict_creates_review_before_bond_entry(self):
        self.plan()
        self.run_op('edit_task', {'task_id': 'clean-bedroom', 'status': 'todo', 'evidence_refs': ['photo-1'],
                                 'review_reason': 'Condition evidence conflicts'})
        self.active_bond()
        self.assertEqual(self.case()['bond']['state'], 'UnderReview')
        self.error('review_required', self.draft)

    def test_direct_bond_entry_without_plan(self):
        self.active_bond()
        self.assertIsNone(self.case()['plan'])
        self.assertEqual(self.case()['bond']['state'], 'AwaitingOutcome')
        draft = self.draft()['result']['draft']
        self.assertEqual(draft['delivery_status'], 'prepared_not_sent')
        self.assertEqual(self.case()['bond']['state'], 'AwaitingOutcome')
        self.assertIn('history:entry-1', draft['source_refs'])

    def test_activation_requires_reference_or_deposit(self):
        self.run_op('open_bond', {'bond_reference': None, 'deposit_evidence_ref': None})
        self.error('needs_clarification', self.run_op, 'activate_bond', {'entry': self.entry()})
        self.assertEqual(self.case()['bond']['state'], 'Draft')

    def test_deposit_record_is_valid_alternative(self):
        item = deepcopy(self.create['payload']['evidence'][0])
        item.update(evidence_id='deposit-1', kind='deposit_record')
        self.run_op('add_evidence', {'evidence': item})
        self.run_op('open_bond', {'bond_reference': None, 'deposit_evidence_ref': 'deposit-1'})
        self.run_op('activate_bond', {'entry': self.entry()})
        self.assertEqual(self.case()['bond']['state'], 'AwaitingOutcome')

    def test_dispute_blocks_draft_and_keeps_claim_classification(self):
        self.disputed_bond()
        self.error('review_required', self.draft)
        case = self.case()
        self.assertEqual(case['bond']['claims'][0]['classification'], 'reported_claim')
        self.assertEqual(case['reviews'][0]['status'], 'open')
        self.assertEqual(case['bond']['drafts'], [])

    def test_annotation_hold_referral_and_return_do_not_release(self):
        self.disputed_bond()
        for action in ['annotate', 'hold', 'refer', 'return']:
            self.decide(action)
            self.assertEqual(self.case()['bond']['state'], 'UnderReview')
        self.assertEqual(len(self.case()['reviews']), 1)
        self.error('review_required', self.draft)

    def test_explicit_release_requires_all_review_gates_cleared(self):
        self.disputed_bond()
        self.run_op('bond_update', {'entry': self.entry(conflicting_evidence=True)})
        self.decide('release', True)
        self.assertEqual(self.case()['bond']['state'], 'UnderReview')
        self.decide('release', True, review_id='review-2')
        self.assertEqual(self.case()['bond']['state'], 'AwaitingOutcome')
        self.assertTrue(self.draft()['result']['draft'])

    def test_release_without_resolved_gate_fails(self):
        self.disputed_bond()
        self.error('review_required', self.decide, 'release', False)

    def test_unflagged_update_cannot_clear_previous_dispute(self):
        self.disputed_bond()
        self.run_op('bond_update', {'entry': self.entry()})
        self.assertEqual(self.case()['bond']['state'], 'UnderReview')

    def test_new_evidence_invalidates_old_draft_without_deleting_history(self):
        self.active_bond()
        self.draft()
        item = deepcopy(self.create['payload']['evidence'][0])
        item['evidence_id'] = 'new-evidence'
        self.run_op('add_evidence', {'evidence': item})
        self.assertEqual(self.case()['bond']['drafts'][0]['status'], 'superseded')

    def test_confirmation_cannot_be_inferred_or_performed_in_draft(self):
        self.run_op('open_bond', {'bond_reference': 'RBO', 'deposit_evidence_ref': None})
        self.error('invalid_state', self.run_op, 'confirm_outcome', {'outcome': 'Refund', 'evidence_refs': [], 'tenant_confirmed': True})
        self.error('invalid_input', self.run_op, 'confirm_outcome', {'outcome': 'Refund', 'evidence_refs': [], 'tenant_confirmed': False})

    def test_outcome_closes_reviews_retains_audit_and_suppresses_all_reminders(self):
        self.plan()
        self.disputed_bond()
        self.run_op('reminder_preferences', {'enabled': True, 'follow_up_at': '2026-11-02T09:00:00+11:00'})
        self.run_op('confirm_outcome', {'outcome': 'Tenant confirms actual outcome', 'evidence_refs': [], 'tenant_confirmed': True})
        case = self.case()
        self.assertEqual(case['bond']['state'], 'Resolved')
        self.assertEqual(case['reviews'][0]['status'], 'closed_by_tenant')
        self.assertTrue(all(r['state'] == 'suppressed' for r in case['reminders']))
        self.assertTrue(case['audit'] and case['bond']['history'])
        result = self.run_op('poll_reminders', {}, as_of='2026-11-03T09:00:00+11:00')
        self.assertEqual(result['result']['delivered'], [])
        self.error('case_closed', self.run_op, 'add_evidence', {'evidence': self.create['payload']['evidence'][0]})

    def test_withdrawal_from_draft_is_explicit_and_preserved(self):
        self.run_op('open_bond', {'bond_reference': None, 'deposit_evidence_ref': None})
        self.run_op('withdraw', {'reason': 'Tenant withdraws', 'tenant_confirmed': True})
        self.assertEqual(self.case()['bond']['state'], 'Withdrawn')

    def test_opt_in_and_disable_and_completion_control_delivery(self):
        self.plan()
        self.assertEqual(self.case()['reminders'], [])
        self.run_op('reminder_preferences', {'enabled': True, 'follow_up_at': None})
        self.run_op('edit_task', {'task_id': 'keys', 'status': 'done', 'evidence_refs': []})
        result = self.run_op('poll_reminders', {}, as_of='2026-11-03T09:00:00+11:00')
        self.assertTrue(result['result']['delivered'])
        self.assertNotIn('plan:keys', [r['owner'] for r in result['result']['delivered']])
        again = self.run_op('poll_reminders', {}, as_of='2026-11-03T09:01:00+11:00')
        self.assertEqual(again['result']['delivered'], [])
        self.run_op('reminder_preferences', {'enabled': False, 'follow_up_at': None}, as_of='2026-11-03T09:01:00+11:00')
        self.assertTrue(all(r['state'] == 'suppressed' for r in self.case()['reminders']))

    def test_follow_up_utc_is_displayed_in_sydney_time(self):
        self.active_bond()
        self.run_op('reminder_preferences', {'enabled': True, 'follow_up_at': '2026-10-16T00:00:00Z'})
        self.assertEqual(self.case()['bond']['follow_up_at'], '2026-10-16T11:00:00+11:00')

    def test_dst_uses_local_calendar_days(self):
        self.assertEqual(due_on('2026-10-05', -3), '2026-10-02T09:00:00+10:00')
        self.assertEqual(due_on('2026-10-05', 0), '2026-10-05T09:00:00+11:00')

    def test_exact_replay_returns_original_result_even_after_newer_commands(self):
        command = self.command('open_bond', {'bond_reference': 'RBO', 'deposit_evidence_ref': None})
        original = self.agent.submit(command)
        self.run_op('activate_bond', {'entry': self.entry()})
        self.assertEqual(original, self.agent.submit(command))
        self.assertEqual(self.case()['version'], 3)

    def test_changed_request_id_payload_and_stale_version_rejected(self):
        command = self.command('open_bond', {'bond_reference': 'RBO', 'deposit_evidence_ref': None})
        self.agent.submit(command)
        altered = deepcopy(command)
        altered['payload']['bond_reference'] = 'OTHER'
        self.error('request_conflict', self.agent.submit, altered)
        stale = self.command('activate_bond', {'entry': self.entry()}, expected_version=1)
        self.error('version_conflict', self.agent.submit, stale)

    def test_foreign_tenant_and_unauthorised_operator_denied(self):
        self.error('access_denied', self.agent.submit, self.command('poll_reminders', {}, actor_id='other-tenant'))
        self.error('access_denied', self.agent.submit, self.command('poll_reminders', {}, actor_id='demo-operator', actor_role='operator'))
        with self.assertRaises(AftercareError):
            self.agent.get('aftercare-demo-1', 'stranger')
        self.disputed_bond()
        self.error('access_denied', self.agent.submit, self.command('operator_decision', {'review_id': 'review-1', 'decision': 'release', 'note': 'x', 'gate_resolved': True}))
        with self.assertRaises(AftercareError):
            self.agent.get('aftercare-demo-1', 'unknown-operator', 'operator')

    def test_cross_tenant_context_and_unknown_evidence_fail(self):
        tenancy = deepcopy(self.create['payload']['tenancy'])
        tenancy.update(tenant_id='other', source_version=2)
        self.error('case_mismatch', self.run_op, 'revise_tenancy', {'tenancy': tenancy})
        self.active_bond()
        self.error('missing_evidence', self.run_op, 'bond_update', {'entry': self.entry(evidence_refs=['missing'])})

    def test_evidence_is_immutable_and_future_dates_rejected(self):
        changed = deepcopy(self.create['payload']['evidence'][0])
        changed['source_version'] = 2
        self.error('evidence_conflict', self.run_op, 'add_evidence', {'evidence': changed})
        changed['evidence_id'] = 'new'
        changed['recorded_at'] = '2026-11-01T09:00:00+11:00'
        self.error('invalid_input', self.run_op, 'add_evidence', {'evidence': changed})

    def test_invalid_money_types_dates_and_extra_fields_fail(self):
        self.active_bond()
        for amount in [-1, True, 1.5, 100000001]:
            self.error('invalid_input', self.run_op, 'bond_update', {'entry': self.entry(claims=[{'claim_id': 'C', 'amount_cents': amount, 'reason': 'x', 'evidence_refs': [], 'disputed': False}])})
        self.error('invalid_input', self.run_op, 'create_plan', {'move_out_date': '2026-02-30', 'schedule_confirmed': True})
        self.error('invalid_input', self.run_op, 'poll_reminders', {'force': True})
        self.error('invalid_input', self.agent.submit, self.command('poll_reminders', {}, as_of='2026-10-15T10:00:00'))

    def test_duplicate_claims_and_out_of_order_command_time_fail(self):
        self.disputed_bond()
        claim = deepcopy(self.case()['bond']['claims'][0])
        for key in ['classification', 'entry_id', 'currency']:
            del claim[key]
        self.error('duplicate_claim', self.run_op, 'bond_update', {'entry': self.entry(claims=[claim])})
        self.error('stale_time', self.agent.submit, self.command('poll_reminders', {}, as_of='2026-10-14T10:00:00+11:00'))

    def test_empty_rooms_and_overlong_room_ids_cannot_create_uneditable_tasks(self):
        for rooms in [[], [{'id': 'r' * 80, 'name': 'Room'}]]:
            tenancy = deepcopy(self.create['payload']['tenancy'])
            tenancy.update(rooms=rooms, inventory=None, source_version=2)
            self.error('invalid_input', self.run_op, 'revise_tenancy', {'tenancy': tenancy})

    def test_furnished_empty_inventory_cannot_be_confirmed(self):
        tenancy = deepcopy(self.create['payload']['tenancy'])
        tenancy.update(inventory=[], source_version=2)
        self.run_op('revise_tenancy', {'tenancy': tenancy})
        self.error('needs_clarification', self.run_op, 'create_plan', {'move_out_date': '2026-10-31', 'schedule_confirmed': True})

    def test_inventory_named_check_does_not_collide_with_verification_task(self):
        tenancy = deepcopy(self.create['payload']['tenancy'])
        tenancy.update(inventory=[{'id': 'check', 'name': 'Desk', 'room_id': 'bedroom'}],
                       inventory_confirmed=False, source_version=2)
        self.run_op('revise_tenancy', {'tenancy': tenancy})
        self.run_op('create_plan', {'move_out_date': '2026-10-31', 'schedule_confirmed': False})
        ids = [t['task_id'] for t in self.case()['plan']['tasks']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue({'verify-inventory', 'inventory-check'} <= set(ids))

    def test_storage_failure_rolls_back_case_and_receipt(self):
        before = self.case()
        command = self.command('create_plan', {'move_out_date': '2026-10-31', 'schedule_confirmed': True})
        with closing(sqlite3.connect(self.agent.database)) as conn, conn:
            conn.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON receipts BEGIN SELECT RAISE(ABORT,'simulated storage error'); END")
        self.error('storage_error', self.agent.submit, command)
        with closing(sqlite3.connect(self.agent.database)) as conn, conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 1)
            conn.execute('DROP TRIGGER reject_receipt')
        self.agent.submit(command)
        self.assertEqual(self.case()['version'], before['version'] + 1)

    def test_review_storage_failure_never_reports_routed_success(self):
        self.active_bond()
        with closing(sqlite3.connect(self.agent.database)) as conn, conn:
            conn.execute("CREATE TRIGGER reject_review BEFORE UPDATE ON cases BEGIN SELECT RAISE(ABORT,'queue storage failed'); END")
        self.error('storage_error', self.run_op, 'bond_update', {'entry': self.entry(conflicting_evidence=True)})
        self.assertEqual(self.case()['reviews'], [])

    def test_concurrent_exact_retries_create_one_update(self):
        self.active_bond()
        command = self.command('bond_update', {'entry': self.entry()})
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(self.agent.submit, [command] * 4))
        self.assertTrue(all(r == responses[0] for r in responses))
        self.assertEqual(len(self.case()['bond']['history']), 2)

    def test_concurrent_distinct_writes_require_reload(self):
        self.active_bond()
        commands = [self.command('bond_update', {'entry': self.entry()}) for _ in range(2)]
        def attempt(command):
            try:
                return self.agent.submit(command)['version']
            except AftercareError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, commands))
        self.assertIn('version_conflict', results)
        self.assertEqual(len(self.case()['bond']['history']), 2)

    def test_close_then_poll_cannot_deliver_obsolete_reminders(self):
        self.active_bond()
        self.run_op('reminder_preferences', {'enabled': True, 'follow_up_at': '2026-10-16T09:00:00+11:00'})
        close = self.command('confirm_outcome', {'outcome': 'Confirmed', 'evidence_refs': [], 'tenant_confirmed': True}, as_of='2026-10-16T09:00:00+11:00')
        poll = self.command('poll_reminders', {}, as_of='2026-10-16T09:00:00+11:00')
        self.agent.submit(close)
        self.error('version_conflict', self.agent.submit, poll)
        self.assertEqual(self.run_op('poll_reminders', {}, as_of='2026-10-16T09:00:00+11:00')['result']['delivered'], [])

    def test_case_persists_across_agent_instances_and_passes_schema(self):
        self.active_bond()
        other = AftercareAgent(self.agent.database)
        self.assertEqual(other.get('aftercare-demo-1', 'demo-tenant'), self.case())
        validate('aftercare-case', self.case())

    def test_empty_poll_is_a_read_and_keeps_concurrent_edits_current(self):
        self.plan()
        self.run_op('reminder_preferences', {'enabled': True, 'follow_up_at': None})
        loaded = self.case()
        empty = self.run_op('poll_reminders', {})
        self.assertEqual(empty['result']['delivered'], [])
        self.assertEqual(empty['version'], loaded['version'])
        self.assertEqual(self.case(), loaded, 'An empty poll must not commit')
        # A tenant edit prepared before the poll is still current.
        self.agent.submit({**self.command('edit_task', {'task_id': 'keys', 'status': 'done', 'evidence_refs': []}),
                           'expected_version': loaded['version']})
        due = self.run_op('poll_reminders', {}, as_of='2026-11-03T09:00:00+11:00')
        self.assertTrue(due['result']['delivered'])
        self.assertEqual(due['version'], loaded['version'] + 2, 'A delivering poll still commits once')

    def test_plan_includes_utility_and_bond_refund_steps(self):
        self.plan()
        tasks = {t['task_id']: t for t in self.case()['plan']['tasks']}
        self.assertEqual(tasks['utilities']['due_at'], '2026-10-26T09:00:00+11:00')
        self.assertEqual(tasks['bond-refund']['due_at'], '2026-11-01T09:00:00+11:00')

    def test_empty_poll_retains_receipt_and_request_identity(self):
        poll = self.command('poll_reminders', {})
        response = self.agent.submit(poll)
        changed = {**poll, 'operation': 'reminder_preferences',
                   'payload': {'enabled': True, 'follow_up_at': None}}
        self.error('request_conflict', self.agent.submit, changed)
        self.run_op('reminder_preferences', {'enabled': True, 'follow_up_at': None})
        self.assertEqual(self.agent.submit(poll), response)

    def test_past_move_out_dates_and_zero_claims_are_rejected(self):
        self.error('invalid_input', self.run_op, 'create_plan', {'move_out_date': '2026-10-14', 'schedule_confirmed': True})
        self.plan()
        self.error('invalid_input', self.run_op, 'propose_date', {'move_out_date': '2026-10-01'})
        self.active_bond()
        self.error('invalid_input', self.run_op, 'bond_update', {'entry': self.entry(claims=[
            {'claim_id': 'zero', 'amount_cents': 0, 'reason': 'Nothing', 'evidence_refs': [], 'disputed': False}])})

    def test_draft_uses_readable_sydney_dates(self):
        self.active_bond()
        draft = self.run_op('request_draft', {'use_model': False, 'allow_external_ai': False})['result']['draft']
        self.assertIn('Tenant-reported update (15 Oct 2026)', draft['text'])


if __name__ == '__main__':
    unittest.main()
