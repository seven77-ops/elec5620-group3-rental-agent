"""Run with: python3 -m contract_agent review --agreement ... --consent --output ..."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .document import load_document
from .contracts import question_list, validate_review
from .errors import ContractError
from .intake import receive_review
from .model_gateway import configured_gateway
from .report import render_markdown
from .review import approve_review, correct_review, generate_questions, review_agreement


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ContractError(f"Duplicate JSON field: {key}")
        value[key] = item
    return value


def _invalid_constant(value):
    raise ContractError(f"Non-finite JSON value: {value}")


def _load_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        value = json.load(stream, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    if not isinstance(value, dict):
        raise ContractError("JSON input must be an object")
    return value


def _write(review, prefix, *, allow_identical=False):
    validate_review(review)
    question_packet = question_list(review) if review["status"] == "Questions Ready" else None
    json_text = json.dumps(review, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    markdown_text = render_markdown(review)
    question_text = (json.dumps(question_packet, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
                     if question_packet is not None else None)
    json_path, md_path = Path(str(prefix) + ".json"), Path(str(prefix) + ".md")
    questions_path = Path(str(prefix) + ".questions.json") if review["status"] == "Questions Ready" else None
    paths = [json_path, md_path] + ([questions_path] if questions_path else [])
    if any(path.exists() or path.is_symlink() for path in paths):
        expected = [json_text, markdown_text] + ([question_text] if questions_path else [])
        if (allow_identical and all(path.is_file() and not path.is_symlink() for path in paths)
                and all(path.read_text(encoding="utf-8") == content
                        for path, content in zip(paths, expected))):
            print(f"Existing identical output: {json_path}\nStatus: {review['status']}")
            return
        raise ContractError("Output exists with different content; choose a new --output prefix")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("x", encoding="utf-8") as stream:
        stream.write(json_text)
    with md_path.open("x", encoding="utf-8") as stream:
        stream.write(markdown_text)
    if questions_path:
        with questions_path.open("x", encoding="utf-8") as stream:
            stream.write(question_text)
    print(f"Review: {json_path}\nReadable report: {md_path}\nStatus: {review['status']}")
    if questions_path:
        print(f"Question list (not sent): {questions_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Agent 3 course prototype: local, evidence-grounded contract assistance")
    actions = parser.add_subparsers(dest="action", required=True)
    start = actions.add_parser("review", help="UC05: read and assess an agreement")
    start.add_argument("--agreement", required=True, help="TXT, DOCX or text-based PDF")
    start.add_argument("--consent", action="store_true", help="tenant explicitly consented to processing")
    start.add_argument("--selection", help="optional Agent 2 SelectedListingEvidence .selection.json")
    start.add_argument("--as-of", help="reference date YYYY-MM-DD; default Sydney date")
    start.add_argument("--allow-external-ai", action="store_true", help="tenant also consents to configured model")
    start.add_argument("--output", required=True, help="new file prefix for .json and .md")
    receive = actions.add_parser("receive", help="SCRUM-25: idempotent Agent 2 selection and agreement intake")
    receive.add_argument("--agreement", required=True)
    receive.add_argument("--consent", action="store_true")
    receive.add_argument("--selection", required=True, help="Agent 2 SelectedListingEvidence JSON")
    receive.add_argument("--request-id", required=True, help="stable caller-generated ID for retries")
    receive.add_argument("--as-of", required=True, help="fixed reference date YYYY-MM-DD")
    receive.add_argument("--store", default="reports/intake-requests.sqlite3", help="local SQLite receipt store")
    receive.add_argument("--allow-external-ai", action="store_true")
    receive.add_argument("--output", required=True)
    correct = actions.add_parser("correct", help="save tenant corrections as a new review version")
    correct.add_argument("--review", required=True)
    correct.add_argument("--corrections", required=True, help="JSON object of changed field values")
    correct.add_argument("--output", required=True)
    decide = actions.add_parser("decide", help="record a human escalation decision")
    decide.add_argument("--review", required=True)
    decide.add_argument("--decision", required=True, choices=["approve", "return"])
    decide.add_argument("--reviewer", required=True)
    decide.add_argument("--note", required=True)
    decide.add_argument("--output", required=True)
    questions = actions.add_parser("questions", help="UC06: generate/edit questions from Reviewed findings")
    questions.add_argument("--review", required=True)
    questions.add_argument("--edits", help="optional JSON array of {finding_id,text} edits")
    questions.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "review":
            document = load_document(args.agreement, consent=args.consent)
            selected = _load_json(args.selection) if args.selection else None
            review = review_agreement(document, consent=args.consent, selection=selected,
                                      as_of=args.as_of, gateway=configured_gateway if args.allow_external_ai else None,
                                      allow_external_ai=args.allow_external_ai)
        elif args.action == "receive":
            document = load_document(args.agreement, consent=args.consent)
            selection = _load_json(args.selection)
            review, created = receive_review(
                document, consent=args.consent, selection=selection, request_id=args.request_id,
                as_of=args.as_of, store=args.store,
                gateway=configured_gateway if args.allow_external_ai else None,
                allow_external_ai=args.allow_external_ai)
        elif args.action == "correct":
            review = correct_review(validate_review(_load_json(args.review)), _load_json(args.corrections))
        elif args.action == "decide":
            review = approve_review(validate_review(_load_json(args.review)), reviewer=args.reviewer,
                                    decision=args.decision, note=args.note)
        else:
            edits = None
            if args.edits:
                with Path(args.edits).open(encoding="utf-8") as stream:
                    edits = json.load(stream, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
            review = generate_questions(validate_review(_load_json(args.review)), edits=edits)
        _write(review, args.output, allow_identical=args.action == "receive" and not created)
        if args.action == "receive":
            print("Intake: created" if created else "Intake: duplicate request, original review returned")
        return 0
    except (ContractError, OSError, ValueError, TypeError, KeyError) as exc:
        code = exc.code if isinstance(exc, ContractError) else "input_or_io_error"
        print(json.dumps({"error": {"code": code, "message": str(exc),
                                    "request_id": getattr(args, "request_id", None)}},
                         ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
