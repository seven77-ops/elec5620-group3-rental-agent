import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_agent.document import load_document
from contract_agent.errors import ContractError
from contract_agent.review import approve_review, correct_review, generate_questions, review_agreement

ROOT = Path(__file__).resolve().parents[1]
PACKET = json.loads((ROOT / "data" / "demo" / "selected-listing-evidence.json").read_text(encoding="utf-8"))
AGREEMENTS = ROOT / "data" / "demo" / "agreements"


def reviewed(name="selection-demo.txt", selection=PACKET, **kwargs):
    document = load_document(AGREEMENTS / name, consent=True)
    return review_agreement(document, consent=True, selection=selection, as_of="2026-10-15", **kwargs)


class ReviewTests(unittest.TestCase):
    def test_consent_before_document_read(self):
        with self.assertRaises(ContractError):
            load_document(AGREEMENTS / "selection-demo.txt", consent=False)

    def test_agent2_selection_and_evidence(self):
        result = reviewed()
        self.assertEqual(result["status"], "Reviewed")
        self.assertEqual(result["fields"]["rent_scope"]["value"], "per_person")
        self.assertEqual(result["selection_evidence"]["listing_id"], "DEMO-006")
        self.assertTrue(result["fields"]["address"]["evidence"]["line"])
        self.assertFalse(any(f["code"] == "rent_difference" for f in result["findings"]))

    def test_high_risk_blocks_questions_until_human_decision(self):
        result = reviewed("risk-demo.txt")
        self.assertEqual(result["status"], "Awaiting Human Review")
        self.assertIn("bond_over_four_weeks", {f["code"] for f in result["findings"]})
        with self.assertRaises(ContractError):
            generate_questions(result)
        approved = approve_review(result, reviewer="Tutor Operator", decision="approve", note="Escalation explained to tenant")
        self.assertEqual(approved["status"], "Reviewed")
        questions = generate_questions(approved)
        self.assertEqual(questions["status"], "Questions Ready")
        self.assertTrue(all(q["finding_id"] in {f["id"] for f in questions["findings"]} for q in questions["questions"]))

    def test_correction_creates_revision_and_invalidates_questions(self):
        result = reviewed("risk-demo.txt")
        result = approve_review(result, reviewer="Tutor Operator", decision="approve", note="Discussed discrepancy")
        result = generate_questions(result)
        corrected = correct_review(result, {"bond": 2000, "address": PACKET["listing_snapshot"]["address"]})
        self.assertEqual(corrected["version"], 2)
        self.assertEqual(corrected["revisions"][0]["version"], 1)
        self.assertEqual(corrected["questions"], [])
        self.assertEqual(corrected["status"], "Reviewed")
        self.assertEqual(corrected["fields"]["bond"]["evidence"]["source_name"], "tenant correction")

    def test_rent_scope_mismatch_is_not_a_numeric_mismatch(self):
        selected = copy.deepcopy(PACKET)
        selected["listing_snapshot"]["rent_scope"] = "whole_property"
        for source in selected["source_records"]:
            if source["listing_id"] == selected["listing_id"]:
                source["rent_scope"] = "whole_property"
        result = reviewed(selection=selected)
        codes = {f["code"] for f in result["findings"]}
        self.assertIn("rent_not_comparable", codes)
        self.assertNotIn("rent_difference", codes)

    def test_listing_rent_conflict_requires_human_review(self):
        selected = copy.deepcopy(PACKET)
        selected["listing_snapshot"]["rent_amount"] = 480
        for source in selected["source_records"]:
            if source["listing_id"] == selected["listing_id"]:
                source["rent_amount"] = 480
        result = reviewed(selection=selected)
        self.assertEqual(result["status"], "Awaiting Human Review")
        self.assertIn("rent_difference", {f["code"] for f in result["findings"]})
        with self.assertRaises(ContractError):
            generate_questions(result)

    def test_building_precision_address_difference_requires_human_review(self):
        document = load_document(AGREEMENTS / "selection-demo.txt", consent=True)
        document["text"] = document["text"].replace(
            PACKET["listing_snapshot"]["address"], "Another fictional building")
        result = review_agreement(document, consent=True, selection=PACKET, as_of="2026-10-15")
        self.assertEqual(result["status"], "Awaiting Human Review")
        self.assertIn("address_difference", {f["code"] for f in result["findings"]})

    def test_recheck_extends_rule_pack_window_from_latest_check(self):
        from contract_agent.rules import rule_pack_current
        self.assertTrue(rule_pack_current("2026-11-20"))
        self.assertTrue(rule_pack_current("2026-11-28"))
        self.assertFalse(rule_pack_current("2026-11-29"))
        self.assertFalse(rule_pack_current("2026-10-14"))

    def test_stale_rule_pack_suspends_conclusions(self):
        result = review_agreement(load_document(AGREEMENTS / "risk-demo.txt", consent=True), consent=True,
                                  as_of="2027-01-01", selection=PACKET)
        self.assertEqual(result["status"], "Degraded Summary Only")
        self.assertEqual(result["findings"], [])
        with self.assertRaises(ContractError):
            generate_questions(result)

    def test_model_failure_retries_once_then_uses_rule_explanation(self):
        calls = []
        def bad_gateway(context):
            calls.append(context)
            return {"explanations": [{"finding_id": "made-up", "text": "unsupported"}]}
        result = reviewed("risk-demo.txt", gateway=bad_gateway, allow_external_ai=True)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["mode"], "rules_fallback")

    def test_no_listing_still_reviews(self):
        result = reviewed(selection=None)
        self.assertEqual(result["status"], "Reviewed")
        self.assertIsNone(result["selection_evidence"])

    def test_missing_fields_requests_resubmission(self):
        document = {"source_name": "thin.txt", "text": "[page 1]\nThis document is not a readable labelled tenancy agreement.",
                    "sha256": "0" * 64, "format": "txt", "page_count": 1, "extraction_mode": "text"}
        result = review_agreement(document, consent=True, as_of="2026-10-15")
        self.assertEqual(result["status"], "Awaiting Resubmission")

    def test_edited_questions_preserve_finding_ids(self):
        result = reviewed("risk-demo.txt")
        result = approve_review(result, reviewer="Operator", decision="approve", note="Reviewed")
        questions = generate_questions(result)
        edits = [{"finding_id": q["finding_id"], "text": "Please clarify " + q["finding_id"]}
                 for q in questions["questions"]]
        updated = generate_questions(questions, edits=edits)
        self.assertEqual([q["text"] for q in updated["questions"]], [e["text"] for e in edits])
