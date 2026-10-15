"""Agent 2 -> Agent 3 local intake with durable request-id replay handling."""

from __future__ import annotations

from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from .errors import ContractError, DuplicateRequestConflict, SelectionError
from .handoff import validate_selection
from .review import review_agreement

REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _fingerprint(document: dict, selection: dict, as_of: str, allow_external_ai: bool) -> str:
    payload = {"document_sha256": document["sha256"], "selection": selection,
               "as_of": as_of, "allow_external_ai": allow_external_ai}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf-8")
    return sha256(raw).hexdigest()


def receive_review(document: dict, *, consent: bool, selection: dict, request_id: str,
                   as_of: str, store: str | Path, gateway=None,
                   allow_external_ai: bool = False) -> tuple[dict, bool]:
    """Return (review, newly_created). A retry returns the original review byte data.

    The caller must explicitly provide a stable request ID and reference date.
    SQLite serializes concurrent deliveries of the same request ID.
    """
    if consent is not True:
        raise ContractError("Explicit consent is required before receiving an agreement")
    if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise ContractError("request_id must contain 1-128 letters, digits, dots, underscores, colons or hyphens")
    if selection is None:
        raise SelectionError("Agent 2 SelectedListingEvidence is required for receive")
    selected = validate_selection(selection)
    if not isinstance(document, dict) or not isinstance(document.get("sha256"), str):
        raise ContractError("A loaded agreement with SHA-256 is required")
    # review_agreement also validates the date and text before a new result is stored.
    digest = _fingerprint(document, selected, as_of, allow_external_ai)
    path = Path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(path, timeout=5)) as db:
            with db:
                db.execute("CREATE TABLE IF NOT EXISTS intake_requests ("
                           "request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, "
                           "review_json TEXT NOT NULL)")
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT fingerprint, review_json FROM intake_requests WHERE request_id = ?",
                                 (request_id,)).fetchone()
                if row is not None:
                    if row[0] != digest:
                        raise DuplicateRequestConflict("request_id already belongs to a different agreement, selection or reference date")
                    return json.loads(row[1]), False
                review = review_agreement(document, consent=True, selection=selected, as_of=as_of,
                                          gateway=gateway, allow_external_ai=allow_external_ai)
                review["intake"] = {
                    "request_id": request_id, "selection_sha256": sha256(json.dumps(
                        selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                        allow_nan=False).encode("utf-8")).hexdigest(),
                    "document_sha256": document["sha256"],
                    "recommendation_run_id": selected["recommendation_run_id"],
                    "selection_check_run_id": selected["selection_check_run_id"],
                    "search_id": selected["search_id"], "profile_version": selected["profile_version"],
                    "listing_id": selected["listing_id"], "selected_at": selected["selected_at"],
                    "received_review_version": 1,
                }
                db.execute("INSERT INTO intake_requests VALUES (?, ?, ?)",
                           (request_id, digest, json.dumps(review, ensure_ascii=False, allow_nan=False)))
                return review, True
    except sqlite3.Error as exc:
        raise ContractError(f"Intake request store is unavailable: {exc}") from exc
