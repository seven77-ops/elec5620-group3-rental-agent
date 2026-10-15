"""UC05/UC06 lifecycle; all rule decisions remain deterministic."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import uuid
from zoneinfo import ZoneInfo

from .errors import ContractError
from .extract import FIELDS, extract_fields
from .handoff import validate_selection
from .model_gateway import explanation
from .rules import RULE_PACK, evaluate_findings, rule_pack_current


def _now() -> str:
    return datetime.now(ZoneInfo("Australia/Sydney")).isoformat(timespec="seconds")


def _assess(review: dict, *, gateway=None, allow_external_ai=False) -> None:
    if review["extraction_confidence"] < 0.5:
        review.update(status="Awaiting Resubmission", findings=[], explanations=[], mode="none",
                      human_review=None, status_reason="Key agreement fields could not be extracted reliably")
        return
    if not rule_pack_current(review["as_of"], review["rule_pack"]):
        review.update(status="Degraded Summary Only", findings=[], explanations=[], mode="none",
                      human_review=None, status_reason="NSW reference pack is missing or stale; rule conclusions suspended")
        return
    findings = evaluate_findings(review["fields"], review["selection_evidence"], review["rule_pack"])
    explanations, mode = explanation(findings, gateway, allow_external_ai=allow_external_ai)
    high = [f["id"] for f in findings if f["severity"] == "high"]
    review.update(findings=findings, explanations=explanations, mode=mode,
                  status="Awaiting Human Review" if high else "Reviewed",
                  human_review={"status": "pending", "finding_ids": high} if high else None,
                  status_reason="High-severity finding requires human escalation decision" if high else None)


def review_agreement(document: dict, *, consent: bool, selection: dict | None = None,
                     as_of: str | None = None, gateway=None, allow_external_ai=False,
                     rule_pack: dict | None = None) -> dict:
    if consent is not True:
        raise ContractError("Explicit consent is required before reviewing an agreement")
    if not isinstance(document, dict) or not isinstance(document.get("text"), str):
        raise ContractError("A readable document is required")
    if len(document["text"].strip()) < 30 or len(document["text"]) > 120_000:
        raise ContractError("Agreement text is empty, unreadable or too long")
    selected = validate_selection(selection)
    as_of = as_of or datetime.now(ZoneInfo("Australia/Sydney")).date().isoformat()
    try:
        date.fromisoformat(as_of)
    except ValueError as exc:
        raise ContractError("as_of must be YYYY-MM-DD") from exc
    fields, clauses, confidence = extract_fields(document)
    review = {
        "schema_version": "1.0", "review_id": "cr-" + uuid.uuid4().hex,
        "version": 1, "created_at": _now(), "updated_at": _now(), "as_of": as_of,
        "status": "Reviewing", "status_reason": None,
        "document": {key: document.get(key) for key in ("source_name", "sha256", "format", "page_count", "extraction_mode")},
        "consented_at": _now(), "fields": fields, "additional_clauses": clauses,
        "extraction_confidence": confidence, "selection_evidence": deepcopy(selected),
        "rule_pack": deepcopy(rule_pack if rule_pack is not None else RULE_PACK),
        "findings": [], "explanations": [], "mode": "none", "human_review": None,
        "questions": [], "question_version": 0, "revisions": [], "events": [],
        "data_limitations": ["Course prototype: informational checklist, not legal advice.",
                             "Field extraction is narrow; verify all values against the original agreement."],
    }
    if selected is not None:
        review["data_limitations"].extend(selected["data_limitations"])
    _assess(review, gateway=gateway, allow_external_ai=allow_external_ai)
    review["events"].append({"at": _now(), "action": "review", "version": 1,
                             "result": review["status"]})
    return review


def correct_review(previous: dict, changes: dict) -> dict:
    if not isinstance(changes, dict) or not changes:
        raise ContractError("Provide at least one field correction")
    if any(key not in FIELDS for key in changes):
        raise ContractError("Unknown contract field in correction")
    review = deepcopy(previous)
    for key, value in changes.items():
        if value == "":
            value = None
        if key in {"rent_amount", "bond"} and value is not None:
            if isinstance(value, bool):
                raise ContractError(f"{key} must be a positive number")
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise ContractError(f"{key} must be a positive number") from exc
            if not 0 < value < 1_000_000:
                raise ContractError(f"{key} is outside the supported range")
        if key.endswith("_date") and value is not None:
            try:
                value = date.fromisoformat(str(value)).isoformat()
            except ValueError as exc:
                raise ContractError(f"{key} must be YYYY-MM-DD") from exc
        if key == "rent_period" and value not in (None, "week", "fortnight", "month"):
            raise ContractError("rent_period is unsupported")
        if key == "rent_scope" and value not in (None, "per_person", "per_room", "whole_property"):
            raise ContractError("rent_scope is unsupported")
        if key == "currency" and value not in (None, "AUD"):
            raise ContractError("Only AUD currency is supported")
        if isinstance(value, str) and len(value) > 200:
            raise ContractError(f"{key} is too long")
    if all(review["fields"][key]["value"] == value for key, value in changes.items()):
        return review
    review["revisions"].append({"version": review["version"], "status": review["status"],
                                "fields": deepcopy(review["fields"]),
                                "findings": deepcopy(review["findings"]),
                                "human_review": deepcopy(review["human_review"])})
    review["version"] += 1
    for key, value in changes.items():
        if review["fields"][key]["value"] != value:
            review["fields"][key] = {"value": value, "confidence": 1.0 if value is not None else 0.0,
                                      "evidence": {"source_name": "tenant correction", "page": None,
                                                   "line": None, "quote": None} if value is not None else None}
    core = ("address", "landlord", "tenant", "rent_amount", "bond", "start_date")
    review["extraction_confidence"] = round(sum(review["fields"][key]["confidence"] for key in core) / len(core), 3)
    review["questions"] = []
    review["question_version"] = 0
    review["updated_at"] = _now()
    _assess(review)
    review["events"].append({"at": _now(), "action": "tenant_correction",
                             "version": review["version"], "result": review["status"]})
    return review


def approve_review(previous: dict, *, reviewer: str, decision: str, note: str) -> dict:
    if previous.get("status") != "Awaiting Human Review":
        raise ContractError("Only a pending high-risk review can receive an escalation decision")
    if (decision not in {"approve", "return"} or not isinstance(reviewer, str)
            or not reviewer.strip() or not isinstance(note, str) or not note.strip()):
        raise ContractError("Reviewer, approve/return decision and reason are required")
    review = deepcopy(previous)
    review["human_review"] = {"status": "approved" if decision == "approve" else "returned",
                              "finding_ids": previous["human_review"]["finding_ids"],
                              "reviewer": reviewer.strip()[:120], "note": note.strip()[:1000], "decided_at": _now(),
                              "review_version": review["version"]}
    review["status"] = "Reviewed" if decision == "approve" else "Awaiting Resubmission"
    review["status_reason"] = None if decision == "approve" else "Human reviewer requested a clearer or corrected copy"
    review["updated_at"] = _now()
    review["events"].append({"at": _now(), "action": "human_escalation_decision",
                             "version": review["version"], "result": review["status"]})
    return review


def generate_questions(previous: dict, edits: list[dict] | None = None) -> dict:
    if previous.get("status") not in {"Reviewed", "Questions Ready"}:
        raise ContractError("Questions require a Reviewed contract version")
    review = deepcopy(previous)
    questions = [{"finding_id": f["id"], "review_version": review["version"],
                  "text": f"Could you clarify: {f['title']}? {f['reason']}",
                  "evidence": deepcopy(f["evidence"])} for f in review["findings"]]
    if edits is not None:
        if not isinstance(edits, list) or {e.get("finding_id") for e in edits if isinstance(e, dict)} != {q["finding_id"] for q in questions} or len(edits) != len(questions):
            raise ContractError("Edited questions must preserve every original finding reference")
        replacement = {e["finding_id"]: e.get("text") for e in edits}
        if any(not isinstance(text, str) or not 1 <= len(text.strip()) <= 1000 for text in replacement.values()):
            raise ContractError("Every edited question needs non-empty text up to 1000 characters")
        for question in questions:
            question["text"] = replacement[question["finding_id"]].strip()
    review["questions"] = questions
    review["question_version"] += 1
    review["status"] = "Questions Ready"
    review["updated_at"] = _now()
    review["events"].append({"at": _now(), "action": "generate_questions",
                             "version": review["version"], "result": "Questions Ready"})
    return review
