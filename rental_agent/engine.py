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
            issues.append(f'{key}：来源信息冲突')
            return None
        if value is None:
            issues.append(f'{key}：信息缺失')
            return None
        if e is None or not recent(e['observed_at'], as_of):
            issues.append(f'{key}：缺少有效时点内的模拟证据')
            return None
        evidence_used[key] = deepcopy(e)
        return value

    status = fact('listing_status')
    check('availability', None if status in (None, 'unknown') else status == 'active', '房源须为 active（仅模拟状态）')
    check('freshness', True if recent(fact('last_checked_at'), as_of) else None, '快照核对时间须不晚于评估时点且不超过24小时')
    check('permission', True if fact('source_permission') is True else None, '数据使用权限须明确')
    check('conflicts', None if item.get('conflicts') or duplicate_conflict else True, '字段或同来源重复记录冲突须先核对')
    mode = fact('rental_mode')
    check('rental_mode', None if mode is None else mode == p['rental_mode'], f"租赁方式须为 {p['rental_mode']}")
    earliest, latest = fact('available_from'), fact('latest_start_date')
    window = p['move_in_window']
    overlap = None if earliest is None or latest is None else max(earliest, window['from']) <= min(latest, window['to'])
    check('move_in', overlap, f"供方接受的起租范围须与 {window['from']} 至 {window['to']} 相交")
    minimum = fact('minimum_lease_months')
    check('lease', None if minimum is None else minimum <= p['lease_months'], f"须接受 {p['lease_months']} 个月租期")
    for key in p['hard_requirements']:
        check(key, fact(key), f'必须满足 {key}')

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
        issues.append('rent_scope：计价对象不一致；不自动按人数或卧室分摊')
    if p['budget']['hard_limit']:
        check('budget', None if weekly is None else weekly <= p['budget']['maximum'],
              f"周费用须不超过 AUD {p['budget']['maximum']}（{p['budget']['scope']}）")

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
            issues.append('commute：目的地、时段、交通模式、位置精度或查询时效不匹配')
    if p['commute']['hard_limit']:
        check('commute', None if duration is None else duration <= p['commute']['maximum_minutes'],
              f"模拟到校时间须不超过 {p['commute']['maximum_minutes']} 分钟")

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
        reasons.append(f"可比周费用 AUD {weekly:.2f}（{p['budget']['scope']}；{'含账单' if p['budget']['includes_bills'] else '不单独加入未包含的账单'}）")
        if weekly > p['budget']['preferred']:
            tradeoffs.append(f"比舒适预算高 AUD {weekly - p['budget']['preferred']:.2f}/周")
    if duration is not None:
        reasons.append(f'模拟到校通勤 {duration:g} 分钟；目的地 {p["destination_id"]}')
        if duration > p['commute']['preferred_minutes']:
            tradeoffs.append(f"比期望通勤多 {duration - p['commute']['preferred_minutes']:g} 分钟")
    if distance is not None:
        reasons.append(f'模拟最近超市直线距离 {distance:g} 米，不是步行时长')
    for key, value in values.items():
        if value is True:
            reasons.append(f'满足软偏好 {key}')
        elif value is False:
            tradeoffs.append(f'不满足软偏好 {key}')
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
                                   'reason': '同来源 ID 且事实相同，仅评估一条'})
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
        clarification.append(f'仅有 {len(eligible)} 套符合完整条件；请确认待补信息，或由 Agent 1 询问是否调整指定条件。未自动放宽条件。')
    if pending:
        clarification.append('请逐项确认待确认清单中的未知、过期或冲突字段，再重新评估。')
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
        'data_limitations': ['全部房源、路线、设施和证据均为模拟数据，不可用于真实租房决策。',
                             '本原型仅为 Agent 2 的确定性工具核心，未接入 LLM、房源平台或 TfNSW。',
                             'as_of 是输入快照时点，不代表今天仍可租；分数是偏好匹配，不是房屋安全或签约保证。',
                             '不支持自动换汇、按人数分摊、真实市场租金估值或未来班次保证。'],
    }
    validate_contract('RecommendationReport', report)
    return report
