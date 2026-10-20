"""Compare saved confirmed versions on one snapshot; never replace stored reports."""
from copy import deepcopy
import json
from .bridge import compare_reports, evaluate, fingerprint
from .handover import check_record, check_report
from .report import cell


def task_history(store, case_id):
    session, _ = store.load(case_id)
    rows = []
    for task in store.tasks(case_id):
        if task['version'] != session['latest_version'] or task['task_id'] != session['latest_task_id']:
            binding = 'historical'
        elif session['state'] != 'Confirmed':
            binding = 'outdated_for_current_draft'
        else:
            binding = 'current_confirmed_version'
        rows.append({'task_id': task['task_id'], 'profile_version': task['version'],
                     'status': task['status'], 'binding': binding,
                     'recommendation_run_id': (task.get('report') or {}).get('recommendation_run_id')})
    return rows


def verified_report(store, case_id, task):
    if task['case_id'] != case_id or task['status'] != 'completed' or not task.get('report'):
        raise ValueError('Comparison requires completed tasks from this case.')
    record = store.profile(case_id, task['version'])
    check_record(record)
    if (task['search_id'] != record['searchId'] or task['profile_hash'] != fingerprint(record['profile'])
            or task['dataset_hash'] != fingerprint(task['dataset'])):
        raise ValueError('Stored task references or fingerprints do not match.')
    check_report(task['report'], record, task['dataset'])
    if task['report'] != evaluate(record['profile'], task['dataset']):
        raise ValueError('Stored report differs from the reproducible local evaluation.')
    return deepcopy(task['report'])


def compare_tasks(store, case_id, before_id, after_id):
    before_task, after_task = store.task(before_id), store.task(after_id)
    before = verified_report(store, case_id, before_task)
    after = verified_report(store, case_id, after_task)
    if before['profile_version'] >= after['profile_version']:
        raise ValueError('Choose an earlier confirmed version as the comparison baseline.')
    raw = compare_reports(before, after)
    return {'before_task_id': before_id, 'after_task_id': after_id,
            'search_id': after['search_id'], 'dataset_fingerprint': after['dataset_fingerprint'],
            'as_of': after['as_of'], 'raw_comparison': raw,
            'english_comparison': english_comparison(raw, before, after)}


def compare_current(store, case_id, before_version=None, optional=False):
    session, _ = store.load(case_id)
    if session['state'] != 'Confirmed':
        raise ValueError('Confirm the current draft before comparing its recommendations.')
    if not session['latest_task_id']:
        if optional:
            return None
        raise ValueError('Run /search for the current confirmed version before comparing.')
    current = store.task(session['latest_task_id'])
    if current['version'] != session['latest_version'] or current['status'] != 'completed':
        raise ValueError('The current confirmed version has no completed recommendation report.')
    if before_version is not None and (before_version < 1 or before_version >= session['latest_version']):
        raise ValueError('Baseline must be an earlier confirmed profile version.')
    candidates = [t for t in store.tasks(case_id)
                  if t['version'] < current['version'] and t['status'] == 'completed'
                  and (before_version is None or t['version'] == before_version)]
    matches = [t for t in candidates if t['dataset_hash'] == current['dataset_hash']]
    if not matches:
        if candidates:
            raise ValueError('Earlier reports use a different data snapshot; comparison is unavailable.')
        if optional:
            return None
        raise ValueError('No completed earlier report exists for this comparison.')
    baseline = max(matches, key=lambda t: t['version'])
    result = compare_tasks(store, case_id, baseline['task_id'], current['task_id'])
    latest, _ = store.load(case_id)
    if (latest['state'] != 'Confirmed' or latest['latest_version'] != session['latest_version']
            or latest['latest_task_id'] != current['task_id']):
        raise ValueError('Current preferences changed during comparison. Review the latest version.')
    return result


def english_comparison(raw, before, after):
    """English reasons from structured fields, retaining the raw upstream reasons separately."""
    result = deepcopy(raw)
    result['note'] = ('Rank change = previous rank minus new rank. Only eligible candidates have a formal '
                      'score and rank. Unknown values are not zero. Rounded dimension contributions '
                      'may differ slightly from the total score. Raw upstream reasons are in comparison.json.')
    def index(report):
        return {r['listing_id']: r for g in ('eligible', 'pending_confirmation', 'excluded') for r in report[g]}
    left, right = index(before), index(after)
    profile_changes = [x for x in raw['changed_fields'] if x['field'] != 'profile_version']
    for row in result['rows']:
        a, b = left.get(row['listing_id'], {}), right.get(row['listing_id'], {})
        reasons = [f"Eligibility: {row['before_status']} -> {row['after_status']}."]
        ac, bc = a.get('hard_checks', {}), b.get('hard_checks', {})
        for name in sorted(ac.keys() | bc.keys()):
            if ac.get(name) != bc.get(name):
                reasons.append(f"Hard check {name}: {ac.get(name, {}).get('status', 'inactive')} -> "
                               f"{bc.get(name, {}).get('status', 'inactive')}; the check outcome or evidence changed.")
        for name, contribution in row['score_contributions'].items():
            if (a.get('score_breakdown', {}).get(name) != b.get('score_breakdown', {}).get(name)
                    or raw['before_weights'][name] != raw['after_weights'][name]):
                reasons.append(f"{name}: effective weight {raw['before_weights'][name]:.1%} -> "
                               f"{raw['after_weights'][name]:.1%}; weighted contribution "
                               f"{cell(contribution['before'])} -> {cell(contribution['after'])}.")
        if row['after_status'] in ('pending', 'excluded'):
            blockers = ', '.join(f"{k}={v['status']}" for k, v in bc.items() if v['status'] != 'pass')
            missing = ', '.join(k for k, v in b.get('score_breakdown', {}).items()
                                if v is None and after['effective_weights'][k] > 0)
            reasons.append(f"No formal score or rank. Hard-check blockers: {blockers or 'none'}; "
                           f"unknown positively weighted dimensions: {missing or 'none'}.")
        elif row['after_status'] == 'duplicate':
            reasons.append('Duplicate source record; no separate score or rank.')
        if row['before_rank'] is not None and row['after_rank'] is not None:
            reasons.append(f"Rank: {row['before_rank']} -> {row['after_rank']}. Ranking is relative to all eligible candidates.")
            if row['rank_change'] and row['score_change'] == 0:
                reasons.append('Own total score is unchanged; inspect changes in other candidates.')
        if row['before_status'] != row['after_status']:
            for change in profile_changes:
                reasons.append('Confirmed input change: ' + change['field'] + ': '
                               + json.dumps(change['before'], ensure_ascii=False) + ' -> '
                               + json.dumps(change['after'], ensure_ascii=False) + '.')
        row['change_reasons'] = reasons
    return result


def render_comparison(bundle):
    comparison = bundle['english_comparison']
    lines = ['# Recommendation Version Comparison', '',
             f"Search: {cell(bundle['search_id'])}", '',
             f"Versions: {comparison['before_profile_version']} -> {comparison['after_profile_version']}", '',
             f"Assessment time: {cell(bundle['as_of'])}", '', comparison['note'], '',
             '## Confirmed input changes', '', '| Field | Before | After |', '|---|---|---|']
    for change in comparison['changed_fields']:
        lines.append('| ' + ' | '.join(cell(change[k]) for k in ('field', 'before', 'after')) + ' |')
    lines += ['', '## All candidates', '',
              '| Listing | Eligibility before / after | Rank before / after | Score before / after | Change reasons |',
              '|---|---|---|---|---|']
    for row in comparison['rows']:
        lines.append('| ' + ' | '.join(cell(v) for v in (
            row['listing_id'], f"{row['before_status']} -> {row['after_status']}",
            f"{cell(row['before_rank'])} -> {cell(row['after_rank'])}",
            f"{cell(row['before_score'])} -> {cell(row['after_score'])}",
            ' '.join(row['change_reasons']))) + ' |')
    lines += ['', '## Dimension contributions', '',
              '| Listing | Dimension | Before | After | Change |', '|---|---|---:|---:|---:|']
    for row in comparison['rows']:
        for dimension, values in row['score_contributions'].items():
            lines.append('| ' + ' | '.join(cell(v) for v in
                         (row['listing_id'], dimension, values['before'], values['after'], values['change'])) + ' |')
    return '\n'.join(lines) + '\n'
