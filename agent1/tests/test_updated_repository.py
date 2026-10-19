"""Verify the new integration envelope against the supplied team repository."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preference_agent.bridge import AGENT2, evaluate, fingerprint, validate_contract
from preference_agent.cli import export_case
from preference_agent.fields import flatten
from preference_agent.handover import HandoverService, coordination_envelope
from preference_agent.llm import ManualOnly
from preference_agent.service import PreferenceAgent
from preference_agent.store import Store


class UpdatedRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'state.sqlite3')
        self.agent = PreferenceAgent(self.store, ManualOnly())
        self.case = self.agent.startCollection()['case_id']
        self.data = json.loads((AGENT2 / 'data/demo/listings.json').read_text(encoding="utf-8-sig"))
        profile = json.loads((AGENT2 / 'data/demo/profiles/commute.json').read_text(encoding="utf-8-sig"))
        self.agent.setFields(self.case, flatten(profile))
        token = self.agent.reviewDraft(self.case)['confirmation_token']
        self.record = self.agent.confirmProfile(self.case, token, 'SYNTHETIC_TEST_ACTOR')

    def test_export_matches_team_envelope_and_actual_agent2(self):
        task = HandoverService(self.store).submitConfirmed(self.case, self.data)
        directory = Path(self.temp.name) / 'export'
        export_case(self.store, self.case, directory)
        envelope = json.loads((directory / 'handoff.json').read_text(encoding="utf-8-sig"))
        fixture = json.loads((AGENT2.parent / 'integration/agent1-to-agent2/handoff.json').read_text(encoding="utf-8-sig"))
        self.assertEqual(set(envelope), set(fixture))
        self.assertEqual(set(envelope['confirmation']), set(fixture['confirmation']))
        profile_path = (directory / envelope['profileFile']).resolve()
        self.assertEqual(profile_path.parent, directory.resolve())
        profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
        validate_contract('RentalProfile', profile)
        self.assertNotEqual(envelope['caseId'], envelope['searchId'])
        self.assertEqual(envelope['searchId'], profile['search_id'])
        self.assertEqual(envelope['profileVersion'], profile['profile_version'])
        self.assertEqual(envelope['profileFingerprint'], fingerprint(profile))
        self.assertEqual(envelope['taskId'], task['task_id'])
        self.assertTrue(envelope['confirmation']['confirmed'])
        self.assertEqual(evaluate(profile, self.data), task['report'])
        self.assertNotIn('confirmation', profile)

    def test_export_before_search_has_no_fabricated_handoff(self):
        directory = Path(self.temp.name) / 'export'
        export_case(self.store, self.case, directory)
        self.assertTrue((directory / 'confirmation.json').is_file())
        self.assertFalse((directory / 'handoff.json').exists())

    def test_mismatched_task_cannot_be_exported_as_valid_envelope(self):
        original = HandoverService(self.store).submitConfirmed(self.case, self.data)
        for field, value in [('case_id', 'other'), ('search_id', 'other'), ('version', 99),
                             ('profile_hash', 'invalid'), ('task_id', '')]:
            with self.subTest(field=field):
                task = deepcopy(original)
                task[field] = value
                with self.assertRaises(ValueError):
                    coordination_envelope(self.record, task)


if __name__ == '__main__':
    unittest.main()
