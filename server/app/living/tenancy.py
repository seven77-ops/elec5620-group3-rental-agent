"""Read-only tenancy sources and explicitly confirmed, token-bound living imports."""
from copy import deepcopy
from hashlib import sha256
import re

from ..common import ApiError, integer, now, request_id, require, shape
from ..lease_drafts.service import LeaseDraftService
from ..repository import canonical
from ..settings import TENANT
from .fields import merge_profile, profile_values
from .service import LivingService


def _address(value):
    return ' '.join((value or '').casefold().split())


class LivingTenancy:
    def __init__(self, ctx):
        self.ctx = ctx
        self.living = LivingService(ctx)
        self.drafts = LeaseDraftService(ctx)

    def _accepted(self, key, value):
        if value is None or value == '' or isinstance(value, str) and not value.strip():
            return {}
        try:
            return profile_values({key: value}, self.living.catalog, partial=True)
        except ApiError:
            # A lease's free-text contact is not automatically a valid email/phone.
            return {}

    def _contacts(self, value):
        if not isinstance(value, str) or len(value) > 2000 or any(c in value for c in ('\r', '\n', '\x00')):
            return {}
        result = {}
        emails = set(re.findall(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+", value))
        if len(emails) == 1:
            result.update(self._accepted('agent_email', next(iter(emails))))
        phones = set()
        stripped = value.strip()
        if re.fullmatch(r'\+?[0-9() -]+', stripped):
            phones.add(stripped)
        # Labels prevent an unrelated date or number in free text becoming a phone.
        for match in re.finditer(r'(?:\bphone\b|\btel(?:ephone)?\b|\bmobile\b|电话|手机)\s*[:：]?\s*(\+?[0-9(][0-9() -]*)', value, re.I):
            phones.add(match.group(1).strip())
        phones = {phone for phone in phones if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', phone)}
        if len(phones) == 1:
            result.update(self._accepted('agent_phone', next(iter(phones))))
        return result

    def _draft_source(self, db, case):
        index = self.ctx.repo.get(db, 'lease_draft_index', case['case_id']) or []
        if not index:
            return None
        draft = self.drafts.owned(db, case['case_id'], index[-1]['draft_id'])
        try:
            _, current_token = self.drafts.source(db, case['case_id'])
        except ApiError:
            current_token = None
        values = {}
        fields = draft['fields']
        for destination, keys in (('address', ('address',)), ('lease_start_date', ('lease_start_date', 'start_date')),
                                  ('lease_end_date', ('lease_end_date', 'end_date'))):
            value = next((fields.get(k) for k in keys if fields.get(k) not in (None, '')), None)
            values.update(self._accepted(destination, value))
        agent_present = bool((fields.get('agent_name') or '').strip() or (fields.get('agent_contact') or '').strip())
        values.update(self._accepted('agent_name', fields.get('agent_name') if agent_present else fields.get('landlord_name')))
        values.update(self._contacts(fields.get('agent_contact') if agent_present else fields.get('landlord_contact')))
        return {'kind': 'lease_draft', 'id': draft['draft_id'], 'version': draft['version'],
                'label': '已保存租约草稿 v' + str(draft['version']), 'values': values,
                'current': current_token is not None and current_token == draft['context_token'],
                'basis': {'context_token': draft['context_token'], 'fields': fields},
                'warning': '来源是未签署租约草稿，不能据此推定已入住。请先核实并确认这是你的实际租约。'}

    def _aftercare_source(self, db, case):
        identifier = case.get('aftercare_case_id')
        if not identifier:
            return None
        mapping = self.ctx.repo.get(db, 'aftercare_mapping', identifier)
        require(mapping and mapping['case_id'] == case['case_id'], 404, 'not_found', '未找到此案例的已确认租约来源。')
        saved = self.ctx.aftercare.get(identifier, TENANT)
        tenancy = saved['tenancy']
        if tenancy.get('confirmed') is not True:
            return None
        values = self._accepted('address', tenancy.get('address'))
        if type(tenancy.get('carpeted')) is bool:
            values['carpeted'] = tenancy['carpeted']
        return {'kind': 'aftercare', 'id': identifier, 'version': tenancy['source_version'],
                'label': '已确认租后租约资料 v' + str(tenancy['source_version']), 'current': True,
                'values': values, 'basis': {'tenancy': tenancy},
                'warning': '资料来自你已确认的租约记录，请再次核对当前实际居住情况；未提供的联系信息保持未知。'}

    def _preview(self, db, case_id, record):
        case = self.ctx.get(db, 'case', case_id)
        draft = self._draft_source(db, case)
        aftercare = self._aftercare_source(db, case)
        source = draft
        if aftercare:
            new_home = (draft and draft['current'] and draft['values'].get('address') and
                        _address(draft['values']['address']) != _address(aftercare['values'].get('address')))
            source = draft if new_home else aftercare
            same_home = (draft and draft['current'] and draft['values'].get('address') and
                         _address(draft['values']['address']) == _address(aftercare['values'].get('address')))
            if same_home:
                # Confirmed tenancy facts win; only the explicitly reviewed import
                # can turn same-address draft contacts/dates into living facts.
                source['values'] = {**draft['values'], **aftercare['values']}
                source['basis']['supplementary_draft'] = {
                    'id': draft['id'], 'version': draft['version'],
                    'context_token': draft['basis']['context_token'], 'fields': draft['basis']['fields']}
                source['label'] += ' + 同地址租约草稿 v' + str(draft['version'])
                source['warning'] = ('地址和地毯信息来自已确认租约；联系人和租期来自同地址未签署草稿。'
                                     '请再次核对并确认这些是实际资料；草稿不代表已签约或已入住。')
            if new_home:
                source['warning'] = ('租约草稿地址与已确认租约地址不同，请明确确认是否已换住处。'
                                     '导入仅更新所选资料，现有水电网络、维修和服务记录都会保留。'
                                     '未签署草稿本身不代表实际入住。')
        elif draft and draft['current'] and record['profile'].get('address') and draft['values'].get('address') and \
                _address(record['profile']['address']) != _address(draft['values']['address']):
            source['warning'] = ('租约草稿地址与当前居住资料地址不同，请确认是否已换住处。'
                                 '现有水电网络、维修和服务记录都会保留；草稿本身不代表实际入住。')
        values = deepcopy(source['values']) if source else {}
        public_source = None
        if source:
            token = sha256(canonical({'case_id': case_id, 'kind': source['kind'], 'id': source['id'],
                'version': source['version'], 'basis': source['basis'], 'values': values,
                'selection': case.get('selection')}).encode()).hexdigest()
            public_source = {k: source[k] for k in ('kind', 'id', 'version', 'label', 'current', 'warning')}
            public_source['token'] = token
            if not source['current']:
                public_source['warning'] = '此草稿关联的候选、需求或跟进信息已变化，不能导入。请核对并保存当前租约草稿。'
        previous = {key: deepcopy(record['profile'].get(key)) for key in values}
        return {'expected_version': record['version'], 'source': public_source, 'values': values,
                'previous': previous, 'linked_source': deepcopy(record.get('tenancy_source')),
                'changed': any(previous[key] != value for key, value in values.items())}

    def preview(self, case_id: str):
        with self.ctx.repo.transaction() as db:
            return self._preview(db, case_id, self.living._record(db, case_id))

    def apply(self, case_id: str, body: dict):
        shape(body, ('request_id', 'expected_version', 'confirmed', 'actual_tenancy_confirmed', 'source_token', 'fields'))
        key = case_id + ':' + request_id(body['request_id'])
        require(body['confirmed'] is True and body['actual_tenancy_confirmed'] is True,
                422, 'confirmation_required', '请明确确认导入，并确认来源属于你的实际租约。')
        require(integer(body['expected_version']) and isinstance(body['source_token'], str),
                422, 'invalid_input', '请提供当前资料版本和来源标识。')
        fields = body['fields']
        require(isinstance(fields, list) and 0 < len(fields) <= 7 and all(isinstance(k, str) for k in fields)
                and len(set(fields)) == len(fields), 422, 'invalid_input', '请选择不重复的非空来源字段。')
        identity = {'operation': 'tenancy_import', 'body': body}
        with self.ctx.repo.transaction() as db:
            record = self.living._record(db, case_id)
            old = self.ctx.receipt(db, 'living_receipt', key, identity)
            if old:
                return old['result']
            preview = self._preview(db, case_id, record)
            source = preview['source']
            require(source and source['current'] and source['token'] == body['source_token'],
                    409, 'source_changed', '租约来源已变化或不属于此案例，请重新读取并核对。')
            self.living._version(record, body['expected_version'])
            require(set(fields) <= set(preview['values']), 422, 'invalid_input', '只能导入来源中已提供的非空字段。')
            partial = {key: preview['values'][key] for key in fields}
            record['profile'] = profile_values(merge_profile(record['profile'], partial), self.living.catalog)
            record['tenancy_source'] = {k: source[k] for k in ('kind', 'id', 'version', 'label', 'token')}
            record['tenancy_source'].update(fields=deepcopy(fields), actual_tenancy_confirmed=True, imported_at=now())
            return self.living._finish(db, record, key, identity)
