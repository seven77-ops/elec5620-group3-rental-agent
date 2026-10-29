"""Versioned NSW reference checks; informational flags, not legal conclusions."""

from __future__ import annotations

from datetime import date, timedelta
import re
import unicodedata

RULE_PACK = {
    "version": "NSW-reference-2026-10-15",
    "verified_on": "2026-10-15",
    # Re-checked against source_url on 2026-10-29: the page (last updated 19 May 2025) still
    # states a bond of "no more than 4 weeks rent"; the rules are unchanged, so the version is kept.
    "rechecked_on": "2026-10-29",
    "max_age_days": 30,
    "source_url": "https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/starting-a-residential-tenancy/signing-a-lease-and-moving",
}


def rule_pack_current(as_of: str, rule_pack: dict = RULE_PACK) -> bool:
    checked = date.fromisoformat(rule_pack["verified_on"])
    latest = date.fromisoformat(rule_pack.get("rechecked_on") or rule_pack["verified_on"])
    today = date.fromisoformat(as_of)
    return checked <= today <= latest + timedelta(days=rule_pack["max_age_days"])


def _normalized(value):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", str(value)).casefold())


def evaluate_findings(fields: dict, selection: dict | None, rule_pack: dict = RULE_PACK,
                      clauses: list | None = None) -> list[dict]:
    findings = []

    def add(code, severity, title, reason, evidence, *, rule=False):
        findings.append({"id": f"F{len(findings)+1:02}", "code": code, "severity": severity,
                         "title": title, "reason": reason, "evidence": evidence,
                         "rule_version": rule_pack["version"] if rule else None,
                         "rule_url": rule_pack["source_url"] if rule else None})

    def ev(key):
        return fields[key]["evidence"]

    for key, label in (("address", "property address"), ("landlord", "landlord"),
                       ("tenant", "tenant"), ("rent_amount", "rent amount"),
                       ("bond", "bond"), ("start_date", "start date")):
        if fields[key]["value"] is None:
            add(f"missing_{key}", "needs_review", f"Missing {label}",
                "The simple extractor did not locate this field; inspect the original agreement.", [])

    rent, bond = fields["rent_amount"]["value"], fields["bond"]["value"]
    period = fields["rent_period"]["value"]
    if rent is not None and bond is not None:
        if period == "week" and bond > 4 * rent:
            add("bond_over_four_weeks", "high", "Bond exceeds four weeks of rent",
                "The extracted bond exceeds four times the extracted weekly agreement rent; verify both values and seek qualified help if needed.",
                [ev("bond"), ev("rent_amount")], rule=True)
        elif period != "week":
            add("bond_basis_unknown", "needs_review", "Bond comparison needs weekly rent",
                "The agreement rent period could not be used for the four-week reference check.",
                [ev("bond"), ev("rent_amount")], rule=True)

    start, end = fields["start_date"]["value"], fields["end_date"]["value"]
    if start and end and date.fromisoformat(end) <= date.fromisoformat(start):
        add("date_order", "high", "End date is not after start date",
            "The extracted agreement dates are inconsistent; check the original.",
            [ev("start_date"), ev("end_date")])

    if selection is not None:
        snapshot = selection["listing_snapshot"]
        source = {"source_name": "Agent 2 SelectedListingEvidence", "listing_id": selection["listing_id"],
                  "recommendation_run_id": selection["recommendation_run_id"],
                  "selected_at": selection["selected_at"]}
        address = fields["address"]["value"]
        listed_address = snapshot.get("address")
        if address and listed_address and _normalized(address) != _normalized(listed_address):
            add("address_difference", "high",
                "Agreement and selected listing addresses differ",
                "The listing location may be less precise than the agreement; a human must confirm the actual premises.",
                [ev("address"), {**source, "field": "listing_snapshot.address",
                                 "value": listed_address, "source_ref": snapshot.get("evidence", {}).get("address", {}).get("source_ref")}])
        listed_rent = snapshot.get("rent_amount")
        if rent is not None and isinstance(listed_rent, (int, float)) and not isinstance(listed_rent, bool):
            compatible = (period == snapshot.get("rent_period") == "week"
                          and fields["rent_scope"]["value"] == snapshot.get("rent_scope")
                          and fields["currency"]["value"] == snapshot.get("currency") == "AUD")
            if compatible and abs(rent - listed_rent) > 0.005:
                add("rent_difference", "high", "Agreement rent differs from selected listing",
                    "The amount differs for the same weekly period, scope and currency; ask which amount applies.",
                    [ev("rent_amount"), {**source, "field": "listing_snapshot.rent_amount",
                                         "value": listed_rent,
                                         "source_ref": snapshot.get("evidence", {}).get("rent_amount", {}).get("source_ref")}])
            elif not compatible:
                add("rent_not_comparable", "needs_review", "Listing and agreement rent bases need confirmation",
                    "Rent period, charging scope or currency is missing or differs; the amounts were not compared.",
                    [ev("rent_amount"), {**source, "field": "listing_snapshot.rent_amount",
                                         "value": listed_rent}])
    # Extra terms can change obligations; they are flagged for reading, never judged lawful or unlawful.
    for clause in clauses or []:
        add("additional_term_review", "needs_review", "Additional term needs reading",
            "This term is outside the standard NSW form fields. Read it carefully (for example cleaning, fees or "
            "end-of-tenancy duties) and ask the landlord or agent before signing.", [clause["evidence"]])
    return findings
