"""Readable, escaped Markdown report matching Agent 2's JSON/Markdown outputs."""

from html import escape


def _cell(value):
    return escape(str(value if value is not None else "unknown"), quote=False).replace("|", "\\|").replace("\n", "<br>")


def render_markdown(review: dict) -> str:
    lines = ["# Agent 3 · Rental agreement review", "",
             f"- Review ID: `{_cell(review['review_id'])}` · version {review['version']}",
             f"- Status: **{_cell(review['status'])}**", f"- Reference date: {_cell(review['as_of'])}",
             f"- Document: {_cell(review['document']['source_name'])}",
             f"- NSW reference pack: {_cell(review['rule_pack']['version'])}",
             f"- Explanation mode: {_cell(review['mode'])}", "",
             "This is an informational course prototype. Verify the original agreement; it is not legal advice.", "",
             "## Extracted fields", "", "| Field | Value | Confidence | Source |", "|---|---|---:|---|"]
    for name, field in review["fields"].items():
        ev = field["evidence"] or {}
        source = f"{ev.get('source_name', '')} p.{ev.get('page', '?')} line {ev.get('line', '?')} — {ev.get('quote', '')}" if ev else "not located"
        lines.append(f"| {_cell(name)} | {_cell(field['value'])} | {field['confidence']:.2f} | {_cell(source)} |")
    lines.extend(["", "## Additional clauses located", ""])
    if review["additional_clauses"]:
        for item in review["additional_clauses"]:
            lines.append(f"- {_cell(item['text'])} ({_cell(item['evidence']['source_name'])}, page {item['evidence']['page']})")
    else:
        lines.append("No labelled additional clauses located; inspect the original.")
    lines.extend(["", "## Findings", ""])
    if review["findings"]:
        for finding in review["findings"]:
            lines.append(f"- **{_cell(finding['id'])} · {_cell(finding['severity'])} · {_cell(finding['title'])}** — {_cell(finding['reason'])}")
            if finding["rule_url"]:
                lines.append(f"  - Rule reference: {_cell(finding['rule_version'])} · {finding['rule_url']}")
            for item in finding["evidence"]:
                if item:
                    lines.append(f"  - Evidence: {_cell(item.get('quote') or item.get('field') or item.get('source_name'))}")
    else:
        lines.append("No checklist findings. This does not certify compliance.")
    if review["status_reason"]:
        lines.extend(["", f"**Workflow hold:** {_cell(review['status_reason'])}"])
    if review["human_review"]:
        lines.extend(["", "## Human escalation", "",
                      f"- Status: {_cell(review['human_review']['status'])}"])
        if review["human_review"].get("note"):
            lines.append(f"- Reviewer note: {_cell(review['human_review']['note'])}")
    lines.extend(["", "## Evidence-linked explanations", ""])
    for item in review["explanations"]:
        lines.append(f"- {_cell(item['finding_id'])}: {_cell(item['text'])}")
    if not review["explanations"]:
        lines.append("No explanation released for the current status.")
    lines.extend(["", "## Tenant questions (UC06)", ""])
    for item in review["questions"]:
        lines.append(f"- {_cell(item['finding_id'])} · review v{item['review_version']}: {_cell(item['text'])}")
    if not review["questions"]:
        lines.append("No questions generated or no findings require clarification.")
    lines.extend(["", "## Data limitations", ""])
    lines.extend(f"- {_cell(item)}" for item in review["data_limitations"])
    return "\n".join(lines) + "\n"
