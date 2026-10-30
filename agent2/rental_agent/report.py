"""Auditable Markdown rendering and the optional preference-comparison feature."""

import html

from .validation import DIMENSIONS, ValidationError


LABELS = {'commute': 'Commute', 'cost': 'Cost', 'housing': 'Housing', 'amenities': 'Amenities'}
STATES = {'eligible': 'Eligible', 'pending': 'Pending confirmation', 'excluded': 'Excluded', 'duplicate': 'Duplicate'}


def safe(value):
    """Treat source text as text, never Markdown/HTML instructions or links."""
    value = str(value).replace('\n', ' ').replace('\r', ' ')
    # Escape each original character once; never re-escape an inserted entity.
    return ''.join(f'&#{ord(char)};' if char in '|`*_[]#\\' else html.escape(char, quote=True)
                   for char in value)


def numeric(value):
    return 'Unknown' if value is None else f'{value:.2f}'


def comparison_details(a, b, before_weights, after_weights):
    """Explain displayed assessments; never turn partial contributions into a score."""
    reasons = [f"Eligibility: {STATES[a['status']]} → {STATES[b['status']]}."]
    left_checks, right_checks = a.get('hard_checks', {}), b.get('hard_checks', {})
    check_labels = {'pass': 'Met', 'fail': 'Not met', 'unknown': 'Pending confirmation'}
    for key in sorted(left_checks.keys() | right_checks.keys()):
        left, right = left_checks.get(key), right_checks.get(key)
        if left != right:
            old = 'Disabled' if left is None else f"{check_labels[left['status']]} ({left['reason']})"
            new = 'Disabled' if right is None else f"{check_labels[right['status']]} ({right['reason']})"
            reasons.append(f'Required criterion {key}: {old} → {new}.')

    contributions = {}
    for key in DIMENSIONS:
        av, bv = a.get('score_breakdown', {}).get(key), b.get('score_breakdown', {}).get(key)
        aw, bw = before_weights[key], after_weights[key]
        # Unknown data has no contribution estimate unless its weight is zero.
        ac = 0.0 if aw == 0 else (None if av is None else round(av * aw, 4))
        bc = 0.0 if bw == 0 else (None if bv is None else round(bv * bw, 4))
        delta = None if ac is None or bc is None else round(bc - ac, 4)
        contributions[key] = {'before': ac, 'after': bc, 'change': delta}
        if a['status'] != 'duplicate' and (av != bv or aw != bw):
            change = 'Not comparable' if delta is None else f'{delta:+.4f}'
            reasons.append(f'{LABELS[key]}: component {numeric(av)} → {numeric(bv)}; '
                           f'effective weight {aw:.1%} → {bw:.1%}; '
                           f'weighted contribution {numeric(ac)} → {numeric(bc)} (change {change}).')

    if b['status'] in ('pending', 'excluded'):
        blockers = [f"{key}: {value['reason']}" for key, value in sorted(right_checks.items())
                    if value['status'] != 'pass'] + b.get('issues', [])
        if blockers:
            reasons.append('Reasons for no current rank: ' + '; '.join(dict.fromkeys(blockers)) + '.')
        reasons.append('No formal total score or rank is available. Known component contributions cannot replace a complete score.')
    elif b['status'] == 'duplicate':
        reasons.append('Duplicate records with the same source and facts are not scored or ranked independently.')
    if a['rank'] is not None and b['rank'] is not None:
        if a['rank'] == b['rank']:
            reasons.append('Rank unchanged; a total-score change does not necessarily change rank.')
        else:
            reasons.append(f"Rank {a['rank']} → {b['rank']}; ranking depends on relative scores and IDs across all eligible candidates.")
            if a['score'] == b['score']:
                reasons.append('This listing displayed total score is unchanged. Its rank change reflects eligibility and score changes among other candidates, not an increase in its own score.')
    return reasons, contributions


def compare_reports(before, after):
    """Compare all candidates, not only Top 5; do not mutate either evaluation."""
    if before['search_id'] != after['search_id']:
        raise ValidationError('comparison: Only preference versions from the same rental search can be compared')
    if any(before[key] != after[key] for key in ('dataset_fingerprint', 'as_of', 'scoring_version', 'data_mode')):
        raise ValidationError('comparison: Only the same data snapshot, timestamp and scoring version can be compared')

    def index(report):
        rows = {r['listing_id']: r for group in ('eligible', 'pending_confirmation', 'excluded') for r in report[group]}
        rows.update({r['listing_id']: {'status': 'duplicate', 'rank': None, 'score': None} for r in report['duplicates']})
        return rows

    left, right = index(before), index(after)
    rows = []
    for identifier in sorted(left.keys() | right.keys()):
        a, b = left[identifier], right[identifier]
        rank_change = None if a['rank'] is None or b['rank'] is None else a['rank'] - b['rank']
        delta = None if a['score'] is None or b['score'] is None else round(b['score'] - a['score'], 4)
        reasons, contributions = comparison_details(a, b, before['effective_weights'], after['effective_weights'])
        rows.append({'listing_id': identifier, 'before_status': a['status'], 'after_status': b['status'],
                     'before_rank': a['rank'], 'after_rank': b['rank'], 'rank_change': rank_change,
                     'before_score': a['score'], 'after_score': b['score'], 'score_change': delta,
                     'change_reasons': reasons, 'score_contributions': contributions})
    changes = []

    def diff(a, b, prefix=''):
        for key in sorted(a.keys() | b.keys()):
            path = f'{prefix}.{key}' if prefix else key
            av, bv = a.get(key), b.get(key)
            if isinstance(av, dict) and isinstance(bv, dict):
                diff(av, bv, path)
            elif av != bv:
                changes.append({'field': path, 'before': av, 'after': bv})

    diff(before['profile'], after['profile'])
    return {'before_profile_version': before['profile_version'], 'after_profile_version': after['profile_version'],
            'before_run_id': before['recommendation_run_id'], 'after_run_id': after['recommendation_run_id'],
            'before_weights': dict(before['effective_weights']), 'after_weights': dict(after['effective_weights']),
            'changed_fields': changes, 'rows': rows,
            'note': 'Rank change = previous rank minus new rank; a positive number means improvement. The comparison covers all candidates, but only eligible items have formal ranks. '
                    'Weighted contributions use displayed component scores and rounding, so their sum may differ slightly from the unrounded total. Unknown is not zero.'}


def render_markdown(report):
    p = report['profile']
    lines = ['# Sydney rental evaluation report (synthetic data)', '',
             '> Coursework demonstration only. Listings, commutes, facilities and evidence are fictional and cannot support renting or signing decisions.', '',
             f"Evaluation snapshot: {safe(report['as_of'])}; Scoring version: {safe(report['scoring_version'])}; Preference version: {p['profile_version']}.", '',
             f"Recommendation run ID: {safe(report['recommendation_run_id'])}", '',
             '## Requirements and results', '',
             f"Budget: AUD {p['budget']['preferred']:g}–{p['budget']['maximum']:g}/week, rent scope {safe(p['budget']['scope'])}; Bills included: {p['budget']['includes_bills']}.", '',
             f"Destination: {safe(p['destination_id'])}; Arrival time: {safe(p['arrival_time'])}; Preferred/maximum commute: {p['commute']['preferred_minutes']:g}/{p['commute']['maximum_minutes']:g} minutes.", '',
             'Weights: ' + ', '.join(f'{LABELS[k]} {report["effective_weights"][k]:.1%}' for k in DIMENSIONS) + '.', '',
             'Counts: ' + '; '.join(f'{k}={v}' for k, v in report['counts'].items()) + '.', '',
             '## Top 5 recommendations', '',
             '| Rank | Listing | Comparable weekly cost AUD | Synthetic commute/minutes | Supermarket straight-line distance/metres | Commute/Cost/Housing/Amenities scores | Total score |',
             '|---|---|---:|---:|---:|---|---:|']
    for row in report['recommendations']:
        scores = ' / '.join(numeric(row['score_breakdown'][k]) for k in DIMENSIONS)
        lines.append(f"| {row['rank']} | {safe(row['listing_id'])} | {numeric(row['weekly_cost'])} | {numeric(row['commute_minutes'])} | {numeric(row['supermarket_distance_m'])} | {scores} | {numeric(row['score'])} |")
    if not report['recommendations']:
        lines.extend(['', 'No candidates meet all requirements. Budget, commute and other requirements have not been relaxed automatically.'])
    for row in report['recommendations']:
        lines.extend(['', f"### {row['rank']}. {safe(row['listing_id'])}", '',
                      '- Recommendation reasons: ' + safe('; '.join(row['reasons'])),
                      f"- Synthetic route details: walking {numeric(row['walking_minutes'])} minutes; transfers {row['transfers'] if row['transfers'] is not None else 'Unknown'}. Walking is included in the total commute and is not added again.",
                      '- Tradeoffs: ' + safe('; '.join(row['tradeoffs']) or 'Known scored criteria do not exceed preferred thresholds; this does not establish that the property has no other risks.'),
                      '- Latest source check: ' + safe(row['last_checked_at'])])
    lines.extend(['', '## Pending confirmation (not formally ranked)', '',
                  '| Listing | Possible score range | Known scoring weight share | Pending required criteria / information issues |',
                  '|---|---|---:|---|'])
    for row in report['pending_confirmation']:
        why = [f"{k}: {v['reason']}" for k, v in row['hard_checks'].items() if v['status'] == 'unknown'] + row['issues']
        lines.append(f"| {safe(row['listing_id'])} | {row['score_range'][0]:.2f}–{row['score_range'][1]:.2f} | {row['evidence_coverage']:.0%} | {safe('; '.join(why))} |")
    lines.extend(['', 'Ranges reflect only possible contributions from missing scoring criteria, not statistical confidence intervals. Known weight share is not a confidence probability.', '',
                  '## Excluded', '', '| Listing | Known unmet criteria |', '|---|---|'])
    for row in report['excluded']:
        why = [f"{k}: {v['reason']}" for k, v in row['hard_checks'].items() if v['status'] == 'fail']
        lines.append(f"| {safe(row['listing_id'])} | {safe('; '.join(why))} |")
    lines.extend(['', '## Duplicate records', ''])
    lines.extend(f"- {safe(r['listing_id'])} → {safe(r['duplicate_of'])}: {safe(r['reason'])}" for r in report['duplicates'])
    if not report['duplicates']:
        lines.append('None.')
    lines.extend(['', '## Questions to confirm', ''])
    lines.extend('- ' + safe(message) for message in report['clarification_requests'])
    if not report['clarification_requests']:
        lines.append('The current synthetic snapshot has no pending items that prevent ranking.')
    if 'comparison' in report:
        comp = report['comparison']
        lines.extend(['', '## Before and after preference changes', '', safe(comp['note']), '',
                      'This report Top 5 uses the adjusted preferences. Original files are unchanged.', '',
                      '| Changed field | Before | After |', '|---|---|---|'])
        for change in comp['changed_fields']:
            lines.append(f"| {safe(change['field'])} | {safe(change['before'])} | {safe(change['after'])} |")
        lines.extend(['', '| Listing | Status change | Previous rank | New rank | Rank change | Previous score | New score | Reasons for change |',
                      '|---|---|---:|---:|---:|---:|---:|---|'])
        for row in comp['rows']:
            reasons = row.get('change_reasons', ['The older report has no reasons for change. Regenerate the comparison using the original preferences and snapshot.'])
            lines.append(f"| {safe(row['listing_id'])} | {STATES[row['before_status']]} → {STATES[row['after_status']]} | {row['before_rank'] or '—'} | {row['after_rank'] or '—'} | {row['rank_change'] if row['rank_change'] is not None else '—'} | {numeric(row['before_score'])} | {numeric(row['after_score'])} | {safe('; '.join(reasons))} |")
    lines.extend(['', '## Synthetic evidence index', '',
                  'fixture: identifies a local synthetic record, not a live webpage. Observation times and sources for used fields are also stored in evidence_refs in the corresponding JSON report.', '',
                  '| Listing | Evidence for used fields |', '|---|---|'])
    for row in report['eligible'] + report['pending_confirmation'] + report['excluded']:
        refs = '; '.join(e['source_ref'] for _, e in sorted(row['evidence_refs'].items()))
        lines.append(f"| {safe(row['listing_id'])} | {safe(refs)} |")
    lines.extend(['', '## Data limitations', ''])
    lines.extend('- ' + safe(message) for message in report['data_limitations'])
    return '\n'.join(lines) + '\n'
