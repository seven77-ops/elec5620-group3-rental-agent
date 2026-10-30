"""Real searches retain only supplied requirements; the synthetic contract stays strict."""
from copy import deepcopy
from jsonschema import Draft202012Validator, FormatChecker
from ..common import load


SCHEMA = deepcopy(load('agent2/schemas/rental-profile.schema.json'))
SCHEMA['required'] = ['schema_version', 'search_id', 'profile_version']
for value in SCHEMA['properties'].values():
    if value.get('type') == 'object':
        value['required'] = []
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def validate_real_profile(profile):
    error = next(VALIDATOR.iter_errors(profile), None)
    if error:
        raise ValueError(f"{'.'.join(map(str,error.path))}: {error.message}")
    for group, low, high in (('budget','preferred','maximum'),
                              ('commute','preferred_minutes','maximum_minutes'),
                              ('move_in_window','from','to')):
        values = profile.get(group, {})
        if low in values and high in values and values[low] > values[high]:
            raise ValueError(f'{group}.{high}: cannot be less than {low}')
    student=profile.get('student_commute')
    if student is not None and not {'mode','maximum_minutes'}<=set(student):
        raise ValueError('Complete the travel mode and minute limit to the USYD main campus')
    hard = profile.get('hard_requirements', [])
    if set(hard) & set(profile.get('soft_preferences', {})):
        raise ValueError('The same feature cannot be both required and preferred')
    if profile.get('rental_mode') == 'shared_room' and 'private_bedroom' in hard:
        raise ValueError('Shared-room mode conflicts with a private-bedroom requirement')


def real_assess(draft, search_id, version):
    """Use Agent1's reviewed revisions and receipts with a sparse real-search contract."""
    from preference_agent.fields import validate_value
    profile = {'schema_version':'1.0','search_id':search_id,'profile_version':version}
    errors = []
    for field,value in draft['values'].items():
        if value is None:
            continue
        try:
            validate_value(field,value)
        except ValueError as exc:
            errors.append(str(exc))
        if '.' in field:
            key,sub = field.split('.',1)
            profile.setdefault(key,{})[sub] = deepcopy(value)
        elif field not in ('preferred_locations','location_priority','additional_requirements'):
            profile[field] = deepcopy(value)
    budget = profile.get('budget',{})
    if budget.get('period') in ('month','fortnight'):
        factor = 12/52 if budget['period']=='month' else .5
        for key in ('preferred','maximum'):
            if key in budget: budget[key] *= factor
        budget['period'] = 'week'
    errors.extend(f"{issue['field']}: {issue['message']}" for issue in draft['issues'])
    if not errors:
        try: validate_real_profile(profile)
        except ValueError as exc: errors.append(str(exc))
    return {'valid':not errors,'errors':errors,'warnings':[], 'profile':profile if not errors else None}


def supplied_profile(profile, legacy=True):
    """Remove legacy template leaves when no sparse origin marker exists.

    Old records cannot establish whether an unchanged demo value was user supplied.
    Chat's explicit brief/patch is merged afterwards, so genuine repeated values survive.
    Saved historical confirmations are never rewritten.
    """
    if not legacy:
        return deepcopy(profile)
    template = load('integration/agent1-to-agent2/confirmed-profile.json')
    result = {}
    for key,value in profile.items():
        if key in ('schema_version','search_id','profile_version'):
            result[key] = deepcopy(value)
        elif isinstance(value,dict) and isinstance(template.get(key),dict):
            remaining = {k:deepcopy(v) for k,v in value.items() if v != template[key].get(k)}
            if remaining: result[key] = remaining
        elif value != template.get(key):
            result[key] = deepcopy(value)
    return result
