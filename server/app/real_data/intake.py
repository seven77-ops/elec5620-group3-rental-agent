"""Validate user-supplied facts without fetching or certifying an advertisement."""
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urlsplit
from ..common import require, shape
from .market import numeric


def instant(value):
    require(isinstance(value, str), 422, 'invalid_input', 'Time must be an ISO 8601 string with a timezone.')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        parsed = None
    require(parsed is not None and parsed.tzinfo is not None, 422, 'invalid_input', 'Time must contain a valid date and timezone.')
    return parsed


def coordinates(value):
    shape(value, ('latitude', 'longitude'))
    require(numeric(value['latitude'], -90, 90) and numeric(value['longitude'], -180, 180),
            422, 'invalid_input', 'Enter valid latitude and longitude. Do not substitute zero for unknown coordinates.')
    return deepcopy(value)


def freshness(observed_at, at=None):
    age = ((at or datetime.now(timezone.utc)) - instant(observed_at)).total_seconds()
    require(age >= 0, 422, 'invalid_input', 'Observation time cannot be in the future.')
    return 'within_24h' if age <= 86400 else 'older_than_24h'


def validate_listing(body):
    shape(body, ('source_url', 'address', 'postcode', 'observed_at', 'weekly_rent', 'rent_scope'),
          ('bedrooms', 'latitude', 'longitude', 'bills_included'))
    for key, limit in (('address', 300), ('source_url', 1500)):
        require(isinstance(body[key], str) and 0 < len(body[key].strip()) <= limit,
                422, 'invalid_input', 'Enter a valid address or source link.')
    try:
        url = urlsplit(body['source_url'])
        valid = url.scheme == 'https' and bool(url.hostname) and not url.username and not url.password
    except ValueError:
        valid = False
    require(valid and not any(c.isspace() for c in body['source_url']), 422, 'invalid_input', 'The source must be an HTTPS link without login credentials.')
    postcode = body['postcode']
    require(isinstance(postcode, str) and len(postcode) == 4 and postcode.isascii() and postcode.isdigit(),
            422, 'invalid_input', 'Postcode must contain four digits.')
    require(numeric(body['weekly_rent'], 0, 100_000), 422, 'invalid_input', 'Enter a valid weekly rent amount.')
    require(body['rent_scope'] in ('whole_property', 'per_room', 'per_person'), 422, 'invalid_input', 'Choose the rent scope.')
    beds = body.get('bedrooms')
    require(beds is None or type(beds) is int and 0 <= beds <= 20, 422, 'invalid_input', 'Bedrooms must be an integer or left blank.')
    bills = body.get('bills_included')
    require(bills is None or type(bills) is bool, 422, 'invalid_input', 'Bills inclusion must be yes, no or unknown.')
    lat, lon = body.get('latitude'), body.get('longitude')
    require((lat is None) == (lon is None), 422, 'invalid_input', 'Provide both latitude and longitude or leave both blank.')
    if lat is not None:
        coordinates({'latitude': lat, 'longitude': lon})
    return {**deepcopy(body), 'bedrooms': beds, 'bills_included': bills, 'latitude': lat, 'longitude': lon,
            'freshness': freshness(body['observed_at']), 'record_kind': 'real_manual_unverified',
            'evaluation_status': 'not_evaluated', 'source_permission': None}
