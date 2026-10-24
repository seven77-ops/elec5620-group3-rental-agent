"""Explicit chat confirmation over the ordinary source-bound lease draft service."""
from copy import copy, deepcopy
import re
from ..common import ApiError, require, shape, integer, request_id, opaque_ref, uid
from ..lease_drafts.service import LeaseDraftService
from ..lease_drafts.ai import grounded_patch, calendar_patch
from ..lease_drafts.fields import validate_fields, questions, extraction_schema, LABELS


PROPOSALS = 'assistant_lease_proposal'
RECEIPTS = 'assistant_lease_apply_receipt'
SOURCE_ERRORS = {'unconfirmed_profile', 'selection_required', 'stale_selection',
                 'legacy_selection', 'real_selection_required'}
CALL_FIELDS = {'task', 'provider', 'model', 'status', 'attempted', 'duration_ms',
               'started_at', 'usage', 'error_code', 'simulated'}


class LeaseChatBridge:
    def __init__(self, ctx):
        self.ctx = ctx
        self.leases = LeaseDraftService(ctx)

    def _conversation(self, db, case_id, conversation_id):
        self.ctx.get(db, 'case', case_id)
        conversation = self.ctx.get(db, 'assistant_conversation', conversation_id)
        require(conversation['case_id'] == case_id, 404, 'not_found', '未找到这个对话。')
        return conversation

    def _state(self, db, case_id):
        """Use the last saved current-source draft, including contract-form saves."""
        _, token = self.leases.source(db, case_id)
        index = self.ctx.repo.get(db, 'lease_draft_index', case_id) or []
        latest = None
        for item in reversed(index):
            if item['context_token'] != token:
                continue
            latest = self.leases.owned(db, case_id, item['draft_id'])
            require(latest['context_token'] == token, 409, 'draft_context_changed',
                    '草稿来源已变化，请重新读取。')
            break
        return {'context_token': token, 'draft_id': latest['draft_id'] if latest else None,
                'base_version': latest['version'] if latest else 0}, latest

    def _snapshot(self, case_id):
        # The normal service owns prefill policy. Recheck it in the same snapshot
        # as the latest draft rather than duplicating locality/followup logic.
        source = self.leases.context(case_id)
        with self.ctx.repo.transaction() as db:
            state, latest = self._state(db, case_id)
            require(source['context_token'] == state['context_token'], 409,
                    'draft_context_changed', '房源或跟进资料已变化，请重新读取。')
        fields = validate_fields(latest['fields'] if latest else source['defaults'])
        return state, fields

    def context(self, case_id):
        """Routing needs only state and missing field names, never saved contacts."""
        try:
            state, fields = self._snapshot(case_id)
        except ApiError as exc:
            if exc.code not in SOURCE_ERRORS:
                raise
            return {'status': 'missing_candidate', 'base_version': 0, 'missing_fields': []}
        return {'status': 'draft' if state['draft_id'] else 'ready',
                'base_version': state['base_version'],
                'missing_fields': [question['field'] for question in questions(fields)]}

    def _current(self, db, pending, revision):
        conversation = self._conversation(db, pending['case_id'], pending['conversation_id'])
        require(conversation['revision'] == revision, 409, 'conversation_conflict',
                '对话已更新，请重新提出租约修改。')
        state, _ = self._state(db, pending['case_id'])
        require(all(state[key] == pending[key] for key in state), 409,
                'draft_context_changed', '房源、跟进或共享草稿已变化，请重新提取并确认。')
        return conversation

    def _pending_base(self, db, conversation, state):
        """Retain only the latest still-applicable unsaved proposal in this chat."""
        current = self._conversation(db, conversation['case_id'], conversation['conversation_id'])
        require(current['revision'] == conversation['revision'], 409,
                'conversation_conflict', '对话已更新，请刷新后重试。')
        for entry in reversed(current.get('messages', [])):
            card = entry.get('lease_proposal')
            if not isinstance(card, dict):
                continue
            pending = self.ctx.repo.get(db, PROPOSALS, card.get('proposal_id', ''))
            if (pending and pending['status'] == 'pending' and
                    pending['case_id'] == current['case_id'] and
                    pending['conversation_id'] == current['conversation_id'] and
                    pending['conversation_revision'] == current['revision'] and
                    all(pending[key] == state[key] for key in state)):
                return pending
        return None

    @staticmethod
    def _public(pending, status=None):
        return {key: deepcopy(pending[key]) for key in
                ('proposal_id', 'fields', 'patch', 'questions', 'base_version')} | {
                    'status': status or pending['status']}

    def prepare(self, case_id, conversation, message):
        require(conversation.get('case_id') == case_id, 404, 'not_found', '未找到这个对话。')
        with self.ctx.repo.transaction() as db:
            current = self._conversation(db, case_id, conversation['conversation_id'])
            require(current['revision'] == conversation['revision'], 409,
                    'conversation_conflict', '对话已更新，请刷新后重试。')
        require(isinstance(message, str) and 0 < len(message.strip()) <= 3000,
                422, 'invalid_input', '描述须为1至3000字。')
        answer = {'intent': 'draft_contract', 'agent': 'agent3', 'listings': [],
                  'actions': [{'type': 'navigate', 'label': '查看租约草稿', 'page': 'contract?mode=draft'}]}
        try:
            state, fields = self._snapshot(case_id)
        except ApiError as exc:
            if exc.code not in SOURCE_ERRORS:
                raise
            answer['content'] = '请先确认当前租房偏好并保存一套真实房源候选，再准备租约草稿。已知资料可在合同助手核对，未知信息留空。'
            return {'answer': answer, 'pending': None, 'call': None}
        with self.ctx.repo.transaction() as db:
            inherited = self._pending_base(db, conversation, state)
        if inherited:
            fields = validate_fields(inherited['fields'])
        # Only the explicit current message is sent for extraction. No stored
        # party names, contacts or saved lease fields go to the external model.
        output, metadata = self.ctx.ai_provider.call({
            'task': 'lease_draft_extract', 'message': message, 'response_schema': extraction_schema()})
        # A month/day or relative date supplies no literal ISO year. Ask for it
        # instead of accepting a model-selected current/next year. All other
        # extraction candidates still pass the existing strict quote checks.
        ambiguous = []
        if isinstance(output, dict) and set(output) == {'fields'} and isinstance(output['fields'], list):
            output = deepcopy(output)
            for item in output['fields']:
                if (isinstance(item, dict) and set(item) == {'field', 'value', 'quote'} and
                        item['field'] in ('start_date', 'end_date', 'first_rent_date', 'agreement_date') and
                        isinstance(item['quote'], str) and 0 < len(item['quote']) <= 500 and item['quote'] in message and
                        isinstance(item['value'], str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', item['value']) and
                        item['value'] not in item['quote'] and not re.search(r'(?<![0-9])[0-9]{4}(?![0-9])', item['quote'])):
                    ambiguous.append(item['field'])
                    item['value'] = None
        patch = calendar_patch(grounded_patch(output, message), fields)
        try:
            combined = validate_fields({**fields, **patch})
        except ApiError:
            require(False, 502, 'ai_invalid_response', '提取内容与现有租约字段冲突，请核对日期、租期和金额。')
        latest_patch = patch
        patch = {**(inherited['patch'] if inherited else {}), **latest_patch}
        followups = [question for question in questions(combined) if question['field'] not in ambiguous]
        if inherited:
            # Preserve unresolved clarification on an unchanged saved date too.
            known_questions = {question['field'] for question in followups} | set(ambiguous)
            followups.extend(deepcopy(question) for question in inherited['questions']
                             if question['field'] not in latest_patch and question['field'] not in known_questions)
        followups.extend({'field': field, 'label': LABELS[field],
                          'question': '请明确' + LABELS[field] + '的年份，并提供 YYYY-MM-DD 日期。'}
                         for field in dict.fromkeys(ambiguous))
        pending = {'proposal_id': uid('lease-proposal'), 'case_id': case_id,
                   'conversation_id': conversation['conversation_id'],
                   'conversation_revision': conversation['revision'] + 1,
                   **state, 'fields': combined, 'patch': patch,
                   'questions': followups, 'status': 'pending'}
        with self.ctx.repo.transaction() as db:
            self._current(db, pending, conversation['revision'])
        answer['content'] = '已整理租约草稿建议。请核对完整字段、变更和待补充问题；确认适用于新州普通整租住宅后，才会保存到合同助手的共享草稿。'
        if inherited:
            answer['content'] += ' 已保留此前待确认的信息，并合并本次明确修改。'
        if ambiguous:
            answer['content'] += ' 日期尚缺明确年份，请补充 YYYY-MM-DD；本次没有猜测或更改这些日期。'
        answer['lease_proposal'] = self._public(pending)
        return {'answer': answer, 'pending': pending,
                'call': {key: value for key, value in metadata.items() if key in CALL_FIELDS}}

    def persist(self, db, pending):
        if pending is None:
            return
        self._current(db, pending, pending['conversation_revision'] - 1)
        validate_fields(pending['fields'])
        require(self.ctx.repo.get(db, PROPOSALS, pending['proposal_id']) is None,
                409, 'proposal_conflict', '此租约提案已经记录，请刷新。')
        self.ctx.repo.put(db, PROPOSALS, pending['proposal_id'], pending)

    def hydrate(self, db, conversation):
        """Return public status from stored proposals without rewriting history."""
        result = deepcopy(conversation)
        state = None
        state_loaded = False
        for entry in result.get('messages', []):
            card = entry.get('lease_proposal')
            if not isinstance(card, dict):
                continue
            pending = self.ctx.repo.get(db, PROPOSALS, card.get('proposal_id', ''))
            if not pending or pending['case_id'] != result['case_id'] or pending['conversation_id'] != result['conversation_id']:
                card['status'] = 'obsolete'
                continue
            status = pending['status']
            if status == 'pending':
                if not state_loaded:
                    try:
                        state, _ = self._state(db, result['case_id'])
                    except ApiError as exc:
                        if exc.status != 409:
                            raise
                    state_loaded = True
                if (state is None or result['revision'] != pending['conversation_revision'] or
                        any(state[key] != pending[key] for key in state)):
                    status = 'obsolete'
            card['status'] = status
        return result

    def apply(self, case_id: str, conversation_id: str, proposal_id: str, body: dict):
        shape(body, ('request_id', 'expected_revision', 'confirmed', 'applicability_confirmed'))
        request_id(body['request_id']); opaque_ref(proposal_id); opaque_ref(conversation_id)
        require(body['confirmed'] is True and body['applicability_confirmed'] is True,
                403, 'confirmation_required', '请核对信息并明确确认适用于新州普通整租住宅。')
        require(integer(body['expected_revision']), 422, 'invalid_input', '请提供当前对话版本。')
        identity = {'conversation_id': conversation_id, 'proposal_id': proposal_id, **body}
        key = case_id + ':' + body['request_id']
        # Import locally to keep the bridge usable from AssistantService itself.
        from .service import AssistantService, BorrowedRepository, message
        with self.ctx.repo.transaction() as db:
            conversation = self._conversation(db, case_id, conversation_id)
            pending = self.ctx.get(db, PROPOSALS, proposal_id)
            require(pending['case_id'] == case_id and pending['conversation_id'] == conversation_id,
                    404, 'not_found', '未找到这个租约提案。')
            old = self.ctx.receipt(db, RECEIPTS, key, identity)
            if old:
                return old['result']
            require(pending['status'] == 'pending', 409, 'proposal_applied', '此租约提案已应用，请读取当前草稿。')
            require(body['expected_revision'] == pending['conversation_revision'], 409,
                    'conversation_conflict', '对话版本已变化，请刷新后重新确认。')
            self._current(db, pending, pending['conversation_revision'])
            fields = validate_fields(pending['fields'])
            # This one field is affirmed explicitly by the applicability checkbox.
            if fields['rental_mode'] is None:
                fields['rental_mode'] = 'whole_property'
            joined = copy(self.ctx)
            joined.repo = BorrowedRepository(self.ctx.repo, db)
            save_body = {'request_id': 'chat-' + proposal_id, 'context_token': pending['context_token'],
                         'expected_version': pending['base_version'], 'confirmed': True,
                         'applicability_confirmed': True, 'fields': fields}
            if pending['draft_id']:
                save_body['draft_id'] = pending['draft_id']
            draft = LeaseDraftService(joined).save(case_id, save_body)
            pending['status'] = 'applied'
            self.ctx.repo.put(db, PROPOSALS, proposal_id, pending)
            conversation['messages'].append(message('assistant',
                '已保存共享租约草稿 v' + str(draft['version']) + '。可前往合同助手继续补充、核对并下载未签署草稿。',
                'agent3', intent='draft_contract', actions=[{
                    'type': 'navigate', 'label': '查看已保存租约草稿', 'page': 'contract?mode=draft'}]))
            conversation['revision'] += 1
            AssistantService(joined).save(db, conversation)
            result = {'draft': draft, 'conversation': self.hydrate(db, conversation)}
            self.ctx.save_receipt(db, RECEIPTS, key, identity, result)
            return result
