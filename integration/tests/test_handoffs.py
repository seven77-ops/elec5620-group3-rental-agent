"""Repository-level synthetic CLI handoffs; never call a model or real service."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'integration' / 'agent1-to-agent2'
sys.path.insert(0, str(ROOT / 'agent2'))

from rental_agent.contracts import validate_contract
from rental_agent.engine import fingerprint


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


class HandoffIntegrationTests(unittest.TestCase):
    def command(self, agent, *args):
        module = 'rental_agent' if agent == 'agent2' else 'contract_agent'
        return subprocess.run([sys.executable, '-m', module, *map(str, args)],
                              cwd=ROOT / agent, capture_output=True, text=True)

    def test_agent3_readme_directory_runs(self):
        result = self.command('agent3', '--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('receive', result.stdout)

    def test_agent1_example_keeps_confirmation_outside_profile(self):
        envelope = load(FIXTURES / 'handoff.json')
        profile = load(FIXTURES / envelope['profileFile'])
        validate_contract('RentalProfile', profile)
        self.assertTrue(envelope['exampleOnly'])
        self.assertEqual(envelope['dataMode'], 'synthetic_demo')
        self.assertNotEqual(envelope['caseId'], envelope['searchId'])
        self.assertEqual(envelope['searchId'], profile['search_id'])
        self.assertEqual(envelope['profileVersion'], profile['profile_version'])
        self.assertEqual(envelope['profileFingerprint'], fingerprint(profile))
        self.assertIs(envelope['confirmation']['confirmed'], True)
        self.assertEqual(envelope['confirmation']['reviewedDraftRevision'], 3)
        self.assertNotIn('confirmation', profile)
        self.assertNotIn('taskId', profile)
        self.assertNotIn('caseId', profile)

    def generate(self, directory):
        expected = load(FIXTURES / 'expected.json')
        prefix = directory / 'selection'
        result = self.command('agent2', '--profile', FIXTURES / 'confirmed-profile.json',
                              '--listings', ROOT / 'agent2/data/demo/listings.json',
                              '--select-listing', 'DEMO-006', '--selected-at', expected['selectedAt'],
                              '--output', prefix)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = load(directory / 'selection.json')
        packet = load(directory / 'selection.selection.json')
        self.assertEqual(report['counts'], expected['counts'])
        self.assertEqual(report['recommendations'][0]['listing_id'], expected['top1']['listing_id'])
        self.assertEqual(report['recommendations'][0]['score'], expected['top1']['score'])
        self.assertEqual(report['profile'], load(FIXTURES / 'confirmed-profile.json'))
        validate_contract('SelectedListingEvidence', packet)
        self.assertEqual(packet['handoff_status'], 'prepared_not_sent')
        return directory / 'selection.selection.json', packet

    def receive(self, directory, selection, *, request='integration-receive-001',
                agreement=None, output='review', consent=True):
        args = ['receive', '--agreement', agreement or ROOT / 'agent3/data/demo/agreements/selection-demo.txt',
                '--selection', selection, '--request-id', request,
                '--as-of', load(FIXTURES / 'expected.json')['contractReferenceDate'],
                '--store', directory / 'receipts.sqlite3', '--output', directory / output]
        if consent:
            args.append('--consent')
        return self.command('agent3', *args)

    def test_fresh_agent2_packet_is_received_and_replayed(self):
        schema2 = ROOT / 'agent2/schemas/selected-listing-evidence.schema.json'
        schema3 = ROOT / 'agent3/schemas/selected-listing-evidence.schema.json'
        self.assertEqual(schema2.read_bytes(), schema3.read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path, packet = self.generate(directory)
            result = self.receive(directory, path)
            self.assertEqual(result.returncode, 0, result.stderr)
            review = load(directory / 'review.json')
            self.assertEqual(review['status'], 'Reviewed')
            self.assertEqual(review['mode'], 'rules')
            self.assertEqual(review['selection_evidence'], packet)
            for key in ['recommendation_run_id', 'selection_check_run_id', 'search_id',
                        'profile_version', 'listing_id', 'selected_at']:
                self.assertEqual(review['intake'][key], packet[key])
            digest = hashlib.sha256(json.dumps(packet, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            self.assertEqual(review['intake']['selection_sha256'], digest)
            result = self.receive(directory, path, output='retry')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('duplicate request', result.stdout)
            self.assertEqual(load(directory / 'retry.json'), review)

    def test_no_consent_rejects_before_receipt_or_review_is_written(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path, _ = self.generate(directory)
            result = self.receive(directory, path, consent=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stderr)['error']['code'], 'invalid_request')
            self.assertFalse((directory / 'receipts.sqlite3').exists())
            self.assertFalse((directory / 'review.json').exists())

    def test_listing_contract_conflict_waits_for_human_and_blocks_questions(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path, _ = self.generate(directory)
            original = ROOT / 'agent3/data/demo/agreements/selection-demo.txt'
            agreement = directory / 'conflict.txt'
            agreement.write_text(original.read_text(encoding='utf-8').replace(
                'Weekly rent: $500 per person', 'Weekly rent: $650 per person'), encoding='utf-8')
            result = self.receive(directory, path, agreement=agreement)
            self.assertEqual(result.returncode, 0, result.stderr)
            review = load(directory / 'review.json')
            self.assertEqual(review['status'], 'Awaiting Human Review')
            self.assertIn('rent_difference', [f['code'] for f in review['findings']])
            result = self.command('agent3', 'questions', '--review', directory / 'review.json',
                                  '--output', directory / 'questions')
            self.assertEqual(result.returncode, 2)
            self.assertFalse((directory / 'questions.questions.json').exists())

    def test_changed_contract_cannot_reuse_request_id(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path, _ = self.generate(directory)
            first = self.receive(directory, path)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = (directory / 'review.json').read_bytes()
            changed = directory / 'changed.txt'
            changed.write_text((ROOT / 'agent3/data/demo/agreements/selection-demo.txt').read_text(
                encoding='utf-8') + '\nSynthetic additional clause.', encoding='utf-8')
            result = self.receive(directory, path, agreement=changed, output='changed-review')
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stderr)['error']['code'], 'duplicate_request_conflict')
            self.assertFalse((directory / 'changed-review.json').exists())
            self.assertEqual((directory / 'review.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
