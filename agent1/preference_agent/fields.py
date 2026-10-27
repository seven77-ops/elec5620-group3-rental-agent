"""Draft fields and deterministic checks. No invented tenant preferences."""
from copy import deepcopy
from jsonschema import Draft202012Validator, FormatChecker
from .bridge import validator, validate_profile

PROFILE_SCHEMA = validator('RentalProfile').schema
SYSTEM_FIELDS = {'schema_version', 'search_id', 'profile_version'}
GROUPS = {'budget', 'commute', 'move_in_window', 'weights'}
FIELDS = {}
for key, spec in PROFILE_SCHEMA['properties'].items():
    if key in SYSTEM_FIELDS:
        continue
    if key in GROUPS:
        for sub, child in spec['properties'].items():
            FIELDS[f'{key}.{sub}'] = deepcopy(child)
    else:
        FIELDS[key] = deepcopy(spec)
# Preserve the original period. Conversion happens only in the displayed preview.
FIELDS['budget.period'] = {'enum': ['week', 'fortnight', 'month']}
FIELDS['preferred_locations'] = {'type': 'array', 'items': {'type': 'string', 'minLength': 1}, 'uniqueItems': True}
FIELDS['location_priority'] = {'enum': ['hard', 'soft', 'unspecified']}
FIELDS['additional_requirements'] = {
    'type': 'array', 'items': {'type': 'object', 'properties': {
        'text': {'type': 'string', 'minLength': 1},
        'priority': {'enum': ['hard', 'soft', 'unspecified']}},
        'required': ['text', 'priority'], 'additionalProperties': False}}
OPTIONAL = {'housing_preferences', 'student_commute', 'preferred_locations', 'location_priority', 'additional_requirements'}

QUESTIONS = {
    'budget.currency': 'Which currency is your budget in? Agent2 currently supports AUD only.',
    'budget.period': 'Is your budget per week, fortnight or month? Use week / fortnight / month.',
    'budget.scope': 'Is the budget per person, per room or for the whole property? Use per_person / per_room / whole_property.',
    'budget.includes_bills': 'Should the budget comparison include bills? Use true / false.',
    'budget.preferred': 'What is your preferred budget?', 'budget.maximum': 'What is your maximum budget?',
    'budget.hard_limit': 'Is the maximum budget a hard constraint? Use true for mandatory or false for negotiable.',
    'occupants': 'How many occupants will move in?', 'rental_mode': 'Do you want a whole property, private room, shared room or student accommodation?',
    'destination_id': 'What is your commute destination ID? The synthetic USYD demo destination is demo-usyd.',
    'arrival_time': 'What is your desired arrival time? Use HH:MM.',
    'timezone': 'Please confirm the commute timezone. This prototype supports Australia/Sydney.',
    'commute.modes': 'Which modes of transport are acceptable? Use public_transport / walk / drive / bike.',
    'commute.preferred_minutes': 'What is your preferred commute duration in minutes?',
    'commute.maximum_minutes': 'What is your maximum acceptable commute duration in minutes?',
    'commute.hard_limit': 'Is the maximum commute duration a hard constraint? Use true / false.',
    'move_in_window.from': 'What is your earliest move-in date? Use YYYY-MM-DD.',
    'move_in_window.to': 'What is your latest move-in date? Use YYYY-MM-DD.',
    'lease_months': 'How many months will you rent for? The minimum is 1 month.',
    'hard_requirements': 'Which facilities are mandatory? Explicitly enter [] if there are none.',
    'soft_preferences': 'Which facilities are soft preferences, and what are their weights? Explicitly enter {} if there are none.',
    'weights.commute': 'What weight should be assigned to commuting?', 'weights.cost': 'What weight should be assigned to cost?',
    'weights.housing': 'What weight should be assigned to housing facilities?', 'weights.amenities': 'What weight should be assigned to nearby amenities?',
}


def validate_value(field, value):
    if field not in FIELDS:
        raise ValueError(f'Unknown or protected field: {field}')
    if value is None:
        return  # explicitly undecided, never automatically a valid search value
    check = Draft202012Validator(FIELDS[field], format_checker=FormatChecker())
    error = next(check.iter_errors(value), None)
    if error:
        raise ValueError(f'{field}: {error.message}')


def flatten(profile):
    result = {}
    for key, value in profile.items():
        if key in SYSTEM_FIELDS:
            continue
        if key in GROUPS:
            result.update({f'{key}.{k}': v for k, v in value.items()})
        else:
            result[key] = deepcopy(value)
    return result


def profile_from(values, search_id, version):
    result = {'schema_version': '1.0', 'search_id': search_id, 'profile_version': version}
    for field in FIELDS.keys() - OPTIONAL:
        value = deepcopy(values.get(field))
        if '.' in field:
            key, sub = field.split('.')
            result.setdefault(key, {})[sub] = value
        else:
            result[field] = value
    if values.get('housing_preferences') is not None:
        result['housing_preferences'] = deepcopy(values['housing_preferences'])
    if values.get('student_commute') is not None:
        result['student_commute'] = deepcopy(values['student_commute'])
    period = result['budget']['period']
    if period in ('month', 'fortnight'):
        factor = 12 / 52 if period == 'month' else .5
        for key in ('preferred', 'maximum'):
            result['budget'][key] *= factor
        result['budget']['period'] = 'week'
    return result


def assess(draft, search_id, version):
    values = draft['values']
    errors, warnings = [], []
    for field in FIELDS:
        value = values.get(field)
        if value is None and field not in OPTIONAL:
            errors.append(f'{field}: {QUESTIONS.get(field, "Please provide this field.")}')
        else:
            try:
                validate_value(field, value)
            except ValueError as exc:
                errors.append(str(exc))
    for issue in draft['issues']:
        errors.append(f"{issue['field']}: {issue['message']}")
    areas = values.get('preferred_locations')
    if areas:
        priority = values.get('location_priority')
        if priority in (None, 'unspecified'):
            errors.append('location_priority: Please specify whether location preferences are hard or soft.')
        elif priority == 'hard':
            errors.append('preferred_locations: Agent2 does not support hard location filtering. Extend the interface or ask the tenant to explicitly revise the requirement.')
        else:
            warnings.append('Location preferences have been retained, but Agent2 does not filter or score by preferred area.')
    for item in values.get('additional_requirements') or []:
        if item['priority'] != 'soft':
            errors.append(f"additional_requirements: Unsupported requirement or unresolved priority: {item['text']}")
        else:
            warnings.append(f"Recorded soft preference not assessed by Agent2: {item['text']}")
    if values.get('rental_mode') == 'shared_room' and 'private_bedroom' in (values.get('hard_requirements') or []):
        errors.append('hard_requirements: A shared room conflicts with a mandatory private bedroom.')
    if values.get('budget.period') in ('month', 'fortnight'):
        warnings.append('The confirmation preview converts the budget to AUD/week: monthly amounts are multiplied by 12/52; fortnightly amounts are divided by 2. Original values are retained.')
    warnings.append('Agent2 uses fictional listings at a fixed assessment time. Occupant count is recorded, but the engine does not check property capacity.')
    profile = None
    if not errors:
        profile = profile_from(values, search_id, version)
        try:
            validate_profile(profile)
        except ValueError as exc:
            errors.append(str(exc))
    return {'valid': not errors, 'errors': errors, 'warnings': warnings, 'profile': profile}
