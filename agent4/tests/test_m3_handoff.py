from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import os
import importlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from aftercare_agent.contracts import ROOT, load_json, validate
from aftercare_agent.errors import AftercareError
from aftercare_agent.handoff import FIELDS, fingerprint
from aftercare_agent.store import AftercareAgent

RAW = ROOT / 'data/demo/m3-handoff'
FIXTURES = RAW / 'snapshots'

def human_fixture():
    # Test double of M3's first persisted snapshot; never applied to production inputs.
    review = load_json(RAW / 'human-review.json')
    review['snapshot_revision'] = 1
    return review

NOW = '2026-10-17T19:01:00+11:00'
TENANT = 'DEMO-TENANT-001'


class M3Handoff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.database = Path(self.tmp.name) / 'm4.sqlite3'
        self.agent = AftercareAgent(self.database)
        self.packet = load_json(FIXTURES / 'normal-confirmation-stub-packet.json')

    def receive(self, packet=None, **kwargs):
        return self.agent.receive(packet or self.packet, actor_id=kwargs.get('actor_id', TENANT), as_of=kwargs.get('as_of', NOW))

    def count(self, table='cases'):
        with closing(self.agent.connect()) as db:
            return db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]

    def error(self, code, function, *args, **kwargs):
        before = self.count()
        with self.assertRaises(AftercareError) as caught:
            function(*args, **kwargs)
        self.assertEqual(code, caught.exception.code)
        self.assertEqual(before, self.count())

    def reconfirm(self, packet):
        r, c = packet['review'], packet['confirmation']
        c.update(review_id=r['review_id'], review_version=r['version'], review_snapshot_revision=r['snapshot_revision'], document_sha256=r['document']['sha256'],
                 review_sha256=fingerprint(r), confirmation_id='DEMO-NEW-CONFIRMATION', confirmation_version=1)
        c['confirmed_fields'].update({k: r['fields'][k]['value'] for k in FIELDS})
        return packet

    def command(self, result, operation, payload, request_id='follow-up'):
        case = self.agent.get(result['case_id'], TENANT)
        return {'schema_version': '1.0', 'request_id': request_id, 'case_id': case['case_id'],
                'actor_id': TENANT, 'actor_role': 'tenant', 'expected_version': case['version'],
                'operation': operation, 'payload': payload, 'as_of': NOW}

    def test_normal_sources_identity_dates_and_no_automatic_plan_or_bond(self):
        result = self.receive()
        self.assertEqual(result['status'], 'created')
        case = self.agent.get(result['case_id'], TENANT)
        validate('aftercare-case', case)
        self.assertIsNone(case['plan'])
        self.assertIsNone(case['bond'])
        self.assertFalse(case['reminders_enabled'])
        self.assertEqual(case['tenant_id'], TENANT)
        self.assertEqual(case['tenancy']['source_ref'], self.packet['confirmation']['confirmation_id'])
        self.assertEqual(case['tenancy']['source_version'], 1)
        self.assertEqual(case['evidence'][0]['source_ref'], self.packet['review']['review_id'])
        self.assertEqual(self.agent.get_handoff(case['case_id'], TENANT), self.packet)
        self.assertEqual(self.agent.get_handoff(case['case_id'], TENANT)['confirmation']['confirmed_fields']['end_date'], '2028-01-31')
        self.assertNotEqual(result['case_id'], self.packet['context']['case_id'])
        self.assertTrue(result['tenancy_id'].startswith('tenancy-'))

    def test_duplicate_same_request_new_request_restart_and_clock(self):
        first = self.receive()
        self.agent = AftercareAgent(self.database)
        for request in (self.packet['request_id'], 'another:delivery'):
            packet = deepcopy(self.packet)
            packet['request_id'] = request
            again = self.receive(packet, as_of='2026-10-17T19:02:00+11:00')
            self.assertEqual(again['status'], 'duplicate')
            self.assertFalse(again['newly_created'])
            self.assertEqual((again['case_id'], again['tenancy_id']), (first['case_id'], first['tenancy_id']))
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.count('m3_handoffs'), 1)

    def test_same_id_changed_content_conflicts(self):
        self.receive()
        self.packet['property_details']['carpeted'] = True
        self.error('request_conflict', self.receive)

    def test_missing_confirmation_is_paused_and_persisted_without_case(self):
        result = self.receive(load_json(FIXTURES / 'missing-confirmation-packet.json'))
        self.assertEqual(result['code'], 'confirmation_required')
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.count('receipts'), 0)
        self.assertEqual(self.count('m3_receipts'), 1)

    def test_selection_confirmation_and_processing_consent_are_insufficient(self):
        self.packet['confirmation']['actual_tenancy_confirmed'] = False
        self.assertTrue(self.packet['review']['selection_evidence']['user_confirmed'])
        self.assertIsNotNone(self.packet['review']['consented_at'])
        self.assertEqual(self.receive()['code'], 'confirmation_required')
        self.assertEqual(self.count(), 0)

    def test_human_review_blocks_even_with_a_confirmation(self):
        self.packet['review'] = human_fixture()
        self.reconfirm(self.packet)
        self.assertEqual(self.receive()['code'], 'review_blocked')
        self.assertEqual(self.count(), 0)

    def test_all_non_reviewed_statuses_block(self):
        for index, status in enumerate(('Questions Ready', 'Awaiting Resubmission', 'Degraded Summary Only')):
            with self.subTest(status=status):
                packet = deepcopy(self.packet)
                packet['request_id'] = status.replace(' ', '-')
                packet['review']['status'] = status
                packet['review']['review_id'] = 'cr-' + str(index) * 32
                self.reconfirm(packet)
                self.assertEqual(self.receive(packet)['code'], 'review_blocked')
        self.assertEqual(self.count(), 0)

    def test_v2_rejects_old_confirmation_and_remembers_newest_even_on_pause(self):
        first = self.receive()
        packet = load_json(FIXTURES / 'v2-old-confirmation-packet.json')
        self.assertEqual(self.receive(packet)['code'], 'review_version_mismatch')
        # An original successful receipt must not bypass newly known current state.
        self.assertEqual(self.receive()['code'], 'stale_snapshot')
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.agent.get(first['case_id'], TENANT)['version'], 1)
        self.assertEqual(self.agent.get_handoff(first['case_id'], TENANT)['review']['version'], 1)
        self.error('handoff_review_stale', self.agent.submit,
                   self.command(first, 'create_plan', {'move_out_date': '2028-02-02', 'schedule_confirmed': True}))

    def test_v2_with_new_confirmation_can_create_on_fresh_case(self):
        packet = self.reconfirm(load_json(FIXTURES / 'v2-old-confirmation-packet.json'))
        packet['request_id'] = 'v2-reconfirmed'
        result = self.receive(packet)
        self.assertEqual(result['status'], 'created')
        self.assertEqual(result['review_version'], 2)
        self.assertEqual(result['receipt']['case']['evidence'][0]['source_version'], 2)

    def test_v2_reconfirmation_preserves_existing_case_without_implicit_overwrite(self):
        first = self.receive()
        packet = self.reconfirm(load_json(FIXTURES / 'v2-old-confirmation-packet.json'))
        packet['request_id'] = 'v2-reconfirmed'
        self.assertEqual(self.receive(packet)['code'], 'existing_tenancy_requires_reconciliation')
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.agent.get(first['case_id'], TENANT)['version'], 1)

    def test_ownership_wrong_actor_and_cross_case_confirmation(self):
        self.error('access_denied', self.receive, actor_id='another-tenant')
        for field in ('tenant_id', 'case_id', 'confirmed_by'):
            packet = deepcopy(self.packet)
            packet['request_id'] = 'wrong-' + field
            packet['confirmation'][field] = 'another-id'
            self.assertEqual(self.receive(packet)['code'], 'confirmation_ownership_mismatch')
        self.assertEqual(self.count(), 0)

    def test_review_and_document_fingerprints_and_field_snapshot(self):
        for key in ('document_sha256', 'review_sha256'):
            packet = deepcopy(self.packet)
            packet['request_id'] = key
            packet['confirmation'][key] = '0' * 64
            self.assertEqual(self.receive(packet)['code'], 'review_fingerprint_mismatch')
        self.packet['confirmation']['confirmed_fields']['rent_amount'] = 1
        self.assertEqual(self.receive()['code'], 'confirmed_fields_mismatch')
        self.assertEqual(self.count(), 0)

    def test_same_version_changed_snapshot_requires_reconfirmation(self):
        self.receive()
        self.packet['request_id'] = 'new-snapshot'
        self.packet['review']['snapshot_revision'] = 2
        self.packet['review']['updated_at'] = '2026-10-17T18:30:00+11:00'
        self.packet['review']['status_reason'] = 'New same-version metadata'
        self.assertEqual(self.receive()['code'], 'review_snapshot_revision_mismatch')

    def test_conflicting_same_version_snapshot_does_not_replace_current(self):
        self.receive()
        self.packet['request_id'] = 'conflicting-snapshot'
        self.packet['review']['status_reason'] = 'Different at identical timestamp'
        self.assertEqual(self.receive()['code'], 'review_snapshot_conflict')

    def test_future_confirmation_or_before_review_blocks(self):
        for at in ('2026-10-18T19:00:00+11:00', '2026-10-16T10:00:00+11:00'):
            packet = deepcopy(self.packet)
            packet['confirmation']['confirmed_at'] = at
            # Separate requests because the invalid timestamps differ.
            packet['request_id'] = 'clock-' + at[:10]
            self.assertEqual(self.receive(packet)['code'], 'confirmation_time_invalid')
        self.assertEqual(self.count(), 0)

    def test_signed_date_uses_nsw_calendar_date_at_midnight(self):
        self.packet['review']['fields']['signed_date']['value'] = '2026-10-18'
        self.packet['review']['updated_at'] = '2026-10-18T00:10:00+11:00'
        self.reconfirm(self.packet)
        self.packet['confirmation']['confirmed_at'] = '2026-10-18T00:30:00+11:00'
        self.assertEqual(self.receive(as_of='2026-10-18T00:31:00+11:00')['status'], 'created')

    def test_unknown_facts_and_unsupported_type_are_not_defaulted(self):
        for key, value in (('jurisdiction', 'VIC'), ('tenancy_type', 'private_room')):
            packet = deepcopy(self.packet)
            packet['request_id'] = key
            packet['confirmation']['confirmed_fields'][key] = value
            self.assertEqual(self.receive(packet)['code'], 'unsupported_tenancy')
        self.packet['review']['fields']['address']['value'] = None
        self.packet['review']['snapshot_revision'] = 2
        self.packet['review']['updated_at'] = '2026-10-17T18:30:00+11:00'
        self.reconfirm(self.packet)
        self.assertEqual(self.receive()['code'], 'tenancy_fields_missing')
        self.assertEqual(self.count(), 0)

    def test_concurrent_delivery_different_request_ids_creates_one_case(self):
        packets = [deepcopy(self.packet) for _ in range(4)]
        for i, packet in enumerate(packets):
            packet['request_id'] = 'parallel:' + str(i)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(self.receive, packets))
        self.assertEqual(sum(r['newly_created'] for r in results), 1)
        self.assertEqual(len({r['tenancy_id'] for r in results}), 1)
        self.assertEqual(len({r['case_id'] for r in results}), 1)
        self.assertEqual(self.count(), 1)

    def test_concurrent_exact_retries_create_one_case(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(self.receive, [deepcopy(self.packet) for _ in range(4)]))
        self.assertEqual(sum(r['newly_created'] for r in results), 1)
        self.assertEqual(len({r['case_id'] for r in results}), 1)
        self.assertEqual(self.count('m3_receipts'), 1)

    def test_confirmation_source_is_immutable(self):
        self.receive()
        self.packet['request_id'] = 'changed-confirmation-source'
        self.packet['confirmation']['confirmed_at'] = '2026-10-17T19:00:30+11:00'
        self.error('confirmation_conflict', self.receive)

    def test_confirmation_version_cannot_roll_back(self):
        self.packet['confirmation']['confirmation_version'] = 2
        self.receive()
        self.packet['request_id'] = 'old-confirmation-version'
        self.packet['confirmation']['confirmation_version'] = 1
        self.assertEqual(self.receive()['code'], 'stale_confirmation')
        self.assertEqual(self.count(), 1)

    def test_human_release_does_not_substitute_actual_tenancy_confirmation(self):
        self.packet['review'] = human_fixture()
        review = self.packet['review']
        review['status'] = 'Reviewed'
        review['human_review'].update(status='approved', review_version=review['version'])
        self.packet['confirmation'] = None
        self.assertEqual(self.receive()['code'], 'confirmation_required')
        self.assertEqual(self.count(), 0)

    def test_malformed_human_finding_references_pause_without_crash(self):
        self.packet['review'] = human_fixture()
        self.packet['review']['status'] = 'Reviewed'
        self.packet['review']['human_review'].update(status='approved', review_version=1, finding_ids=None)
        self.reconfirm(self.packet)
        self.assertEqual(self.receive()['code'], 'review_blocked')
        self.assertEqual(self.count(), 0)

    def test_failure_in_mapping_insert_rolls_back_case_receipt_and_high_water(self):
        with closing(self.agent.connect()) as db:
            db.execute("CREATE TRIGGER fail_mapping BEFORE INSERT ON m3_handoffs BEGIN SELECT RAISE(ABORT, 'test'); END")
        self.error('storage_error', self.receive)
        for table in ('cases', 'receipts', 'm3_handoffs', 'm3_receipts', 'm3_reviews', 'm3_confirmations'):
            self.assertEqual(self.count(table), 0)

    def test_existing_tenancy_id_cannot_create_another_case(self):
        self.packet['confirmation']['tenancy_id'] = 'registered-tenancy'
        self.receive()
        self.packet['request_id'] = 'another:case'
        self.packet['context']['case_id'] = 'another-case'
        self.packet['confirmation']['case_id'] = 'another-case'
        self.packet['review']['review_id'] = 'cr-' + 'a' * 32
        self.reconfirm(self.packet)
        self.error('tenancy_conflict', self.receive)
        self.assertEqual(self.count(), 1)

    def test_move_out_is_separate_and_property_enrichment_keeps_m3_provenance(self):
        result = self.receive()
        command = self.command(result, 'create_plan', {'move_out_date': '2028-01-31', 'schedule_confirmed': False})
        self.error('move_out_confirmation_required', self.agent.submit, command)
        self.assertIsNone(self.agent.get(result['case_id'], TENANT)['plan'])
        tenancy = deepcopy(result['receipt']['case']['tenancy'])
        tenancy.update(rooms=[{'id': 'room', 'name': 'Synthetic room'}], carpeted=False, outdoor=False,
                       furnished=False, inventory=[], inventory_confirmed=True)
        enriched = self.agent.submit(self.command(result, 'revise_tenancy', {'tenancy': tenancy}, 'property-confirmed'))
        self.assertEqual(enriched['case']['tenancy']['source_version'], 1)
        plan = self.agent.submit(self.command(result, 'create_plan', {'move_out_date': '2028-02-02', 'schedule_confirmed': True}, 'date-confirmed'))
        self.assertEqual(plan['case']['plan']['move_out_date'], '2028-02-02')
        self.assertEqual(plan['case']['plan']['state'], 'Active')
        self.assertIsNone(plan['case']['bond'])

    def test_property_revision_cannot_replace_confirmed_contract_source(self):
        result = self.receive()
        tenancy = deepcopy(result['receipt']['case']['tenancy'])
        tenancy['address'] = 'silently changed'
        self.error('handoff_source_immutable', self.agent.submit,
                   self.command(result, 'revise_tenancy', {'tenancy': tenancy}))

    def test_unknown_keys_missing_required_fields_and_invalid_review_are_rejected(self):
        self.packet['confirmation']['untrusted_override'] = True
        self.error('invalid_input', self.receive)
        del self.packet['confirmation']['untrusted_override']
        del self.packet['confirmation']['review_sha256']
        self.error('invalid_input', self.receive)
        self.packet = load_json(FIXTURES / 'normal-confirmation-stub-packet.json')
        self.packet['review']['intake']['selection_sha256'] = '0' * 64
        self.error('invalid_review', self.receive)

    def test_handoff_snapshot_read_requires_owner(self):
        result = self.receive()
        self.error('access_denied', self.agent.get_handoff, result['case_id'], 'another-tenant')

    def high_water(self):
        with closing(self.agent.connect()) as db:
            return db.execute('SELECT version,snapshot_revision,fingerprint FROM m3_reviews WHERE review_id=?',
                              (self.packet['review']['review_id'],)).fetchone()

    def test_real_m3_human_approval_in_same_second_with_explicit_sequence_double(self):
        from agent3.contract_agent.document import load_document
        m3 = importlib.import_module('agent3.contract_agent.review')
        agreement = Path(self.tmp.name) / 'risk.txt'
        text = (ROOT.parent / 'agent3/data/demo/agreements/selection-demo.txt').read_text(encoding='utf-8')
        agreement.write_text(text.replace('Bond: $2000', 'Bond: $2500'), encoding='utf-8')
        with patch.object(m3, '_now', return_value='2026-10-17T18:00:00+11:00'):
            pending = m3.review_agreement(load_document(agreement, consent=True), consent=True,
                                          selection=self.packet['review']['selection_evidence'], as_of='2026-10-15')
            approved = m3.approve_review(pending, reviewer='DEMO-OPERATOR', decision='approve', note='Synthetic test')
        self.assertEqual(pending['updated_at'], approved['updated_at'])
        self.assertEqual(pending['version'], approved['version'])
        # Explicit persistence double; M4 never assigns these sequence numbers.
        pending['snapshot_revision'], approved['snapshot_revision'] = 1, 2
        packet = deepcopy(self.packet)
        packet.update(request_id='pending', review=pending, confirmation=None)
        self.assertEqual(self.receive(packet)['code'], 'review_blocked')
        self.packet.update(request_id='approved', review=approved)
        self.reconfirm(self.packet)
        result = self.receive()
        self.assertEqual(result['status'], 'created')
        self.assertEqual(result['review_snapshot_revision'], 2)
        self.assertEqual(self.high_water()[:2], (1, 2))
        self.assertEqual(self.receive(packet)['code'], 'stale_snapshot')
        self.assertEqual(self.count(), 1)

    def test_same_sequence_conflict_even_with_later_time_does_not_replace_baseline(self):
        self.receive()
        baseline = self.high_water()
        self.packet['request_id'] = 'later-conflict'
        self.packet['review']['updated_at'] = '2026-10-17T18:30:00+11:00'
        self.reconfirm(self.packet)
        self.assertEqual(self.receive()['code'], 'review_snapshot_conflict')
        self.assertEqual(self.high_water(), baseline)

    def test_sequence_not_wall_clock_orders_snapshots_and_survives_restart(self):
        self.packet['confirmation'] = None
        self.assertEqual(self.receive()['code'], 'confirmation_required')
        later = deepcopy(self.packet)
        later['request_id'] = 'newer-sequence-earlier-wall-clock'
        later['review'].update(snapshot_revision=2, updated_at='2026-10-17T17:00:00+11:00')
        self.assertEqual(self.receive(later)['code'], 'confirmation_required')
        self.agent = AftercareAgent(self.database)
        self.assertEqual(self.high_water()[:2], (1, 2))
        old = deepcopy(self.packet)
        old['request_id'] = 'older-sequence-later-clock'
        old['review']['updated_at'] = '2026-10-17T19:00:00+11:00'
        self.assertEqual(self.receive(old)['code'], 'stale_snapshot')
        self.assertEqual(self.high_water()[:2], (1, 2))

    def test_newer_blocked_snapshot_invalidates_success_receipt_and_plan(self):
        created = self.receive()
        newer = deepcopy(self.packet)
        newer['request_id'] = 'new-questions'
        newer['review'].update(snapshot_revision=2, status='Questions Ready')
        self.assertEqual(self.receive(newer)['code'], 'review_blocked')
        self.assertEqual(self.receive()['code'], 'stale_snapshot')
        self.error('handoff_review_stale', self.agent.submit,
                   self.command(created, 'create_plan', {'move_out_date': '2028-02-02', 'schedule_confirmed': True}))
        self.assertEqual(self.count(), 1)

    def test_confirmation_sequence_must_equal_review_sequence(self):
        self.packet['confirmation']['review_snapshot_revision'] = 2
        self.assertEqual(self.receive()['code'], 'review_snapshot_revision_mismatch')
        self.assertEqual(self.count(), 0)

    def test_sequence_is_inside_full_snapshot_fingerprint(self):
        self.packet['review']['snapshot_revision'] = 2
        self.packet['confirmation']['review_snapshot_revision'] = 2
        self.assertEqual(self.receive()['code'], 'review_fingerprint_mismatch')
        self.assertEqual(self.count(), 0)

    def test_missing_invalid_or_fabricated_sequence_is_rejected_without_state(self):
        for container, field in (('review', 'snapshot_revision'), ('confirmation', 'review_snapshot_revision')):
            for value in (None, True, 0, -1, '1', 1.0, 9223372036854775808):
                with self.subTest(container=container, value=value):
                    packet = deepcopy(self.packet)
                    if value is None:
                        del packet[container][field]
                    else:
                        packet[container][field] = value
                    with self.assertRaises(AftercareError):
                        self.receive(packet)
        self.assertEqual(self.count('m3_reviews'), 0)
        self.assertEqual(self.count('m3_receipts'), 0)

    def test_compatibility_validator_rejects_unrecognized_review_extensions(self):
        self.packet['review']['untrusted_extension'] = True
        self.error('invalid_review', self.receive)

    def test_contract_version_cannot_reset_sequence_or_regress(self):
        self.packet['confirmation'] = None
        self.packet['review'].update(version=2, snapshot_revision=3)
        self.receive()
        for version, sequence, expected in ((3, 1, 'stale_snapshot'), (3, 3, 'review_snapshot_conflict'), (1, 4, 'review_version_regression')):
            packet = deepcopy(self.packet)
            packet['request_id'] = f'regression-{version}-{sequence}'
            packet['review'].update(version=version, snapshot_revision=sequence)
            self.assertEqual(self.receive(packet)['code'], expected)
            self.assertEqual(self.high_water()[:2], (2, 3))

    def test_reads_exports_and_duplicate_delivery_do_not_change_sequence(self):
        from aftercare_agent.report import export_case
        first = self.receive()
        original = self.high_water()
        self.agent.get_handoff(first['case_id'], TENANT)
        export_case(self.agent.get(first['case_id'], TENANT), Path(self.tmp.name) / 'read-export')
        self.assertEqual(self.receive()['status'], 'duplicate')
        self.packet['request_id'] = 'another-delivery'
        self.assertEqual(self.receive()['status'], 'duplicate')
        self.assertEqual(self.high_water(), original)

    def test_racing_newer_snapshots_never_reduce_high_water(self):
        packets = [deepcopy(self.packet) for _ in range(3)]
        for sequence, packet in enumerate(packets, 1):
            packet['request_id'] = 'parallel-snapshot-' + str(sequence)
            packet['review']['snapshot_revision'] = sequence
            packet['confirmation'] = None
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(self.receive, packets))
        self.assertTrue(all(r['status'] == 'paused' for r in results))
        self.assertEqual(self.high_water()[:2], (1, 3))
        self.assertEqual(self.count(), 0)

    def test_legacy_database_migration_preserves_history_and_never_invents_baseline(self):
        import sqlite3
        legacy = Path(self.tmp.name) / 'legacy.sqlite3'
        with closing(sqlite3.connect(legacy)) as db:
            db.execute('CREATE TABLE m3_reviews (review_id TEXT PRIMARY KEY, tenant_id TEXT, upstream_case_id TEXT, version INTEGER, fingerprint TEXT, updated_at TEXT)')
            raw = deepcopy(self.packet['review'])
            del raw['snapshot_revision']
            db.execute('INSERT INTO m3_reviews VALUES(?,?,?,?,?,?)', (raw['review_id'], TENANT,
                       self.packet['context']['case_id'], raw['version'], fingerprint(raw), raw['updated_at']))
            db.commit()
        self.agent = AftercareAgent(legacy)
        result = self.receive()
        self.assertEqual(result['code'], 'snapshot_migration_required')
        self.assertEqual(self.high_water(), (raw['version'], None, fingerprint(raw)))
        self.assertEqual(self.count(), 0)

    def test_cli_exports_paused_json_and_markdown_without_overwrite(self):
        prefix = Path(self.tmp.name) / 'missing'
        command = [sys.executable, '-m', 'aftercare_agent', 'receive', '--packet',
                   str(FIXTURES / 'missing-confirmation-packet.json'), '--store', str(self.database),
                   '--actor-id', TENANT, '--as-of', NOW, '--output', str(prefix)]
        env = {**os.environ, 'PYTHONPATH': str(ROOT), 'PYTHONIOENCODING': 'utf-8'}
        run = subprocess.run(command, cwd=ROOT.parent, env=env, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(run.returncode, 3, run.stderr)
        self.assertEqual(load_json(str(prefix) + '.json')['response']['code'], 'confirmation_required')
        self.assertIn('M3', Path(str(prefix) + '.md').read_text(encoding='utf-8'))
        repeated = subprocess.run(command, cwd=ROOT.parent, env=env, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(repeated.returncode, 2)
        self.assertIn('output_exists', repeated.stderr)


if __name__ == '__main__':
    unittest.main()
