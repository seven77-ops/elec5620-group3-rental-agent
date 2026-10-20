"""English presentation of Agent2's structured results; preserve raw evidence."""
from .bridge import validate_contract


def cell(value):
    if value is None:
        return 'Unknown'
    return str(value).replace('\\', '\\\\').replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def render_english_report(report):
    """Summarise structured values without translating or rewriting raw evidence."""
    validate_contract('RecommendationReport', report)
    counts = report['counts']
    lines = [
        '# Rental Recommendation Summary', '',
        f"Search: {cell(report['search_id'])}", '',
        f"Confirmed profile version: {report['profile_version']}", '',
        f"Recommendation run: {cell(report['recommendation_run_id'])}", '',
        f"Assessment time: {cell(report['as_of'])}", '',
        f"Report status: {cell(report['report_status'])}", '',
        '## Candidate counts', '',
        '| Input | Eligible | Pending confirmation | Excluded | Duplicates |',
        '|---:|---:|---:|---:|---:|',
        '| ' + ' | '.join(str(counts[k]) for k in ('input', 'eligible', 'pending', 'excluded', 'duplicates')) + ' |', '',
        '## Recommendations', '',
        '| Rank | Listing ID | Score |', '|---:|---|---:|',
    ]
    for row in report['recommendations']:
        lines.append(f"| {row['rank']} | {cell(row['listing_id'])} | {cell(row['score'])} |")
    if not report['recommendations']:
        lines += ['', 'No confirmed eligible candidates were found in the supplied dataset.']
    lines += ['', '## Assessment overview', '',
              '| Listing ID | Status | Score | Failed hard checks | Unknown hard checks |',
              '|---|---|---:|---|---|']
    for group in ('eligible', 'pending_confirmation', 'excluded'):
        for row in report[group]:
            failed = ', '.join(k for k, v in row['hard_checks'].items() if v['status'] == 'fail') or 'None'
            unknown = ', '.join(k for k, v in row['hard_checks'].items() if v['status'] == 'unknown') or 'None'
            lines.append('| ' + ' | '.join(cell(v) for v in
                         (row['listing_id'], row['status'], row['score'], failed, unknown)) + ' |')
    lines += ['', '## Scope and limitations', '',
              '- All listings are synthetic and assessed at a fixed time; no live availability check was performed.',
              '- Unknown scores are not zero. Pending candidates have not been confirmed eligible.',
              '- A zero-eligible result does not establish that the wider rental market has no suitable properties.',
              '- Preferred areas and unsupported soft requirements are not assessed; occupant capacity is not checked.',
              '- This English summary uses structured fields only. Original reasons and evidence remain unchanged in recommendations.json, the raw Agent2 response. Its source text may use another language.',
              '- Profile confirmation, explicit property selection and consent to process a contract are separate actions.', '']
    return '\n'.join(lines)
