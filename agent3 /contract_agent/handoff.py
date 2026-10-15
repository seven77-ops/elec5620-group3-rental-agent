"""Validate the actual Agent 2 SelectedListingEvidence contract."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .errors import SelectionError

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "selected-listing-evidence.schema.json"


def validate_selection(packet: dict | None) -> dict | None:
    if packet is None:
        return None
    if not isinstance(packet, dict):
        raise SelectionError("SelectedListingEvidence must be a JSON object")
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SelectionError("Bundled Agent 2 selection schema is unavailable") from exc
    error = next(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(packet), None)
    if error is not None:
        field = ".".join(map(str, error.absolute_path)) or "$"
        raise SelectionError(f"SelectedListingEvidence.{field}: {error.message}")
    snapshot, assessment, profile = packet["listing_snapshot"], packet["assessment"], packet["profile"]
    if not (packet["listing_id"] == snapshot["listing_id"] == assessment["listing_id"]):
        raise SelectionError("Selection listing IDs disagree")
    if packet["search_id"] != profile["search_id"] or packet["profile_version"] != profile["profile_version"]:
        raise SelectionError("Selection profile identity disagrees")
    profile_digest = sha256(json.dumps(profile, sort_keys=True, ensure_ascii=False,
                                       allow_nan=False).encode("utf-8")).hexdigest()
    if packet["profile_fingerprint"] != profile_digest:
        raise SelectionError("Selection profile fingerprint disagrees")
    if snapshot not in packet["source_records"]:
        raise SelectionError("Selected listing snapshot is absent from source records")
    if assessment["status"] != "eligible":
        raise SelectionError("Only an eligible selected listing can be supplied")
    return packet
