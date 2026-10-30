"""Rule-based evaluation; no network, model, database or wall-clock dependencies."""

from collections import defaultdict
from copy import deepcopy
import hashlib
import json

from .validation import DIMENSIONS, timestamp, validate_dataset, validate_profile
from .contracts import validate_contract


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def decay(value, preferred, maximum, drop):
    if value <= preferred:
        return 100.0
    if maximum == preferred:
        return 0.0
    return max(0.0, min(100.0, 100 - drop * (value - preferred) / (maximum - preferred)))


def recent(value, as_of):
    return value is not None and 0 <= (as_of - timestamp(value, 'timestamp')).total_seconds() <= 86400


def evaluate_listing(p, item, as_of, weights, duplicate_conflict=False):
    """Consume validated input; retain separate eligibility and preference scores."""
    checks, issues, evidence_used = {}, [], {}

    def check(name, value, description):
        state = 'unknown' if value is None else ('pass' if value else 'fail')
        checks[name] = {'status': state, 'reason': description}

    def fact(key):
        value = item.get(key)
        e = item.get('evidence', {}).get(key)
        if key in item.get('conflicts', []):
            issues.append(f'{key}: Conflicting source information')
            return None
        if value is None:
            issues.append(f'{key}: Missing information')
            return None
        if e is None or not recent(e['observed_at'], as_of):
            issues.append(f'{key}: Missing synthetic evidence within the valid time window')
            return None
        evidence_used[key] = deepcopy(e)
        return value

    status = fact('listing_status')
    check('availability', None if status in (None, 'unknown') else status == 'active', 'The listing must be active (synthetic status only)')
    check('freshness', True if recent(fact('last_checked_at'), as_of) else None, 'The snapshot check must not be later than evaluation time or more than 24 hours old')
    check('permission', True if fact('source_permission') is True else None, 'Data-use permission must be explicit')
    check('conflicts', None if item.get('conflicts') or duplicate_conflict else True, 'Conflicting fields or duplicate records from the same source must be checked first')
    mode = fact('rental_mode')
    check('rental_mode', None if mode is None else mode == p['rental_mode'], f"Rental mode must be {p['rental_mode']}")
    earliest, latest = fact('available_from'), fact('latest_start_date')
    window = p['move_in_window']
    overlap = None if earliest is None or latest is None else max(earliest, window['from']) <= min(latest, window['to'])
    check('move_in', overlap, f"The provider start-date range must overlap {window['from']} to {window['to']}")
    minimum = fact('minimum_lease_months')
    check('lease', None if minimum is None else minimum <= p['lease_months'], f"A {p['lease_months']}-month lease must be accepted")
    for key in p['hard_requirements']:
        check(key, fact(key), f'Must satisfy {key}')

    amount, period, scope, currency = (fact(k) for k in ('rent_amount', 'rent_period', 'rent_scope', 'currency'))
    fees = fact('mandatory_fees_weekly')
    weekly = None
    if None not in (amount, period, scope, currency, fees) and scope == p['budget']['scope'] and currency == 'AUD':
        weekly = amount * {'week': 1, 'fortnight': 0.5, 'month': 12 / 52}[period] + fees
        if p['budget']['includes_bills']:
            included = fact('bills_included')
            if included is None:
                weekly = None
            elif not included:
                bills = fact('bills_weekly')
                weekly = None if bills is None else weekly + bills
    elif scope is not None and scope != p['budget']['scope']:
        issues.append('rent_scope: Rent scopes differ; costs are not automatically divided by occupants or bedrooms')
    if p['budget']['hard_limit']:
        check('budget', None if weekly is None else weekly <= p['budget']['maximum'],
              f"Weekly cost must not exceed AUD {p['budget']['maximum']} ({p['budget']['scope']})")

    commute = fact('commute')
    precision = fact('location_precision')
    duration = None
    if commute is not None:
        matches = (commute.get('destination_id') == p['destination_id']
                   and commute.get('arrival_time') == p['arrival_time']
                   and commute.get('timezone') == p['timezone']
                   and commute.get('mode') in p['commute']['modes']
                   and precision in ('entrance', 'building')
                   and recent(commute.get('queried_at'), as_of))
        if matches:
            duration = commute.get('duration_minutes')
        else:
            issues.append('commute: Destination, time, transport mode, location precision or query freshness does not match')
    if p['commute']['hard_limit']:
        check('commute', None if duration is None else duration <= p['commute']['maximum_minutes'],
              f"Synthetic campus travel time must not exceed {p['commute']['maximum_minutes']} minutes")

    soft = {k: v for k, v in p['soft_preferences'].items() if v > 0}
    values = {k: fact(k) for k in soft}
    housing = None
    if soft and all(v is not None for v in values.values()):
        housing = sum(100 * values[k] * weight for k, weight in soft.items()) / sum(soft.values())
    distance = fact('supermarket_distance_m')
    scores = {
        'commute': None if duration is None else decay(duration, p['commute']['preferred_minutes'], p['commute']['maximum_minutes'], 60),
        'cost': None if weekly is None else decay(weekly, p['budget']['preferred'], p['budget']['maximum'], 40),
        'housing': housing,
        'amenities': None if distance is None else max(0.0, min(100.0, 100 * (1500 - distance) / 1200)),
    }
    coverage = sum(weights[k] for k in DIMENSIONS if scores[k] is not None)
    lower = sum(weights[k] * scores[k] for k in DIMENSIONS if scores[k] is not None)
    upper = lower + sum(weights[k] * 100 for k in DIMENSIONS if scores[k] is None)
    score_complete = all(scores[k] is not None for k in DIMENSIONS if weights[k] > 0)
    states = [c['status'] for c in checks.values()]
    state = 'excluded' if 'fail' in states else ('pending' if 'unknown' in states or not score_complete else 'eligible')
    reasons, tradeoffs = [], []
    if weekly is not None:
        reasons.append(f"Comparable weekly cost AUD {weekly:.2f} ({p['budget']['scope']}; {'bills included' if p['budget']['includes_bills'] else 'excluded bills are not added separately'})")
        if weekly > p['budget']['preferred']:
            tradeoffs.append(f"AUD {weekly - p['budget']['preferred']:.2f}/week above the preferred budget")
    if duration is not None:
        reasons.append(f'Synthetic campus commute {duration:g} minutes; destination {p["destination_id"]}')
        if duration > p['commute']['preferred_minutes']:
            tradeoffs.append(f"{duration - p['commute']['preferred_minutes']:g} minutes above the preferred commute")
    if distance is not None:
        reasons.append(f'Synthetic straight-line distance to the nearest supermarket: {distance:g} metres; not a walking duration')
    for key, value in values.items():
        if value is True:
            reasons.append(f'Meets soft preference {key}')
        elif value is False:
            tradeoffs.append(f'Does not meet soft preference {key}')
    return {
        'listing_id': item['listing_id'], 'status': state, 'rank': None,
        'score': round(lower, 4) if state == 'eligible' else None,
        'score_range': [round(lower, 4), round(upper, 4)] if state == 'pending' else None,
        'score_breakdown': {k: None if v is None else round(v, 4) for k, v in scores.items()},
        'evidence_coverage': round(coverage, 6), 'hard_checks': checks,
        'weekly_cost': None if weekly is None else round(weekly, 4),
        'commute_minutes': duration,
        'walking_minutes': commute.get('walking_minutes') if duration is not None else None,
        'transfers': commute.get('transfers') if duration is not None else None,
        'supermarket_distance_m': distance,
        'reasons': reasons, 'tradeoffs': tradeoffs,
        'issues': sorted(set(issues)), 'evidence_refs': evidence_used,
        'last_checked_at': item.get('last_checked_at'),
        '_sort_score': lower,
    }


def evaluate(profile, dataset, as_of=None):
    """Evaluate at an explicit snapshot, returning a reproducible JSON-compatible report."""
    validate_profile(profile)
    validate_dataset(dataset)
    as_of_text = dataset['as_of'] if as_of is None else as_of
    instant = timestamp(as_of_text, 'as_of')
    weights = dict(profile['weights'])
    if sum(profile['soft_preferences'].values()) == 0:
        weights['housing'] = 0
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}
    groups = defaultdict(list)
    for item in dataset['listings']:
        groups[(item['source'], item['source_listing_id'])].append(item)
    evaluated, duplicates = [], []
    ignored = {'listing_id', 'evidence', 'fixture_category', 'description'}
    for _, group in sorted(groups.items()):
        group = sorted(group, key=lambda row: row['listing_id'])
        signatures = {fingerprint({k: v for k, v in row.items() if k not in ignored}) for row in group}
        conflict = len(signatures) > 1
        if len(group) > 1 and not conflict:
            # Identical facts can retain the best valid evidence from either copy.
            # Keep original source_ref and observed_at; never fabricate fresh timestamps.
            merged = deepcopy(group[0])
            for row in group:
                for field, candidate in row.get('evidence', {}).items():
                    current = merged.setdefault('evidence', {}).get(field)
                    if recent(candidate['observed_at'], instant) and (
                        current is None or not recent(current['observed_at'], instant)
                        or timestamp(candidate['observed_at'], 'evidence') > timestamp(current['observed_at'], 'evidence')
                    ):
                        merged['evidence'][field] = deepcopy(candidate)
            group = [merged] + group[1:]
        for index, item in enumerate(group):
            if index > 0 and not conflict:
                duplicates.append({'listing_id': item['listing_id'], 'duplicate_of': group[0]['listing_id'],
                                   'reason': 'Same source ID and identical facts; evaluated once only'})
            else:
                evaluated.append(evaluate_listing(profile, item, instant, weights, conflict))
    eligible = sorted((r for r in evaluated if r['status'] == 'eligible'), key=lambda r: (-r['_sort_score'], r['listing_id']))
    for rank, row in enumerate(eligible, 1):
        row['rank'] = rank
    for row in evaluated:
        del row['_sort_score']
    pending = sorted((r for r in evaluated if r['status'] == 'pending'), key=lambda r: r['listing_id'])
    excluded = sorted((r for r in evaluated if r['status'] == 'excluded'), key=lambda r: r['listing_id'])
    clarification = []
    if len(eligible) < 5:
        clarification.append(f'Only {len(eligible)} listings meet all requirements. Confirm missing information, or ask Agent 1 about changing specific requirements. No requirements were relaxed automatically.')
    if pending:
        clarification.append('Confirm each unknown, expired or conflicting field in the pending list, then re-evaluate.')
    profile_hash, dataset_hash = fingerprint(profile), fingerprint(dataset)
    run_id = 'rr-' + fingerprint({'profile_fingerprint': profile_hash, 'dataset_fingerprint': dataset_hash,
                                 'as_of': as_of_text, 'scoring_version': 'rules-1.0', 'schema_version': '1.1'})
    report = {
        'schema_version': '1.1', 'scoring_version': 'rules-1.0', 'search_id': profile['search_id'],
        'recommendation_run_id': run_id, 'profile_fingerprint': profile_hash,
        'profile_version': profile['profile_version'], 'data_mode': 'synthetic_demo',
        'as_of': as_of_text, 'dataset_fingerprint': dataset_hash,
        'profile': deepcopy(profile), 'effective_weights': weights,
        'report_status': 'partial' if pending or len(eligible) < 5 else 'complete',
        'counts': {'input': len(dataset['listings']), 'eligible': len(eligible), 'pending': len(pending),
                   'excluded': len(excluded), 'duplicates': len(duplicates)},
        'recommendations': eligible[:5], 'eligible': eligible, 'pending_confirmation': pending,
        'excluded': excluded, 'duplicates': duplicates, 'clarification_requests': clarification,
        'data_limitations': ['All listings, routes, facilities and evidence are synthetic and cannot support real rental decisions.',
                             'This prototype is the deterministic Agent 2 tool core, without an LLM, listing platform or TfNSW connection.',
                             'as_of is the input snapshot time and does not establish current availability. Scores indicate preference fit, not property safety or approval to sign.',
                             'Automatic currency conversion, per-person cost division, live market valuations and future service guarantees are unsupported.'],
    }
    validate_contract('RecommendationReport', report)
    return report
