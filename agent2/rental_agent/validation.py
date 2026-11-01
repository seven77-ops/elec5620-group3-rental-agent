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
    require(isinstance(value, dict), path, 'Must be a JSON object')
    return value


def text(value, path):
    require(isinstance(value, str) and bool(value.strip()), path, 'Must be a nonempty string')


def number(value, path, minimum=0):
    require(type(value) in (int, float) and minimum <= value <= 1e12 and math.isfinite(value),
            path, f'Must be a finite number from {minimum} to 1e12 (not a boolean)')


def boolean(value, path):
    require(type(value) is bool, path, 'Must be true or false')


def timestamp(value, path):
    text(value, path)
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValidationError(f'{path}: An ISO 8601 timestamp is required') from exc
    require(result.tzinfo is not None, path, 'The timestamp must include a timezone offset')
    return result


def calendar_date(value, path):
    text(value, path)
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f'{path}: A valid YYYY-MM-DD date is required') from exc
    require(result.isoformat() == value, path, 'YYYY-MM-DD format is required')
    return result


def clock_time(value, path):
    text(value, path)
    try:
        result = time.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f'{path}: HH:MM is required') from exc
    require(len(value) == 5 and result.tzinfo is None, path, 'Local HH:MM is required')


def validate_profile(p):
    from .contracts import validate_contract
    validate_contract('RentalProfile', p)
    mapping(p, 'profile')
    require(p.get('schema_version') == '1.0', 'schema_version', 'Only version 1.0 is supported')
    for key in ('search_id', 'destination_id'):
        text(p.get(key), key)
    require(type(p.get('profile_version')) is int and p['profile_version'] > 0,
            'profile_version', 'Must be a positive integer')
    require(type(p.get('occupants')) is int and p['occupants'] > 0, 'occupants', 'Must be a positive integer')
    require(isinstance(p.get('rental_mode'), str) and p['rental_mode'] in MODES, 'rental_mode', 'Unsupported rental mode')
    require(p.get('timezone') == 'Australia/Sydney', 'timezone', 'This prototype supports Australia/Sydney only')
    clock_time(p.get('arrival_time'), 'arrival_time')
    budget = mapping(p.get('budget'), 'budget')
    require(budget.get('currency') == 'AUD', 'budget.currency', 'This prototype supports AUD only')
    require(budget.get('period') == 'week', 'budget.period', 'The preference budget must use week')
    require(isinstance(budget.get('scope'), str) and budget['scope'] in SCOPES, 'budget.scope', 'Unsupported rent scope')
    for key in ('includes_bills', 'hard_limit'):
        boolean(budget.get(key), f'budget.{key}')
    for key in ('preferred', 'maximum'):
        number(budget.get(key), f'budget.{key}')
    require(budget['maximum'] >= budget['preferred'], 'budget.maximum', 'Cannot be less than the preferred budget')
    commute = mapping(p.get('commute'), 'commute')
    boolean(commute.get('hard_limit'), 'commute.hard_limit')
    for key in ('preferred_minutes', 'maximum_minutes'):
        number(commute.get(key), f'commute.{key}')
    require(commute['maximum_minutes'] >= commute['preferred_minutes'], 'commute.maximum_minutes', 'Cannot be less than the preferred duration')
    require(isinstance(commute.get('modes'), list) and bool(commute['modes']), 'commute.modes', 'Must be a nonempty array')
    require(all(isinstance(m, str) and m in {'public_transport', 'walk', 'drive', 'bike'} for m in commute['modes']),
            'commute.modes', 'Unsupported transport mode')
    window = mapping(p.get('move_in_window'), 'move_in_window')
    require(calendar_date(window.get('from'), 'move_in_window.from') <= calendar_date(window.get('to'), 'move_in_window.to'),
            'move_in_window', 'Start cannot be after end')
    number(p.get('lease_months'), 'lease_months', 1)
    hard = p.get('hard_requirements')
    require(isinstance(hard, list) and all(isinstance(k, str) and k in FEATURES for k in hard),
            'hard_requirements', 'Must be an array of supported boolean feature fields')
    soft = mapping(p.get('soft_preferences'), 'soft_preferences')
    require(set(soft) <= FEATURES, 'soft_preferences', 'Contains unsupported feature fields')
    require(not set(soft).intersection(hard), 'soft_preferences', 'Required features cannot also count as scored soft preferences')
    for k, v in soft.items():
        number(v, f'soft_preferences.{k}')
    weights = mapping(p.get('weights'), 'weights')
    require(set(weights) == set(DIMENSIONS), 'weights', 'Must contain commute/cost/housing/amenities')
    for k, v in weights.items():
        number(v, f'weights.{k}')
    effective = sum(v for k, v in weights.items() if k != 'housing' or sum(soft.values()) > 0)
    require(effective > 0, 'weights', 'The effective weight sum must be greater than zero')


def validate_dataset(data):
    mapping(data, 'dataset')
    require(data.get('schema_version') == '1.0', 'dataset.schema_version', 'Only version 1.0 is supported')
    require(data.get('data_mode') == 'synthetic_demo', 'dataset.data_mode', 'This prototype supports synthetic_demo only; live data cannot be mixed in')
    timestamp(data.get('as_of'), 'dataset.as_of')
    rows = data.get('listings')
    require(isinstance(rows, list) and len(rows) <= 30, 'listings', 'Must be an array of at most 30 records')
    identifiers = set()
    for index, row in enumerate(rows):
        path = f'listings[{index}]'
        mapping(row, path)
        for key in ('listing_id', 'source', 'source_listing_id'):
            text(row.get(key), f'{path}.{key}')
        require(row['listing_id'] not in identifiers, f'{path}.listing_id', 'Duplicate internal ID')
        identifiers.add(row['listing_id'])
        require(row.get('data_kind') == 'synthetic', f'{path}.data_kind', 'Only synthetic is allowed')
        enums = {'listing_status': {'active', 'unavailable', 'unknown'}, 'rental_mode': MODES,
                 'rent_scope': SCOPES, 'rent_period': {'week', 'fortnight', 'month'},
                 'location_precision': {'entrance', 'building', 'street', 'suburb', 'unknown'},
                 'currency': {'AUD'}}
        for key, choices in enums.items():
            if row.get(key) is not None:
                require(isinstance(row[key], str) and row[key] in choices, f'{path}.{key}', 'Unsupported value')
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
            require(row['available_from'] <= row['latest_start_date'], path, 'The provider start-date range is reversed')
        conflicts = row.get('conflicts', [])
        require(isinstance(conflicts, list) and all(isinstance(k, str) for k in conflicts), f'{path}.conflicts', 'Must be an array of strings')
        evidence = mapping(row.get('evidence', {}), f'{path}.evidence')
        for key, e in evidence.items():
            ep = f'{path}.evidence.{key}'
            mapping(e, ep)
            text(e.get('source_ref'), f'{ep}.source_ref')
            require(e.get('data_kind') == 'synthetic', ep, 'Evidence must be marked synthetic')
            timestamp(e.get('observed_at'), f'{ep}.observed_at')
        route = row.get('commute')
        if route is not None:
            mapping(route, f'{path}.commute')
            require(route.get('data_kind') == 'synthetic', f'{path}.commute', 'Routes must be marked synthetic')
            for key in ('duration_minutes', 'walking_minutes', 'transfers'):
                if route.get(key) is not None:
                    number(route[key], f'{path}.commute.{key}')
            if route.get('queried_at') is not None:
                timestamp(route['queried_at'], f'{path}.commute.queried_at')
