"""Local review schema validation, in the style of Agent 2 contracts.py."""

import json
from hashlib import sha256
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .errors import ContractError
from .handoff import validate_selection

SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "contract-review.schema.json"
QUESTIONS_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "contract-question-list.schema.json"


def validate_review(review):
    try:
        json.dumps(review, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ContractError("ContractReview contains non-JSON or non-finite values") from exc
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    error = next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(review), None)
    if error is not None:
        field = ".".join(map(str, error.absolute_path)) or "$"
        raise ContractError(f"ContractReview.{field}: {error.message}")
    validate_selection(review["selection_evidence"])
    if "intake" in review:
        selection = review["selection_evidence"]
        intake = review["intake"]
        if selection is None or intake["document_sha256"] != review["document"]["sha256"]:
            raise ContractError("ContractReview intake does not match its document or selection")
        for key in ("recommendation_run_id", "selection_check_run_id", "search_id",
                    "profile_version", "listing_id", "selected_at"):
            if intake[key] != selection[key]:
                raise ContractError(f"ContractReview intake.{key} disagrees with the selection")
        encoded = json.dumps(selection, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")
        if intake["selection_sha256"] != sha256(encoded).hexdigest():
            raise ContractError("ContractReview intake selection fingerprint disagrees")
    return review


def question_list(review):
    if review["status"] != "Questions Ready":
        raise ContractError("Question list is available only in Questions Ready status")
    packet = {"schema_version": "1.0", "recipient": "Tenant",
              "handoff_status": "prepared_not_sent", "review_id": review["review_id"],
              "review_version": review["version"], "question_version": review["question_version"],
              "generated_at": review["updated_at"], "questions": review["questions"]}
    schema = json.loads(QUESTIONS_SCHEMA.read_text(encoding="utf-8"))
    error = next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(packet), None)
    if error is not None:
        field = ".".join(map(str, error.absolute_path)) or "$"
        raise ContractError(f"ContractQuestionList.{field}: {error.message}")
    return packet
