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
LABELS = {'address':'居住地址', 'suburb':'区域', 'postcode':'邮编', 'agent_name':'中介姓名',
          'agent_email':'中介邮箱', 'agent_phone':'中介电话', 'emergency_phone':'紧急联系电话',
          'moving_to':'搬家目的地', 'own_furniture':'自己的家具', 'landlord_furniture':'房东家具',
          'notes':'补充说明', 'bedrooms':'卧室数', 'bathrooms':'浴室数', 'carpeted':'是否有地毯',
          'has_pets':'是否有宠物', 'has_elevator':'是否有电梯', 'move_out_date':'搬出日期',
          'lease_start_date':'实际租约起始日期', 'lease_end_date':'实际租约结束日期',
          'electricity':'电力供应商', 'gas':'燃气供应商', 'internet':'网络供应商', 'water':'供水服务商'}


def blank_profile():
    return {**{k: '' for k in TEXT_FIELDS}, **{k: None for k in (*NUMBER_FIELDS, *BOOL_FIELDS, *DATE_FIELDS)},
            'utilities': {k: None for k in UTILITIES}}


def text(value, limit=1000, required=False, single_line=False):
    require(isinstance(value, str) and len(value) <= limit and (not required or bool(value.strip()))
            and not any(ord(c) < 32 and c not in ('\n', '\t') for c in value)
            and (not single_line or not any(c in value for c in ('\n', '\t'))),
            422, 'invalid_input', '请提供有效文字；标题和联系信息不能包含换行或控制字符。')
    return value


def day(value):
    if value is None:
        return None
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value),
            422, 'invalid_input', '日期须为有效的 YYYY-MM-DD 或留空。')
    try:
        date.fromisoformat(value)
    except ValueError:
        require(False, 422, 'invalid_input', '日期不存在，请重新填写。')
    return value


def provider_id(value, catalog, categories, nullable=False):
    if nullable and value is None:
        return None
    require(isinstance(value, str) and value in catalog.providers and
            bool(set(catalog.providers[value]['categories']) & set(categories)),
            422, 'invalid_provider', '请选择目录中适合该服务类别的供应商。')
    return value


def profile_values(values, catalog, partial=False):
    required = tuple(k for k in PROFILE_FIELDS if k not in ('lease_start_date', 'lease_end_date'))
    shape(values, () if partial else required, PROFILE_FIELDS if partial else ('lease_start_date', 'lease_end_date'))
    result = deepcopy(values) if partial else {**blank_profile(), **deepcopy(values)}
    for key in TEXT_FIELDS:
        if key in values:
            text(values[key], 5000 if key == 'notes' else 1000, single_line=key not in ('notes', 'own_furniture', 'landlord_furniture'))
    if 'postcode' in values:
        require(values['postcode'] == '' or re.fullmatch(r'[0-9]{4}', values['postcode']), 422, 'invalid_input', '邮编须为四位数字或留空。')
    if 'agent_email' in values:
        email = values['agent_email']
        require(email == '' or len(email) <= 254 and re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", email),
                422, 'invalid_input', '请填写有效邮箱或留空。')
        if email:
            local, domain = email.rsplit('@', 1)
            require(len(local) <= 64 and not local.startswith('.') and not local.endswith('.') and '..' not in local
                    and all(len(label) <= 63 for label in domain.split('.')),
                    422, 'invalid_input', '请填写有效邮箱或留空。')
    for key in ('agent_phone', 'emergency_phone'):
        if key in values:
            phone = values[key]
            require(phone == '' or len(phone) <= 40 and re.fullmatch(r'\+?[0-9() -]+', phone)
                    and 3 <= len(re.sub(r'\D', '', phone)) <= 15, 422, 'invalid_input', '请填写有效电话号码或留空。')
    for key in NUMBER_FIELDS:
        if key in values:
            require(values[key] is None or type(values[key]) is int and 0 <= values[key] <= 100,
                    422, 'invalid_input', '卧室和浴室数须为0至100的整数或留空。')
    for key in BOOL_FIELDS:
        if key in values:
            require(values[key] is None or type(values[key]) is bool, 422, 'invalid_input', '此条件须为是、否或未知。')
    for key in DATE_FIELDS:
        if key in values:
            day(values[key])
    require(not (result.get('lease_start_date') and result.get('lease_end_date')) or
            result['lease_end_date'] > result['lease_start_date'],
            422, 'invalid_input', '租约结束日期须晚于起始日期。')
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
    shape(values, ('title', 'description', 'location', 'priority'), ('email_tone','recipient_name','email_draft'))
    if 'recipient_name' in values:
        text(values['recipient_name'],200,single_line=True)
    if 'email_draft' in values:
        shape(values['email_draft'],('subject','body'))
        text(values['email_draft']['subject'],200,required=True,single_line=True)
        text(values['email_draft']['body'],8000,required=True)
    if 'email_tone' in values:
        require(values['email_tone'] in ('standard','polite','concise'), 422, 'invalid_input', '请选择有效的邮件语气。')
    text(values['title'], 200, required=True, single_line=True)
    text(values['description'], 5000, required=True)
    text(values['location'], 500, single_line=True)
    require(values['priority'] in ('normal', 'urgent'), 422, 'invalid_input', '维修优先级须为普通或紧急。')
    return deepcopy(values)


def status_values(values):
    shape(values, (), ('status', 'note', 'email_tone'))
    require(bool(values), 422, 'invalid_input', '请填写本次维修更新。')
    if 'status' in values:
        require(values['status'] in ('prepared', 'contacted', 'resolved'), 422, 'invalid_input', '请选择有效的维修状态。')
    if 'note' in values:
        text(values['note'], 3000, required=True)
    if 'email_tone' in values:
        require(values['email_tone'] in ('standard','polite','concise'), 422, 'invalid_input', '请选择有效的邮件语气。')
    return deepcopy(values)


def booking_values(values, catalog):
    shape(values, ('provider_id', 'service_date', 'quote_amount', 'status', 'notes'), ('booking_id',))
    if 'booking_id' in values:
        opaque_ref(values['booking_id'])
    provider_id(values['provider_id'], catalog, ('cleaner', 'removalist'))
    day(values['service_date'])
    amount = values['quote_amount']
    require(amount is None or type(amount) in (int, float) and math.isfinite(amount) and 0 <= amount <= 1_000_000_000,
            422, 'invalid_input', '报价须为有效非负金额或未知。')
    require(values['status'] in ('considering', 'contacted', 'booked', 'completed'), 422, 'invalid_input', '请选择有效的服务记录状态。')
    text(values['notes'], 5000)
    return deepcopy(values)


def profile_summary(values, catalog):
    lines = []
    for key, value in values.items():
        if key == 'utilities':
            for utility, identifier in value.items():
                name = catalog.providers[identifier]['name'] if identifier else '清空选择'
                lines.append(LABELS[utility] + '：' + name)
        else:
            display = '未知' if value is None else ('是' if value is True else '否' if value is False else str(value) or '清空')
            lines.append(LABELS[key] + '：' + display)
    return lines
