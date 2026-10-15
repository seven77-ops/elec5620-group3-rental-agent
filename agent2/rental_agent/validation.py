"""Input contract validation. Unknown facts remain None; malformed facts fail fast."""

from datetime import date, datetime, time
import math


DIMENSIONS = ('commute', 'cost', 'housing', 'amenities')
FEATURES = {'private_bedroom', 'private_bathroom', 'furnished', 'laundry', 'kitchen_access'}
MODES = {'whole_property', 'private_room', 'shared_room', 'student_accommodation'}
SCOPES = {'per_person', 'per_room', 'whole_property'}


class ValidationError(ValueError):
    """A user-readable input error including the offending field path."""


def require(condition, path, message):
    if not condition:
        raise ValidationError(f'{path}: {message}')


def mapping(value, path):
    require(isinstance(value, dict), path, '必须是 JSON 对象')
    return value


def text(value, path):
    require(isinstance(value, str) and bool(value.strip()), path, '必须是非空字符串')


def number(value, path, minimum=0):
    require(type(value) in (int, float) and minimum <= value <= 1e12 and math.isfinite(value),
            path, f'必须是 {minimum} 至 1e12 范围的有限数字（不是布尔值）')


def boolean(value, path):
    require(type(value) is bool, path, '必须是 true 或 false')


def timestamp(value, path):
    text(value, path)
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValidationError(f'{path}: 需要 ISO 8601 时间') from exc
    require(result.tzinfo is not None, path, '时间必须包含时区偏移')
    return result


def calendar_date(value, path):
    text(value, path)
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f'{path}: 需要有效的 YYYY-MM-DD 日期') from exc
    require(result.isoformat() == value, path, '需要 YYYY-MM-DD 格式')
    return result


def clock_time(value, path):
    text(value, path)
    try:
        result = time.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f'{path}: 需要 HH:MM') from exc
    require(len(value) == 5 and result.tzinfo is None, path, '需要本地 HH:MM')


def validate_profile(p):
    from .contracts import validate_contract
    validate_contract('RentalProfile', p)
    mapping(p, 'profile')
    require(p.get('schema_version') == '1.0', 'schema_version', '仅支持 1.0')
    for key in ('search_id', 'destination_id'):
        text(p.get(key), key)
    require(type(p.get('profile_version')) is int and p['profile_version'] > 0,
            'profile_version', '必须是正整数')
    require(type(p.get('occupants')) is int and p['occupants'] > 0, 'occupants', '必须是正整数')
    require(isinstance(p.get('rental_mode'), str) and p['rental_mode'] in MODES, 'rental_mode', '不支持的租赁方式')
    require(p.get('timezone') == 'Australia/Sydney', 'timezone', '原型仅支持 Australia/Sydney')
    clock_time(p.get('arrival_time'), 'arrival_time')
    budget = mapping(p.get('budget'), 'budget')
    require(budget.get('currency') == 'AUD', 'budget.currency', '原型仅支持 AUD')
    require(budget.get('period') == 'week', 'budget.period', '偏好预算须按 week 输入')
    require(isinstance(budget.get('scope'), str) and budget['scope'] in SCOPES, 'budget.scope', '不支持的计价对象')
    for key in ('includes_bills', 'hard_limit'):
        boolean(budget.get(key), f'budget.{key}')
    for key in ('preferred', 'maximum'):
        number(budget.get(key), f'budget.{key}')
    require(budget['maximum'] >= budget['preferred'], 'budget.maximum', '不能小于舒适预算')
    commute = mapping(p.get('commute'), 'commute')
    boolean(commute.get('hard_limit'), 'commute.hard_limit')
    for key in ('preferred_minutes', 'maximum_minutes'):
        number(commute.get(key), f'commute.{key}')
    require(commute['maximum_minutes'] >= commute['preferred_minutes'], 'commute.maximum_minutes', '不能小于期望时间')
    require(isinstance(commute.get('modes'), list) and bool(commute['modes']), 'commute.modes', '须为非空数组')
    require(all(isinstance(m, str) and m in {'public_transport', 'walk', 'drive', 'bike'} for m in commute['modes']),
            'commute.modes', '不支持的交通模式')
    window = mapping(p.get('move_in_window'), 'move_in_window')
    require(calendar_date(window.get('from'), 'move_in_window.from') <= calendar_date(window.get('to'), 'move_in_window.to'),
            'move_in_window', '开始不能晚于结束')
    number(p.get('lease_months'), 'lease_months', 1)
    hard = p.get('hard_requirements')
    require(isinstance(hard, list) and all(isinstance(k, str) and k in FEATURES for k in hard),
            'hard_requirements', '须为支持的布尔设施字段数组')
    soft = mapping(p.get('soft_preferences'), 'soft_preferences')
    require(set(soft) <= FEATURES, 'soft_preferences', '包含不支持的设施字段')
    require(not set(soft).intersection(hard), 'soft_preferences', '硬条件设施不能重复作为软偏好计分')
    for k, v in soft.items():
        number(v, f'soft_preferences.{k}')
    weights = mapping(p.get('weights'), 'weights')
    require(set(weights) == set(DIMENSIONS), 'weights', '必须包含 commute/cost/housing/amenities')
    for k, v in weights.items():
        number(v, f'weights.{k}')
    effective = sum(v for k, v in weights.items() if k != 'housing' or sum(soft.values()) > 0)
    require(effective > 0, 'weights', '有效权重总和必须大于零')


def validate_dataset(data):
    mapping(data, 'dataset')
    require(data.get('schema_version') == '1.0', 'dataset.schema_version', '仅支持 1.0')
    require(data.get('data_mode') == 'synthetic_demo', 'dataset.data_mode', '原型仅支持 synthetic_demo；禁止真实数据混入')
    timestamp(data.get('as_of'), 'dataset.as_of')
    rows = data.get('listings')
    require(isinstance(rows, list) and len(rows) <= 30, 'listings', '必须是最多30条记录的数组')
    identifiers = set()
    for index, row in enumerate(rows):
        path = f'listings[{index}]'
        mapping(row, path)
        for key in ('listing_id', 'source', 'source_listing_id'):
            text(row.get(key), f'{path}.{key}')
        require(row['listing_id'] not in identifiers, f'{path}.listing_id', '内部 ID 重复')
        identifiers.add(row['listing_id'])
        require(row.get('data_kind') == 'synthetic', f'{path}.data_kind', '只允许 synthetic')
        enums = {'listing_status': {'active', 'unavailable', 'unknown'}, 'rental_mode': MODES,
                 'rent_scope': SCOPES, 'rent_period': {'week', 'fortnight', 'month'},
                 'location_precision': {'entrance', 'building', 'street', 'suburb', 'unknown'},
                 'currency': {'AUD'}}
        for key, choices in enums.items():
            if row.get(key) is not None:
                require(isinstance(row[key], str) and row[key] in choices, f'{path}.{key}', '不支持的取值')
        for key in FEATURES | {'bills_included', 'source_permission'}:
            if row.get(key) is not None:
                boolean(row[key], f'{path}.{key}')
        for key in ('rent_amount', 'bills_weekly', 'mandatory_fees_weekly', 'supermarket_distance_m', 'minimum_lease_months'):
            if row.get(key) is not None:
                number(row[key], f'{path}.{key}')
        if row.get('last_checked_at') is not None:
            timestamp(row['last_checked_at'], f'{path}.last_checked_at')
        for key in ('available_from', 'latest_start_date'):
            if row.get(key) is not None:
                calendar_date(row[key], f'{path}.{key}')
        if row.get('available_from') and row.get('latest_start_date'):
            require(row['available_from'] <= row['latest_start_date'], path, '供方起租日期范围颠倒')
        conflicts = row.get('conflicts', [])
        require(isinstance(conflicts, list) and all(isinstance(k, str) for k in conflicts), f'{path}.conflicts', '必须是字符串数组')
        evidence = mapping(row.get('evidence', {}), f'{path}.evidence')
        for key, e in evidence.items():
            ep = f'{path}.evidence.{key}'
            mapping(e, ep)
            text(e.get('source_ref'), f'{ep}.source_ref')
            require(e.get('data_kind') == 'synthetic', ep, '证据必须标记 synthetic')
            timestamp(e.get('observed_at'), f'{ep}.observed_at')
        route = row.get('commute')
        if route is not None:
            mapping(route, f'{path}.commute')
            require(route.get('data_kind') == 'synthetic', f'{path}.commute', '路线必须标记 synthetic')
            for key in ('duration_minutes', 'walking_minutes', 'transfers'):
                if route.get(key) is not None:
                    number(route[key], f'{path}.commute.{key}')
            if route.get('queried_at') is not None:
                timestamp(route['queried_at'], f'{path}.commute.queried_at')
