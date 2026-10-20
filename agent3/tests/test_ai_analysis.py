import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contract_agent.ai_analysis import analyze_contract as analyze
from contract_agent.document import load_document
from contract_agent.review import correct_review, review_agreement

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("address", "rent_amount", "start_date", "end_date", "rent_period", "rent_scope", "currency")


def baseline(name="selection-demo.txt"):
    document = load_document(ROOT / "data" / "demo" / "agreements" / name, consent=True)
    return document, review_agreement(document, consent=True, as_of="2026-10-15")


def candidate(field, value, line, quote):
    return {"field": field, "value": value, "line": line, "quote": quote}


class Gateway:
    def __init__(self, fields, explanations=None):
        self.fields, self.explanations, self.calls = fields, explanations, []

    def __call__(self, context):
        self.calls.append(copy.deepcopy(context))
        if context["task"] == "contract_extract":
            return {"fields": self.fields}
        if isinstance(self.explanations, Exception):
            raise self.explanations
        if self.explanations is not None:
            return self.explanations
        return {"explanations": [{"finding_id": finding["id"], "text": "Please verify: " + finding["reason"]}
                                 for finding in context["findings"]]}


class AiAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.document, self.review = baseline()

    def run_fields(self, fields, **kwargs):
        gateway = Gateway(fields, **kwargs)
        return analyze(self.document, self.review, gateway), gateway

    def test_free_text_fields_have_derived_page_and_exact_raw_evidence(self):
        lines = ["[page 1]", "Agreement narrative.", "[page 3]",
                 "  Alex rents 12 Example Street for AUD $1,250.50 per fortnight per room.  ",
                 "The term runs from 2027-02-01 until 2028-01-31."]
        self.document["text"] = "\n".join(lines)
        rows = [candidate("address", "12 Example Street", 4, lines[3]),
                candidate("rent_amount", 1250.50, 4, lines[3]),
                candidate("rent_period", "fortnight", 4, lines[3]),
                candidate("rent_scope", "per_room", 4, lines[3]),
                candidate("currency", "AUD", 4, lines[3]),
                candidate("start_date", "2027-02-01", 5, lines[4]),
                candidate("end_date", "2028-01-31", 5, lines[4])]
        rows[0].update(source_name="model-forged.txt", page=999)
        result, gateway = self.run_fields(rows)
        self.assertEqual({row["field"] for row in result["candidates"]}, set(FIELDS))
        self.assertTrue(all(row["valid"] for row in result["candidates"]))
        self.assertEqual(result["candidates"][0]["evidence"],
                         {"source_name": self.document["source_name"], "page": 3,
                          "line": 4, "quote": lines[3]})
        context = gateway.calls[0]
        self.assertEqual(context["task"], "contract_extract")
        self.assertEqual(set(context["fields"]), set(FIELDS))
        self.assertEqual(context["document"]["text"], self.document["text"])

    def test_missing_fields_remain_unknown_without_clearing_saved_values(self):
        result, _ = self.run_fields([])
        self.assertEqual([row["field"] for row in result["candidates"]], list(FIELDS))
        for row in result["candidates"]:
            self.assertIsNone(row["value"])
            self.assertIsNone(row["evidence"])
            self.assertFalse(row["valid"])
            self.assertTrue(row["reason"])
        self.assertEqual(result["preview_findings"], self.review["findings"])

    def test_fabricated_lines_quotes_values_and_metadata_lines_are_invalid(self):
        self.document["text"] = "[page 7]\nRent is AUD $500 weekly, at 12 Example Street.\nDates 2027-02-01 to 2028-01-31."
        quote = self.document["text"].splitlines()[1]
        cases = [candidate("rent_amount", 500, 90, quote),
                 candidate("rent_amount", 500, True, quote),
                 candidate("rent_amount", 500, 2.0, quote),
                 candidate("rent_amount", 500, 2, "Rent is AUD $999 weekly."),
                 candidate("rent_amount", 50, 2, quote),
                 candidate("address", "Other Address", 2, quote),
                 candidate("start_date", "2027-03-01", 3, self.document["text"].splitlines()[2]),
                 candidate("rent_period", "month", 2, quote),
                 candidate("rent_scope", "whole_property", 2, quote),
                 candidate("rent_amount", 7, 1, "[page 7]"),
                 candidate("currency", "AUD", 2, quote.strip("."))]
        for row in cases:
            with self.subTest(row=row):
                result, _ = self.run_fields([row])
                found = next(item for item in result["candidates"] if item["field"] == row["field"])
                self.assertFalse(found["valid"])
                self.assertTrue(found["reason"])
                self.assertEqual(result["preview_findings"], self.review["findings"])

    def test_invalid_types_dates_enums_and_nonfinite_numbers_are_invalid(self):
        self.document["text"] = "AUD $500 true 2027-02-30 20270201 2027-W05-1 week month per_person USD -5 nan inf"
        quote = self.document["text"]
        cases = [("rent_amount", True), ("rent_amount", "500"), ("rent_amount", float("nan")),
                 ("rent_amount", float("inf")), ("rent_amount", -5), ("rent_amount", 0),
                 ("rent_amount", 1_000_000), ("address", 500), ("address", ""),
                 ("start_date", "2027-02-30"), ("start_date", "20270201"),
                 ("start_date", "2027-W05-1"), ("end_date", True),
                 ("currency", "USD"), ("rent_period", "year"), ("rent_scope", "each")]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                result, _ = self.run_fields([candidate(field, value, 1, quote)])
                found = next(item for item in result["candidates"] if item["field"] == field)
                self.assertFalse(found["valid"])
                self.assertTrue(found["reason"])
                json.dumps(result, allow_nan=False)

    def test_duplicate_and_unknown_fields_are_visible_but_never_applied(self):
        line = self.document["text"].splitlines()[3]
        rows = [candidate("rent_amount", 500, 4, line), candidate("rent_amount", 500, 4, line),
                candidate("bond", 2000, 5, self.document["text"].splitlines()[4])]
        result, _ = self.run_fields(rows)
        duplicates = [row for row in result["candidates"] if row["field"] == "rent_amount"]
        self.assertEqual(len(duplicates), 2)
        self.assertTrue(all(not row["valid"] and "duplicate" in row["reason"].lower() for row in duplicates))
        unknown = next(row for row in result["candidates"] if row["field"] == "bond")
        self.assertFalse(unknown["valid"])
        self.assertEqual(result["preview_findings"], self.review["findings"])

    def test_null_and_malformed_rows_are_invalid_candidates(self):
        rows = [candidate("address", None, None, None), {"field": "rent_amount", "value": 500},
                "not an entry", {"field": ["address"], "value": "anything"}]
        result, _ = self.run_fields(rows)
        self.assertTrue(all(not row["valid"] and row["reason"] for row in result["candidates"]))
        self.assertEqual(result["preview_findings"], self.review["findings"])

    def test_malformed_overall_extraction_raises_value_error(self):
        for response in (None, [], {}, {"fields": None}, {"fields": {}}, {"fields": "bad"}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                analyze(self.document, self.review, lambda context: response)

    def test_preview_uses_original_rules_without_mutating_document_or_review(self):
        self.document, self.review = baseline("risk-demo.txt")
        self.document["text"] += "\nThe corrected rent is AUD $400 weekly per person."
        before_document, before_review = copy.deepcopy(self.document), copy.deepcopy(self.review)
        line_number = len(self.document["text"].splitlines())
        row = candidate("rent_amount", 400, line_number, self.document["text"].splitlines()[-1])
        result, gateway = self.run_fields([row])
        expected = correct_review(self.review, {"rent_amount": 400})
        self.assertEqual([f["code"] for f in result["preview_findings"]],
                         [f["code"] for f in expected["findings"]])
        rent_evidence = result["preview_findings"][0]["evidence"][1]
        self.assertEqual(rent_evidence, {"source_name": self.document["source_name"], "page": 1,
                                         "line": line_number, "quote": row["quote"]})
        self.assertEqual(expected["status"], "Awaiting Human Review")
        self.assertTrue(any(f["severity"] == "high" for f in result["preview_findings"]))
        self.assertEqual(self.document, before_document)
        self.assertEqual(self.review, before_review)
        self.assertEqual([call["task"] for call in gateway.calls], ["contract_extract", "contract_explain"])
        self.assertEqual(gateway.calls[1]["findings"], result["preview_findings"])
        self.assertEqual(result["explanation_status"], "success")

    def test_valid_candidates_alone_affect_preview_and_explanations_cannot_change_risks(self):
        self.document, self.review = baseline("risk-demo.txt")
        original = copy.deepcopy(self.review)
        quote = self.document["text"].splitlines()[3]
        response = {"explanations": [{"finding_id": finding["id"], "text": "Clarify the saved evidence.",
                                      "severity": "low", "status": "Reviewed"}
                                     for finding in self.review["findings"]], "status": "Reviewed"}
        result, _ = self.run_fields([candidate("rent_amount", 100, 4, quote)], explanations=response)
        self.assertEqual(result["preview_findings"], original["findings"])
        self.assertEqual(self.review, original)
        self.assertTrue(all(set(item) == {"finding_id", "text"} for item in result["explanations"]))

    def test_explanation_wrong_missing_duplicate_ids_and_bad_text_fail_closed(self):
        self.document, self.review = baseline("risk-demo.txt")
        finding_id = self.review["findings"][0]["id"]
        cases = [{"explanations": [{"finding_id": "made-up", "text": "Claim"}]},
                 {"explanations": []},
                 {"explanations": [{"finding_id": finding_id, "text": "Claim"}] * 2},
                 {"explanations": [{"finding_id": finding_id, "text": " "}]},
                 {"explanations": [{"finding_id": finding_id, "text": "x" * 1001}]},
                 {"explanations": [None]}, {"explanations": None}, None]
        for response in cases:
            with self.subTest(response=response):
                gateway = Gateway([], explanations=response)
                if response is None:
                    def malformed(context):
                        return {"fields": []} if context["task"] == "contract_extract" else None
                    gateway = malformed
                result = analyze(self.document, self.review, gateway)
                self.assertEqual(result["explanation_status"], "failed")
                self.assertEqual(result["explanations"], [])
                self.assertEqual(result["preview_findings"], self.review["findings"])

    def test_explanation_failure_leaves_validated_candidates_and_preview_usable(self):
        self.document, self.review = baseline("risk-demo.txt")
        quote = self.document["text"].splitlines()[4]
        result, gateway = self.run_fields([candidate("rent_amount", 500, 5, quote)],
                                        explanations=TimeoutError("provider secret and agreement text"))
        self.assertTrue(next(item for item in result["candidates"] if item["field"] == "rent_amount")["valid"])
        self.assertEqual(result["preview_findings"], self.review["findings"])
        self.assertEqual(result["explanation_status"], "failed")
        self.assertNotIn("provider secret", json.dumps(result))
        self.assertEqual(len(gateway.calls), 2)

    def test_money_tokens_handle_punctuation_without_matching_substrings_or_dates(self):
        cases = [("Rent is $500.", 500, True), ("Pay $500, due weekly.", 500, True),
                 ("Pay $1,250.50 weekly.", 1250.5, True), ("Pay $500.01 weekly.", 500, False),
                 ("Pay $-500 weekly.", 500, False), ("Pay $5000 weekly.", 500, False),
                 ("The term starts 2027-02-01.", 2027, False)]
        for quote, value, valid in cases:
            with self.subTest(quote=quote, value=value):
                self.document["text"] = quote
                result, _ = self.run_fields([candidate("rent_amount", value, 1, quote)])
                found = next(item for item in result["candidates"] if item["field"] == "rent_amount")
                self.assertEqual(found["valid"], valid)

    def test_preview_keeps_rule_pack_and_low_extraction_suspensions(self):
        for as_of, text in [("2027-01-01", self.document["text"]),
                            ("2026-10-15", "Narrative agreement for 12 Example Street, details pending.")]:
            with self.subTest(as_of=as_of, text=text):
                self.document["text"] = text
                self.review = review_agreement(self.document, consent=True, as_of=as_of)
                line = next(i for i, raw in enumerate(text.splitlines(), 1) if "Street" in raw) if "Street" in text else 4
                quote = text.splitlines()[line - 1]
                value = "12 Example Street" if "Street" in quote else self.review["fields"]["address"]["value"]
                result, gateway = self.run_fields([candidate("address", value, line, quote)])
                self.assertEqual(result["preview_findings"], [])
                self.assertEqual(result["explanation_status"], "skipped")
                self.assertEqual(len(gateway.calls), 1)

    def test_no_findings_skips_explanation_request(self):
        result, gateway = self.run_fields([])
        self.assertEqual(result["preview_findings"], [])
        self.assertEqual(result["explanations"], [])
        self.assertEqual(result["explanation_status"], "skipped")
        self.assertEqual(len(gateway.calls), 1)

    def test_gateway_cannot_mutate_review_or_document_through_its_context(self):
        self.document, self.review = baseline("risk-demo.txt")
        document_before, review_before = copy.deepcopy(self.document), copy.deepcopy(self.review)
        def gateway(context):
            if context["task"] == "contract_extract":
                context.clear()
                return {"fields": []}
            context["findings"][0]["severity"] = "low"
            context["findings"][0]["evidence"].clear()
            return {"explanations": [{"finding_id": finding["id"], "text": "Check evidence"}
                                     for finding in self.review["findings"]]}
        result = analyze(self.document, self.review, gateway)
        self.assertEqual(result["preview_findings"], review_before["findings"])
        self.assertEqual(self.document, document_before)
        self.assertEqual(self.review, review_before)


if __name__ == "__main__":
    unittest.main()
