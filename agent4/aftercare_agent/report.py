"""Human-readable evidence and lifecycle export, always derived from committed JSON."""
from pathlib import Path
import json
from .errors import AftercareError, require


def safe(value):
    text = str(value).replace('\n', ' ').replace('\r', ' ')
    for character in ('\\', '`', '*', '_', '[', ']', '<', '>', '|', '#'):
        text = text.replace(character, '\\' + character)
    return text


def render_markdown(case):
    lines = [f"# M4 Aftercare · {safe(case['case_id'])}", '',
             f"Version {case['version']} · local prototype · all demo records are synthetic", '',
             f"Property: {safe(case['tenancy']['address'])}", '',
             'Dates use Australia/Sydney (AEST/AEDT). Planning dates are not statutory deadlines.', '']
    plan = case['plan']
    if plan:
        lines += ['## Move-out plan', '', f"State: {plan['state']} · move-out: {plan['move_out_date']}", '',
                  '| Task | Due (Sydney) | Status | Evidence references |', '|---|---|---|---|']
        for task in plan['tasks']:
            lines.append('| ' + ' | '.join(safe(v) for v in (task['title'], task['due_at'], task['status'], ', '.join(task['evidence_refs']))) + ' |')
        lines += ['', '**Missing evidence / clarification**', '']
        lines += ['- ' + safe(gap) for gap in plan['evidence_gaps'] + plan['clarification_requests']] or ['- None recorded.']
        if plan['pending_schedule']:
            lines += ['', 'Proposed move-out date: ' + plan['pending_schedule']['move_out_date'] + ' (awaiting tenant decision).', '',
                      'Old schedule and completed work are retained; reminders are suppressed until the decision.']
        lines += ['', 'Notice information: unverified; confirm applicable requirements using current official guidance.', '']
    bond = case['bond']
    if bond:
        lines += ['## Bond tracking', '', '**State: ' + bond['state'] + '**', '', '### Dated history', '']
        lines += [f"- {safe(e['occurred_at'])}: {safe(e['text'])} (tenant report; refs: {safe(', '.join(e['evidence_refs']))})" for e in bond['history']]
        lines += ['', '### Reported deductions', '']
        lines += [f"- {safe(c['claim_id'])}: AUD {c['amount_cents']//100}.{c['amount_cents']%100:02d}; {safe(c['reason'])}; reported claim, disputed={c['disputed']}." for c in bond['claims']] or ['- None recorded.']
        lines += ['', '### Follow-up drafts', '']
        for draft in bond['drafts']:
            lines += [f"- {draft['draft_id']}: {draft['status']}; {draft['mode']}; prepared for tenant review, not sent."]
            if draft['status'] == 'current' and bond['state'] == 'AwaitingOutcome':
                lines += ['', *['    ' + line if line else '' for line in draft['text'].splitlines()], '',
                          'Sources: ' + safe(', '.join(draft['source_refs'])), '']
        if bond['outcome']:
            lines += ['', 'Tenant-confirmed closure: ' + safe(bond['outcome'].get('outcome', bond['outcome'].get('reason'))), '']
    lines += ['## Operator review', '']
    lines += [f"- {r['review_id']}: {r['status']} — {safe(r['reason'])}; sources: {safe(', '.join(r['source_refs']))}." for r in case['reviews']] or ['- No review items.']
    lines += ['', '## Reminders', '', 'Opt-in: ' + str(case['reminders_enabled']), '']
    lines += [f"- {r['reminder_id']}: {safe(r['due_at'])} · {r['state']} · {safe(r['title'])}" for r in case['reminders']] or ['- None scheduled.']
    lines += ['', '## Evidence register', '']
    lines += [f"- {e['evidence_id']}: {safe(e['source_ref'])}, version {e['source_version']}, {safe(e['recorded_at'])}; {safe(e['summary'])}" for e in case['evidence']]
    lines += ['', '## Official information links', '',
              '- [NSW moving-out guidance](https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/ending-a-residential-tenancy/moving-out-of-a-rental-home)',
              '- [NSW bond information](https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/getting-your-bond-back)',
              '- [NSW bond dispute information](https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/residential-rental-bonds/dealing-bond-disputes-for-tenants)',
              '', '## Limits', '', 'This initial version organises tenant-reported information. It does not verify the contents of referenced files, determine legal liability, guarantee a refund, or send messages/claims.',
              'Actor IDs and the operator allowlist are local demonstration controls. M3 handoffs require a saved actual-tenancy confirmation; production authentication remains future work.', '']
    return '\n'.join(lines)


def output_paths(prefix):
    return [Path(str(prefix) + ext) for ext in ('.json', '.md')]


def check_output(prefix):
    for path in output_paths(prefix):
        require(not path.exists() and not path.is_symlink(), 'output_exists', 'Output exists; choose a new prefix')


def export_case(case, prefix):
    return export_document(case, render_markdown(case), prefix)


def export_document(document, markdown, prefix):
    check_output(prefix)
    paths = output_paths(prefix)
    paths[0].parent.mkdir(parents=True, exist_ok=True)
    contents = [json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n', markdown]
    opened = []
    try:
        # Reserve both paths exclusively before writing either; clean only files created by this call.
        for path in paths:
            opened.append((path, path.open('x', encoding='utf-8')))
        for (_, stream), content in zip(opened, contents):
            stream.write(content)
    except OSError as exc:
        for path, stream in opened:
            stream.close()
            path.unlink(missing_ok=True)
        raise AftercareError('output_error', 'Export failed; committed data can be exported again with show') from exc
    finally:
        for _, stream in opened:
            stream.close()
    return paths
