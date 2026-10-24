"""Versioned local records and confirmation proposals. No delivery or booking side effects."""
from copy import deepcopy
from ..common import now, uid, shape, integer, request_id, opaque_ref, require
from .catalog import ProviderCatalog
from .repairs import add_repair, update_repair, STATUS_LABELS, TONE_LABELS
from .fields import (blank_profile, profile_values, merge_profile, repair_values,
                     status_values, booking_values, text, profile_summary)


class LivingService:
    def __init__(self, ctx, providers=None):
        self.ctx = ctx
        self.catalog = ProviderCatalog(providers)

    def directory(self):
        return self.catalog.directory()

    def _record(self, db, case_id):
        self.ctx.get(db, 'case', case_id)
        record = self.ctx.repo.get(db, 'living_services', case_id) or {
            'case_id': case_id, 'version': 0, 'profile': blank_profile(),
            'repairs': [], 'bookings': [], 'updated_at': None}
        record['profile'] = merge_profile(blank_profile(), record['profile'])
        return record

    def read(self, case_id: str):
        with self.ctx.repo.transaction() as db:
            return self._record(db, case_id)

    def _envelope(self, body, values=True):
        shape(body, ('request_id', 'expected_version', 'confirmed', *(['values'] if values else [])))
        request_id(body['request_id'])
        require(integer(body['expected_version']), 422, 'invalid_input', '请提供有效资料版本。')
        require(body['confirmed'] is True, 422, 'confirmation_required', '请明确确认此次保存。')

    def _version(self, record, version):
        require(record['version'] == version, 409, 'version_conflict', '资料已变化，请重新读取后确认。')

    def _finish(self, db, record, key, identity):
        record['version'] += 1
        record['updated_at'] = now()
        self.ctx.repo.put(db, 'living_services', record['case_id'], record)
        self.ctx.save_receipt(db, 'living_receipt', key, identity, record)
        return record

    def _mutate(self, case_id, body, operation, action):
        self._envelope(body)
        key = case_id + ':' + body['request_id']
        identity = {'operation': operation, 'body': body}
        with self.ctx.repo.transaction() as db:
            record = self._record(db, case_id)
            old = self.ctx.receipt(db, 'living_receipt', key, identity)
            if old:
                return old['result']
            self._version(record, body['expected_version'])
            action(record, body['values'])
            return self._finish(db, record, key, identity)

    def profile(self, case_id: str, body: dict):
        def save(record, values):
            validated = profile_values(values, self.catalog)
            for key in ('lease_start_date', 'lease_end_date'):
                if key not in values:
                    validated[key] = record['profile'].get(key)
            record['profile'] = profile_values(validated, self.catalog)
        return self._mutate(case_id, body, 'profile', save)

    def _add_repair(self, record, values):
        return add_repair(record, values)

    def repair(self, case_id: str, body: dict):
        return self._mutate(case_id, body, 'repair', self._add_repair)

    def update_repair(self, case_id: str, repair_id: str, body: dict):
        opaque_ref(repair_id)
        return self._mutate(case_id, body, 'repair:' + repair_id,
                            lambda record, values: update_repair(record, repair_id, values))

    def booking(self, case_id: str, body: dict):
        def save(record, values):
            values = booking_values(values, self.catalog)
            booking_id = values.get('booking_id')
            if booking_id is not None:
                opaque_ref(booking_id)
                entry = next((b for b in record['bookings'] if b['booking_id'] == booking_id), None)
                require(entry is not None, 404, 'not_found', '未找到此案例的服务记录。')
                entry.update(values, updated_at=now())
            else:
                record['bookings'].append({**values, 'booking_id': uid('booking'), 'created_at': now()})
        return self._mutate(case_id, body, 'booking', save)

    def prepare_proposal(self, case_id, kind, values, source_message):
        require(kind in ('profile', 'repair', 'repair_update'), 422, 'invalid_input', '不支持此建议类型。')
        text(source_message, 12000)
        with self.ctx.repo.transaction() as db:
            record = self._record(db, case_id)
            if kind == 'profile':
                values = profile_values(values, self.catalog, partial=True)
                require(bool(values), 422, 'invalid_input', '资料建议不能为空。')
                summary = [*profile_summary(values, self.catalog), '仅在你确认后保存；未填写的信息保持原值。']
            elif kind == 'repair_update':
                shape(values, ('repair_id',), ('status', 'note', 'email_tone'))
                opaque_ref(values['repair_id'])
                entry = next((r for r in record['repairs'] if r['repair_id'] == values['repair_id']), None)
                require(entry is not None, 404, 'not_found', '未找到此案例的维修记录。')
                patch = status_values({k:v for k,v in values.items() if k != 'repair_id'})
                summary = ['更新报修：' + entry['title']]
                if 'status' in patch: summary.append('状态：' + STATUS_LABELS[patch['status']])
                if 'note' in patch: summary.append('用户记录：' + patch['note'])
                if 'email_tone' in patch: summary.append('邮件语气：' + TONE_LABELS[patch['email_tone']] + '；保留原来的事实和收件人。')
                summary.append('确认后更新同一条报修；不会发送邮件。')
            else:
                values = repair_values(values)
                summary = ['准备维修邮件：' + values['title'], '位置：' + (values['location'] or '待补充'),
                           '情况描述：' + values['description'],
                           '优先级：' + ('紧急' if values['priority'] == 'urgent' else '普通'),
                           '收件人：' + (record['profile']['agent_email'] or '待补充'),
                           '邮件语气：' + TONE_LABELS[values.get('email_tone','standard')],
                           '仅生成本地草稿，不会发送邮件。']
            proposal = {'proposal_id': uid('living-proposal'), 'case_id': case_id, 'kind': kind,
                        'values': values, 'summary': summary, 'expected_version': record['version'],
                        'source_message': source_message, 'status': 'pending', 'created_at': now()}
            self.ctx.repo.put(db, 'living_proposal', proposal['proposal_id'], proposal)
            return {k: deepcopy(proposal[k]) for k in ('proposal_id', 'kind', 'summary', 'expected_version', 'status')}

    def apply(self, case_id: str, proposal_id: str, body: dict):
        self._envelope(body, values=False)
        opaque_ref(proposal_id)
        key = case_id + ':' + body['request_id']
        identity = {'operation': 'apply:' + proposal_id, 'body': body}
        with self.ctx.repo.transaction() as db:
            record = self._record(db, case_id)
            proposal = self.ctx.get(db, 'living_proposal', proposal_id)
            require(proposal['case_id'] == case_id, 404, 'not_found', '未找到此案例的建议。')
            old = self.ctx.receipt(db, 'living_receipt', key, identity)
            if old:
                return old['result']
            require(proposal['status'] == 'pending', 409, 'proposal_applied', '此建议已经确认保存。')
            self._version(record, body['expected_version'])
            require(proposal['expected_version'] == body['expected_version'], 409, 'version_conflict', '建议基于旧资料，请重新生成并确认。')
            if proposal['kind'] == 'profile':
                record['profile'] = profile_values(merge_profile(record['profile'], proposal['values']), self.catalog)
            elif proposal['kind'] == 'repair_update':
                values = proposal['values']
                update_repair(record, values['repair_id'], {k:v for k,v in values.items() if k != 'repair_id'})
                proposal['result_repair_id'] = values['repair_id']
            else:
                proposal['result_repair_id'] = self._add_repair(record, proposal['values'])
            proposal.update(status='applied', applied_at=now())
            self.ctx.repo.put(db, 'living_proposal', proposal_id, proposal)
            return self._finish(db, record, key, identity)
