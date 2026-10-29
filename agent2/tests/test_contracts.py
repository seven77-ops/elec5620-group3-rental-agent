import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

from rental_agent.engine import evaluate
from rental_agent.validation import ValidationError
from test_engine import ROOT, dataset, listing, profile


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'rental_agent/contracts.py').exists(), '交接契约尚未实现')
        from rental_agent.contracts import validate_contract
        self.validate = validate_contract

    def test_schemas_are_valid_and_self_contained(self):
        for name in ['rental-profile', 'recommendation-report', 'selected-listing-evidence']:
            schema = json.loads((ROOT / f'schemas/{name}.schema.json').read_text(encoding='utf-8'))
            Draft202012Validator.check_schema(schema)
            self.assertNotIn('https://example', json.dumps(schema))

    def test_saved_contract_examples_validate(self):
        for name in ['commute', 'budget', 'housing']:
            self.validate('RentalProfile', json.loads((ROOT / f'data/demo/profiles/{name}.json').read_text(encoding='utf-8')))
        for name in ['commute', 'budget', 'housing', 'comparison', 'selection']:
            self.validate('RecommendationReport', json.loads((ROOT / f'reports/{name}.json').read_text(encoding='utf-8')))
        packet = json.loads((ROOT / 'reports/selection.selection.json').read_text(encoding='utf-8'))
        self.validate('SelectedListingEvidence', packet)
        from rental_agent.handoff import build_selected_listing_evidence
        report = json.loads((ROOT / 'reports/selection.json').read_text(encoding='utf-8'))
        data = json.loads((ROOT / 'data/demo/listings.json').read_text(encoding='utf-8'))
        self.assertEqual(packet, build_selected_listing_evidence(report, data, packet['listing_id'],
                         selected_at=packet['selected_at'], user_confirmed=True))

    def test_profile_and_report_validate(self):
        self.validate('RentalProfile', profile())
        self.validate('RecommendationReport', evaluate(profile(), dataset(listing())))

    def test_missing_unknown_fields_types_and_version_rejected(self):
        for change in [{'profile_version': True}, {'schema_version': '9.0'}, {'unexpected': 42}]:
            p = {**profile(), **change}
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.validate('RentalProfile', p)
        p = profile()
        del p['destination_id']
        with self.assertRaises(ValidationError):
            self.validate('RentalProfile', p)
        with self.assertRaises(ValidationError):
            self.validate('NotAContract', {})

    def test_report_run_id_is_stable_and_input_sensitive(self):
        data = dataset(listing())
        baseline = evaluate(profile(), data)
        identifier = baseline['recommendation_run_id']
        self.assertRegex(identifier, r'^rr-[0-9a-f]{64}$')
        self.assertEqual(identifier, evaluate(profile(), copy.deepcopy(data))['recommendation_run_id'])
        p = profile()
        p['weights']['cost'] = 0.6
        for alternative in [evaluate(p, data), evaluate(profile(), dataset(listing(rent_amount=510))),
                            evaluate(profile(), data, as_of='2026-09-17T10:00:00+10:00')]:
            self.assertNotEqual(identifier, alternative['recommendation_run_id'])

    def test_report_missing_id_and_invalid_item_rejected(self):
        report = evaluate(profile(), dataset(listing()))
        del report['recommendation_run_id']
        with self.assertRaises(ValidationError):
            self.validate('RecommendationReport', report)
        report = evaluate(profile(), dataset(listing()))
        report['recommendations'][0]['score'] = None
        with self.assertRaises(ValidationError):
            self.validate('RecommendationReport', report)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'rental_agent/handoff.py').exists(), '选房证据交接尚未实现')
        from rental_agent.handoff import build_selected_listing_evidence
        from rental_agent.contracts import validate_contract
        self.build, self.validate = build_selected_listing_evidence, validate_contract
        self.data = dataset(listing(), listing('B', bills_included=None), listing('C', rent_amount=900))
        self.report = evaluate(profile(), self.data)

    def select(self, identifier='A', **overrides):
        args = {'selected_at': '2026-09-17T10:00:00+10:00', 'user_confirmed': True}
        args.update(overrides)
        return self.build(self.report, self.data, identifier, **args)

    def test_explicit_selection_contains_traceable_snapshot(self):
        original = copy.deepcopy((self.report, self.data))
        result = self.select()
        self.validate('SelectedListingEvidence', result)
        self.assertEqual(result['recommendation_run_id'], self.report['recommendation_run_id'])
        self.assertEqual(result['listing_id'], 'A')
        self.assertEqual(result['recipient'], 'ContractAgent')
        self.assertEqual(result['handoff_status'], 'prepared_not_sent')
        self.assertEqual(result['listing_snapshot']['rent_amount'], 520)
        self.assertEqual(result['assessment']['weekly_cost'], 520)
        self.assertTrue(result['assessment']['evidence_refs'])
        result['listing_snapshot']['rent_amount'] = 1
        self.assertEqual((self.report, self.data), original)

    def test_selection_rejects_pending_excluded_unknown_and_unconfirmed(self):
        for identifier in ['B', 'C', 'missing']:
            with self.subTest(identifier=identifier), self.assertRaises(ValidationError):
                self.select(identifier)
        for value in [False, None, 'yes', 1]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.select(user_confirmed=value)

    def test_selection_rejects_tampered_report_or_mismatched_dataset(self):
        for field in ['recommendation_run_id', 'profile_fingerprint']:
            changed = copy.deepcopy(self.report)
            changed[field] = ('rr-' if field.endswith('id') else '') + '0' * 64
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.build(changed, self.data, 'A', selected_at=self.data['as_of'], user_confirmed=True)
        changed = copy.deepcopy(self.report)
        changed['eligible'][0]['score'] = 99
        with self.assertRaises(ValidationError):
            self.build(changed, self.data, 'A', selected_at=self.data['as_of'], user_confirmed=True)
        changed_data = dataset(listing(rent_amount=500))
        with self.assertRaises(ValidationError):
            self.build(self.report, changed_data, 'A', selected_at=self.data['as_of'], user_confirmed=True)

    def test_selection_rejects_stale_or_past_time(self):
        for value in ['2026-09-17T08:00:00+10:00', '2026-09-20T09:00:00+10:00']:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.select(selected_at=value)

    def test_selection_checks_comparison_destination_link(self):
        from rental_agent.report import compare_reports
        self.report['comparison'] = compare_reports(self.report, self.report)
        self.report['comparison']['after_run_id'] = 'rr-' + '0' * 64
        with self.assertRaises(ValidationError):
            self.select()

    def test_comparison_history_is_not_exported_as_selected_evidence(self):
        from rental_agent.report import compare_reports
        self.report['comparison'] = compare_reports(self.report, self.report)
        self.report['comparison']['before_run_id'] = 'rr-' + '0' * 64
        packet = self.select()
        self.assertNotIn('comparison', packet)
        self.assertEqual(packet['assessment']['score'], 88.6)

    def test_cli_explicit_selection_and_pair_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = str(Path(temp) / 'selection')
            args = [sys.executable, '-m', 'rental_agent', '--profile', 'data/demo/profiles/commute.json',
                    '--listings', 'data/demo/listings.json', '--output', prefix, '--select-listing', 'DEMO-006']
            missing = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertFalse(Path(prefix + '.json').exists())
            done = subprocess.run(args + ['--selected-at', '2026-09-17T10:00:00+10:00'], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            result = json.loads(Path(prefix + '.selection.json').read_text(encoding='utf-8'))
            self.validate('SelectedListingEvidence', result)


if __name__ == '__main__':
    unittest.main()
