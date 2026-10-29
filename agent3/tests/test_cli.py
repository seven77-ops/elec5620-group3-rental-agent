import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "data" / "demo" / "selected-listing-evidence.json"
AGREEMENT = ROOT / "data" / "demo" / "agreements" / "risk-demo.txt"


class CliTests(unittest.TestCase):
    def command(self, *args):
        return subprocess.run([sys.executable, "-m", "contract_agent", *map(str, args)],
                              cwd=ROOT, capture_output=True, text=True)

    def test_review_decide_questions_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second, third = [Path(tmp) / name for name in ("review", "approved", "questions")]
            result = self.command("review", "--agreement", AGREEMENT, "--consent", "--selection", PACKET,
                                  "--as-of", "2026-10-15", "--output", first)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(Path(str(first) + ".json").read_text(encoding='utf-8'))["status"], "Awaiting Human Review")
            blocked = self.command("questions", "--review", str(first) + ".json", "--output", second)
            self.assertEqual(blocked.returncode, 2)
            approved = self.command("decide", "--review", str(first) + ".json", "--decision", "approve",
                                    "--reviewer", "Operator", "--note", "Reviewed escalation", "--output", second)
            self.assertEqual(approved.returncode, 0, approved.stderr)
            questions = self.command("questions", "--review", str(second) + ".json", "--output", third)
            self.assertEqual(questions.returncode, 0, questions.stderr)
            self.assertEqual(json.loads(Path(str(third) + ".json").read_text(encoding='utf-8'))["status"], "Questions Ready")
            packet = json.loads(Path(str(third) + ".questions.json").read_text(encoding='utf-8'))
            self.assertEqual(packet["recipient"], "Tenant")
            self.assertEqual(packet["handoff_status"], "prepared_not_sent")

    def test_no_consent_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / "result"
            denied = self.command("review", "--agreement", AGREEMENT, "--output", prefix)
            self.assertEqual(denied.returncode, 2)
            self.assertFalse(Path(str(prefix) + ".json").exists())
            okay = self.command("review", "--agreement", AGREEMENT, "--consent",
                                "--as-of", "2026-10-15", "--output", prefix)
            self.assertEqual(okay.returncode, 0, okay.stderr)
            again = self.command("review", "--agreement", AGREEMENT, "--consent",
                                 "--as-of", "2026-10-15", "--output", prefix)
            self.assertEqual(again.returncode, 2)

    def test_receive_is_idempotent_and_rejects_changed_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            prefix, second = directory / "review", directory / "same-review"
            common = ("receive", "--agreement", ROOT / "data" / "demo" / "agreements" / "selection-demo.txt",
                      "--consent", "--selection", PACKET, "--request-id", "SCRUM-25-001",
                      "--as-of", "2026-10-15", "--store", directory / "receipts.sqlite3")
            first = self.command(*common, "--output", prefix)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = json.loads(Path(str(prefix) + ".json").read_text(encoding='utf-8'))
            self.assertEqual(original["intake"]["listing_id"], "DEMO-006")
            self.assertEqual(original["intake"]["document_sha256"], original["document"]["sha256"])
            replay = self.command(*common, "--output", prefix)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertIn("duplicate request", replay.stdout)
            another_export = self.command(*common, "--output", second)
            self.assertEqual(another_export.returncode, 0, another_export.stderr)
            self.assertEqual(json.loads(Path(str(second) + ".json").read_text(encoding='utf-8')), original)
            changed = list(common)
            changed[2] = AGREEMENT
            conflict = self.command(*changed, "--output", directory / "conflict")
            self.assertEqual(conflict.returncode, 2)
            self.assertEqual(json.loads(conflict.stderr)["error"]["code"], "duplicate_request_conflict")
            self.assertFalse((directory / "conflict.json").exists())

    def test_receive_needs_consent_and_valid_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            args = ("receive", "--agreement", AGREEMENT, "--selection", PACKET,
                    "--request-id", "SCRUM-25-002", "--as-of", "2026-10-15",
                    "--store", directory / "receipts.sqlite3", "--output", directory / "review")
            denied = self.command(*args)
            self.assertEqual(json.loads(denied.stderr)["error"]["code"], "invalid_request")
            self.assertFalse((directory / "receipts.sqlite3").exists())
            packet = json.loads(PACKET.read_text(encoding="utf-8"))
            packet["listing_snapshot"]["listing_id"] = "WRONG"
            altered = directory / "invalid-selection.json"
            altered.write_text(json.dumps(packet), encoding="utf-8")
            invalid = self.command("receive", "--agreement", AGREEMENT, "--consent",
                                   "--selection", altered, "--request-id", "SCRUM-25-002",
                                   "--as-of", "2026-10-15", "--store", directory / "receipts.sqlite3",
                                   "--output", directory / "review")
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(json.loads(invalid.stderr)["error"]["code"], "invalid_selection")
