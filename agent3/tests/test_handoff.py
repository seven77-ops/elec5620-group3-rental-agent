import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_agent.errors import ContractError
from contract_agent.handoff import validate_selection

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "demo" / "selected-listing-evidence.json"


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(SAMPLE.read_text(encoding="utf-8"))

    def test_actual_agent2_packet_is_accepted(self):
        self.assertEqual(validate_selection(self.packet)["listing_id"], "DEMO-006")

    def test_bundled_contract_matches_sibling_agent2_when_present(self):
        upstream = ROOT.parent / "agent2"
        if not upstream.exists():
            self.skipTest("Agent 2 is not installed beside this standalone Agent 3 package")
        self.assertEqual((ROOT / "schemas" / "selected-listing-evidence.schema.json").read_bytes(),
                         (upstream / "schemas" / "selected-listing-evidence.schema.json").read_bytes())
        packet = json.loads((upstream / "reports" / "selection.selection.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_selection(packet)["listing_id"], "DEMO-006")

    def test_selection_must_be_confirmed_and_eligible(self):
        changed = copy.deepcopy(self.packet)
        changed["user_confirmed"] = False
        with self.assertRaises(ContractError):
            validate_selection(changed)
        changed = copy.deepcopy(self.packet)
        changed["assessment"]["status"] = "pending"
        with self.assertRaises(ContractError):
            validate_selection(changed)

    def test_mismatched_identity_is_rejected(self):
        changed = copy.deepcopy(self.packet)
        changed["listing_snapshot"]["listing_id"] = "DEMO-OTHER"
        with self.assertRaises(ContractError):
            validate_selection(changed)

    def test_profile_fingerprint_and_snapshot_must_be_consistent(self):
        changed = copy.deepcopy(self.packet)
        changed["profile"]["profile_version"] += 1
        changed["profile_version"] += 1
        with self.assertRaisesRegex(ContractError, "fingerprint"):
            validate_selection(changed)
        changed = copy.deepcopy(self.packet)
        changed["listing_snapshot"]["rent_amount"] += 1
        with self.assertRaisesRegex(ContractError, "source records"):
            validate_selection(changed)
