"""Validate user-supplied facts without fetching or certifying an advertisement."""
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urlsplit
from ..common import require, shape
from .market import numeric


def instant(value):
    require(isinstance(value, str), 422, 'invalid_input', '时间须为带时区的 ISO 8601 字符串。')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        parsed = None
    require(parsed is not None and parsed.tzinfo is not None, 422, 'invalid_input', '时间必须包含有效日期和时区。')
    return parsed


def coordinates(value):
    shape(value, ('latitude', 'longitude'))
    require(numeric(value['latitude'], -90, 90) and numeric(value['longitude'], -180, 180),
            422, 'invalid_input', '请输入有效的纬度和经度；未知坐标不能用零代替。')
    return deepcopy(value)


def freshness(observed_at, at=None):
    age = ((at or datetime.now(timezone.utc)) - instant(observed_at)).total_seconds()
    require(age >= 0, 422, 'invalid_input', '观察时间不能在未来。')
    return 'within_24h' if age <= 86400 else 'older_than_24h'


def validate_listing(body):
    shape(body, ('source_url', 'address', 'postcode', 'observed_at', 'weekly_rent', 'rent_scope'),
          ('bedrooms', 'latitude', 'longitude', 'bills_included'))
    for key, limit in (('address', 300), ('source_url', 1500)):
        require(isinstance(body[key], str) and 0 < len(body[key].strip()) <= limit,
                422, 'invalid_input', '请填写有效的地址或来源链接。')
    try:
        url = urlsplit(body['source_url'])
        valid = url.scheme == 'https' and bool(url.hostname) and not url.username and not url.password
    except ValueError:
        valid = False
    require(valid and not any(c.isspace() for c in body['source_url']), 422, 'invalid_input', '来源须为不含登录信息的 HTTPS 链接。')
    postcode = body['postcode']
    require(isinstance(postcode, str) and len(postcode) == 4 and postcode.isascii() and postcode.isdigit(),
            422, 'invalid_input', '邮编须为四位数字。')
    require(numeric(body['weekly_rent'], 0, 100_000), 422, 'invalid_input', '请填写有效的周租金额。')
    require(body['rent_scope'] in ('whole_property', 'per_room', 'per_person'), 422, 'invalid_input', '请选择租金计价对象。')
    beds = body.get('bedrooms')
    require(beds is None or type(beds) is int and 0 <= beds <= 20, 422, 'invalid_input', '卧室数须为整数或留空。')
    bills = body.get('bills_included')
    require(bills is None or type(bills) is bool, 422, 'invalid_input', '账单范围须为是、否或未知。')
    lat, lon = body.get('latitude'), body.get('longitude')
    require((lat is None) == (lon is None), 422, 'invalid_input', '经纬度须同时填写或同时留空。')
    if lat is not None:
        coordinates({'latitude': lat, 'longitude': lon})
    return {**deepcopy(body), 'bedrooms': beds, 'bills_included': bills, 'latitude': lat, 'longitude': lon,
            'freshness': freshness(body['observed_at']), 'record_kind': 'real_manual_unverified',
            'evaluation_status': 'not_evaluated', 'source_permission': None}
