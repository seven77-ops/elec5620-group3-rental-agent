"""State first; optional routing hints never grant permission to mutate business state."""
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Lock
import sqlite3

from .jev import JevError

DOMAINS = {
    'housing': {'area_advice', 'collect_preferences', 'recommend_areas', 'search', 'update_preferences',
                'compare', 'explain', 'market', 'select', 'followup', 'transit_info', 'workflow'},
    'contract': {'contract', 'draft_contract'},
    'aftercare': {'aftercare', 'living_services'},
}
ESCAPES = {'clarify', 'outside_scope', 'other'}
POLICY_VERSION = 'jev-routing-1.0'


def intent_domain(intent):
    name = intent.get('intent')
    if name == 'knowledge':
        return 'knowledge'
    return next((domain for domain, names in DOMAINS.items() if name in names), 'unclear_or_other')


class DecisionRouter:
    def __init__(self, provider, repo):
        self.provider, self.repo = provider, repo
        self._pool = None
        self._lock = Lock()
        self._slots = BoundedSemaphore(2)
        self._closed = False

    def _audit(self, audit_id, values):
        if not audit_id:
            return
        try:
            with self.repo.transaction(timeout=0) as db:
                prior = self.repo.get(db, 'routing_audit', audit_id) or {}
                self.repo.put(db, 'routing_audit', audit_id, {**prior, **values})
        except (sqlite3.Error, OSError):
            # Diagnostics must not break an otherwise valid tenant request or app shutdown.
            pass

    def observe(self, audit_id, intent, routing=None):
        metadata = {k:routing[k] for k in ('source','reason') if k in (routing or {})}
        self._audit(audit_id, {'observed_intent': intent['intent'], 'observed_domain': intent_domain(intent), **metadata})

    def _classify(self, state, audit_id):
        try:
            result = self.provider.classify(state)
            self._audit(audit_id, {'decision': result, 'decision_status': 'succeeded'})
            return result
        except JevError as error:
            self._audit(audit_id, {'decision_status': 'failed', 'error_code': error.code})
            return None

    def prepare(self, text, conversation, audit_id, explicit=None, pending=None, lease_pending=False,
                repair_active=False):
        p = self.provider
        result = {'mode': p.mode, 'source': 'ali', 'reason': 'disabled', 'direct_intent': None,
                  'allowed_intents': None, 'route': None, 'audit_id': audit_id if p.mode != 'off' else None}
        if explicit:
            result.update(source='state', reason='explicit_continuation', direct_intent=explicit)
            self._audit(result['audit_id'], {'mode': p.mode, 'source': 'state', 'reason': result['reason']})
            return result
        if p.mode == 'off':
            return result
        self._audit(audit_id, {'mode': p.mode, 'policy_version': POLICY_VERSION,
                              'min_confidence':p.min_confidence, 'min_margin':p.min_margin})
        if not p.configured:
            result['reason'] = 'not_configured'
            self._audit(audit_id, {'reason': result['reason']})
            return result
        # A pending task stays with the existing context/recovery path, even for long
        # replies. That path can still recognize a user-requested task switch.
        if pending or lease_pending or repair_active:
            result['reason'] = 'pending_task_context'
            self._audit(audit_id, {'reason': result['reason']})
            return result
        latest = next((m for m in reversed(conversation.get('messages', [])) if m.get('role') == 'assistant'), {})
        state = {'message': text, 'conversation': {
            'active_task': conversation.get('dialogue_mode'),
            'pending_question': {'task': pending.get('task'), 'fields': pending.get('fields', [])} if pending else None,
            'last_assistant_intent': latest.get('intent'), 'has_pending_lease_proposal': bool(lease_pending),
            'has_active_repair': bool(repair_active), 'has_displayed_listings': bool(latest.get('listings'))}}
        if p.mode == 'shadow':
            with self._lock:
                if self._closed or not self._slots.acquire(blocking=False):
                    result['reason'] = 'shadow_busy'
                else:
                    if self._pool is None:
                        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='jev-shadow')
                    future = self._pool.submit(self._classify, state, audit_id)
                    future.add_done_callback(lambda _: self._slots.release())
                    result['reason'] = 'shadow_scheduled'
            self._audit(audit_id, {'source': 'ali', 'reason': result['reason']})
            return result
        decision = self._classify(state, audit_id)
        if decision is None:
            result['reason'] = 'decision_failed'
            return result
        ordered = sorted(decision['probabilities'].values(), reverse=True)
        if decision['confidence'] < p.min_confidence or ordered[0] - ordered[1] < p.min_margin:
            result['reason'] = 'uncertain'
            return result
        route = decision['route']
        result.update(route=route, reason='accepted', source='jev')
        if route == 'knowledge':
            result['direct_intent'] = {'intent': 'knowledge'}
        elif route == 'mixed':
            result['direct_intent'] = {'intent': 'clarify', 'clarification_reason': 'multiple_tasks'}
        elif route in DOMAINS:
            result['allowed_intents'] = sorted(DOMAINS[route] | ESCAPES)
        else:
            result.update(source='ali', reason='unclear')
        self._audit(audit_id, {'source': result['source'], 'reason': result['reason']})
        return result

    def close(self, wait=False):
        with self._lock:
            self._closed = True
            pool = self._pool
        if pool is not None:
            pool.shutdown(wait=wait, cancel_futures=True)
