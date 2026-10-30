"""Strict living-service input validation, without inferring unknown tenancy facts."""
from copy import deepcopy
from datetime import date
import math
import re
from ..common import require, shape, opaque_ref

UTILITIES = ('electricity', 'gas', 'internet', 'water')
TEXT_FIELDS = ('address', 'suburb', 'postcode', 'agent_name', 'agent_email', 'agent_phone',
               'emergency_phone', 'moving_to', 'own_furniture', 'landlord_furniture', 'notes')
NUMBER_FIELDS = ('bedrooms', 'bathrooms')
BOOL_FIELDS = ('carpeted', 'has_pets', 'has_elevator')
DATE_FIELDS = ('move_out_date', 'lease_start_date', 'lease_end_date')
PROFILE_FIELDS = (*TEXT_FIELDS, *NUMBER_FIELDS, *BOOL_FIELDS, *DATE_FIELDS, 'utilities')
LABELS = {'address':'Residential address', 'suburb':'Suburb', 'postcode':'Postcode', 'agent_name':'Agent name',
          'agent_email':'Agent email', 'agent_phone':'Agent phone', 'emergency_phone':'Emergency contact phone',
          'moving_to':'Moving destination', 'own_furniture':'Your furniture', 'landlord_furniture':'Landlord furniture',
          'notes':'Additional notes', 'bedrooms':'Bedrooms', 'bathrooms':'Bathrooms', 'carpeted':'Carpeted',
          'has_pets':'Pets', 'has_elevator':'Lift access', 'move_out_date':'Move-out date',
          'lease_start_date':'Actual lease start date', 'lease_end_date':'Actual lease end date',
          'electricity':'Electricity provider', 'gas':'Gas provider', 'internet':'Internet provider', 'water':'Water provider'}


def blank_profile():
    return {**{k: '' for k in TEXT_FIELDS}, **{k: None for k in (*NUMBER_FIELDS, *BOOL_FIELDS, *DATE_FIELDS)},
            'utilities': {k: None for k in UTILITIES}}


def text(value, limit=1000, required=False, single_line=False):
    require(isinstance(value, str) and len(value) <= limit and (not required or bool(value.strip()))
            and not any(ord(c) < 32 and c not in ('\n', '\t') for c in value)
            and (not single_line or not any(c in value for c in ('\n', '\t'))),
            422, 'invalid_input', 'Provide valid text. Titles and contact details cannot contain newlines or control characters.')
    return value


def day(value):
    if value is None:
        return None
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value),
            422, 'invalid_input', 'Enter a valid YYYY-MM-DD date or leave it blank.')
    try:
        date.fromisoformat(value)
    except ValueError:
        require(False, 422, 'invalid_input', 'This date does not exist. Enter a valid date.')
    return value


def provider_id(value, catalog, categories, nullable=False):
    if nullable and value is None:
        return None
    require(isinstance(value, str) and value in catalog.providers and
            bool(set(catalog.providers[value]['categories']) & set(categories)),
            422, 'invalid_provider', 'Choose a provider listed for this service category.')
    return value


def profile_values(values, catalog, partial=False):
    required = tuple(k for k in PROFILE_FIELDS if k not in ('lease_start_date', 'lease_end_date'))
    shape(values, () if partial else required, PROFILE_FIELDS if partial else ('lease_start_date', 'lease_end_date'))
    result = deepcopy(values) if partial else {**blank_profile(), **deepcopy(values)}
    for key in TEXT_FIELDS:
        if key in values:
            text(values[key], 5000 if key == 'notes' else 1000, single_line=key not in ('notes', 'own_furniture', 'landlord_furniture'))
    if 'postcode' in values:
        require(values['postcode'] == '' or re.fullmatch(r'[0-9]{4}', values['postcode']), 422, 'invalid_input', 'Enter a four-digit postcode or leave it blank.')
    if 'agent_email' in values:
        email = values['agent_email']
        require(email == '' or len(email) <= 254 and re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", email),
                422, 'invalid_input', 'Enter a valid email address or leave it blank.')
        if email:
            local, domain = email.rsplit('@', 1)
            require(len(local) <= 64 and not local.startswith('.') and not local.endswith('.') and '..' not in local
                    and all(len(label) <= 63 for label in domain.split('.')),
                    422, 'invalid_input', 'Enter a valid email address or leave it blank.')
    for key in ('agent_phone', 'emergency_phone'):
        if key in values:
            phone = values[key]
            require(phone == '' or len(phone) <= 40 and re.fullmatch(r'\+?[0-9() -]+', phone)
                    and 3 <= len(re.sub(r'\D', '', phone)) <= 15, 422, 'invalid_input', 'Enter a valid phone number or leave it blank.')
    for key in NUMBER_FIELDS:
        if key in values:
            require(values[key] is None or type(values[key]) is int and 0 <= values[key] <= 100,
                    422, 'invalid_input', 'Bedrooms and bathrooms must be integers from 0 to 100 or left blank.')
    for key in BOOL_FIELDS:
        if key in values:
            require(values[key] is None or type(values[key]) is bool, 422, 'invalid_input', 'This field must be yes, no or unknown.')
    for key in DATE_FIELDS:
        if key in values:
            day(values[key])
    require(not (result.get('lease_start_date') and result.get('lease_end_date')) or
            result['lease_end_date'] > result['lease_start_date'],
            422, 'invalid_input', 'The lease end date must be after the start date.')
    if 'utilities' in values:
        utilities = values['utilities']
        shape(utilities, () if partial else UTILITIES, UTILITIES if partial else ())
        for key, value in utilities.items():
            provider_id(value, catalog, (key,), nullable=True)
    return result


def merge_profile(current, partial):
    return {**deepcopy(current), **deepcopy(partial), 'utilities': {
        **current['utilities'], **partial.get('utilities', {})}}


def repair_values(values):
    shape(values, ('title', 'description', 'location', 'priority'), ('email_tone','email_language','property_address','recipient_name','email_draft'))
    if 'property_address' in values:
        text(values['property_address'],1000,single_line=True)
    if 'email_language' in values:
        require(values['email_language'] in ('en','zh'),422,'invalid_input','Choose a supported email language.')
        values = {**values, 'email_language':'en'}
    if 'recipient_name' in values:
        text(values['recipient_name'],200,single_line=True)
    if 'email_draft' in values:
        shape(values['email_draft'],('subject','body'))
        text(values['email_draft']['subject'],200,required=True,single_line=True)
        text(values['email_draft']['body'],8000,required=True)
    if 'email_tone' in values:
        require(values['email_tone'] in ('standard','polite','concise'), 422, 'invalid_input', 'Choose a valid email tone.')
    text(values['title'], 200, required=True, single_line=True)
    text(values['description'], 5000, required=True)
    text(values['location'], 500, single_line=True)
    require(values['priority'] in ('normal', 'urgent'), 422, 'invalid_input', 'Repair priority must be normal or urgent.')
    return deepcopy(values)


def status_values(values):
    shape(values, (), ('status', 'note', 'email_tone', 'email_language', 'email_draft'))
    if 'email_language' in values:
        require(values['email_language'] in ('en','zh'),422,'invalid_input','Choose a supported email language.')
        values = {**values, 'email_language':'en'}
    if 'email_draft' in values:
        shape(values['email_draft'],('subject','body'))
        text(values['email_draft']['subject'],200,required=True,single_line=True)
        text(values['email_draft']['body'],8000,required=True)
    require(bool(values), 422, 'invalid_input', 'Provide this repair update.')
    if 'status' in values:
        require(values['status'] in ('prepared', 'contacted', 'resolved'), 422, 'invalid_input', 'Choose a valid repair status.')
    if 'note' in values:
        text(values['note'], 3000, required=True)
    if 'email_tone' in values:
        require(values['email_tone'] in ('standard','polite','concise'), 422, 'invalid_input', 'Choose a valid email tone.')
    return deepcopy(values)


def booking_values(values, catalog):
    shape(values, ('provider_id', 'service_date', 'quote_amount', 'status', 'notes'), ('booking_id',))
    if 'booking_id' in values:
        opaque_ref(values['booking_id'])
    provider_id(values['provider_id'], catalog, ('cleaner', 'removalist'))
    day(values['service_date'])
    amount = values['quote_amount']
    require(amount is None or type(amount) in (int, float) and math.isfinite(amount) and 0 <= amount <= 1_000_000_000,
            422, 'invalid_input', 'The quote must be a valid nonnegative amount or unknown.')
    require(values['status'] in ('considering', 'contacted', 'booked', 'completed'), 422, 'invalid_input', 'Choose a valid service record status.')
    text(values['notes'], 5000)
    return deepcopy(values)


def profile_summary(values, catalog):
    lines = []
    for key, value in values.items():
        if key == 'utilities':
            for utility, identifier in value.items():
                name = catalog.providers[identifier]['name'] if identifier else 'Clear selection'
                lines.append(LABELS[utility] + ': ' + name)
        else:
            display = 'Unknown' if value is None else ('Yes' if value is True else 'No' if value is False else str(value) or 'Clear')
            lines.append(LABELS[key] + ': ' + display)
    return lines
