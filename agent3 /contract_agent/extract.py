"""Conservative labelled-field extraction with line/page evidence."""

from __future__ import annotations

import re
from datetime import date

FIELDS = ("address", "landlord", "tenant", "rent_amount", "rent_period", "rent_scope",
          "currency", "bond", "start_date", "end_date", "signed_date")
LABELS = {
    "address": r"(?:property\s+address|premises|address)",
    "landlord": r"(?:landlord|lessor)",
    "tenant": r"(?:tenant|lessee)",
    "rent_amount": r"(?:weekly\s+rent|monthly\s+rent|rent\s+per\s+week|rent\s+per\s+month|rent)",
    "bond": r"(?:rental\s+bond|bond)",
    "start_date": r"(?:start\s+date|commencement\s+date)",
    "end_date": r"(?:end\s+date|expiry\s+date)",
    "signed_date": r"(?:signing\s+date|date\s+signed)",
}
MONEY = re.compile(r"(?:AUD\s*)?\$?\s*([\d,]+(?:\.\d{1,2})?)", re.I)
ISO_DATE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")


def _entry(value=None, *, source_name=None, page=None, line=None, quote=None, confidence=0.0):
    evidence = None if quote is None else {"source_name": source_name, "page": page,
                                           "line": line, "quote": quote[:300]}
    return {"value": value, "confidence": confidence, "evidence": evidence}


def extract_fields(document: dict) -> tuple[dict, list[dict], float]:
    fields = {key: _entry() for key in FIELDS}
    clauses = []
    page = 1
    source_confidence = 0.65 if document.get("extraction_mode") == "ocr" else 0.9
    for line_number, raw in enumerate(document["text"].splitlines(), 1):
        marker = re.fullmatch(r"\[page (\d+)\]", raw.strip(), re.I)
        if marker:
            page = int(marker.group(1))
            continue
        line = raw.strip()
        if not line:
            continue
        evidence = {"source_name": document["source_name"], "page": page,
                    "line": line_number, "quote": line[:300]}
        if re.match(r"(?:additional\s+(?:term|clause)|special\s+condition)\s*[:\-]", line, re.I):
            clauses.append({"text": line[:1000], "evidence": evidence})
        for key, label in LABELS.items():
            if fields[key]["value"] is not None:
                continue
            match = re.match(rf"{label}\s*[:\-]\s*(.+)$", line, re.I)
            if not match:
                continue
            raw_value = match.group(1).strip()
            value = raw_value[:200]
            if key in ("rent_amount", "bond"):
                amount = MONEY.search(raw_value)
                if not amount:
                    continue
                value = float(amount.group(1).replace(",", ""))
            elif key.endswith("_date"):
                parsed = ISO_DATE.search(raw_value)
                if not parsed:
                    continue
                try:
                    date.fromisoformat(parsed.group(1))
                except ValueError:
                    continue
                value = parsed.group(1)
            fields[key] = _entry(value, source_name=document["source_name"], page=page,
                                  line=line_number, quote=line, confidence=source_confidence)
            if key == "rent_amount":
                if re.search(r"weekly|per\s+week|/\s*(?:week|wk)\b", line, re.I):
                    fields["rent_period"] = _entry("week", source_name=document["source_name"],
                                                    page=page, line=line_number, quote=line, confidence=source_confidence)
                elif re.search(r"monthly|per\s+month|/\s*(?:month|mo)\b", line, re.I):
                    fields["rent_period"] = _entry("month", source_name=document["source_name"],
                                                    page=page, line=line_number, quote=line, confidence=source_confidence)
                for pattern, scope in ((r"per\s+person", "per_person"), (r"per\s+room", "per_room"),
                                       (r"whole\s+property", "whole_property")):
                    if re.search(pattern, line, re.I):
                        fields["rent_scope"] = _entry(scope, source_name=document["source_name"],
                                                       page=page, line=line_number, quote=line, confidence=source_confidence)
                if "$" in line or re.search(r"\bAUD\b", line, re.I):
                    fields["currency"] = _entry("AUD", source_name=document["source_name"],
                                                 page=page, line=line_number, quote=line, confidence=source_confidence - 0.1)
    core = ("address", "landlord", "tenant", "rent_amount", "bond", "start_date")
    confidence = round(sum(fields[key]["confidence"] for key in core) / len(core), 3)
    return fields, clauses, confidence
