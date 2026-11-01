"""Adapt public Agent1 services; preserve their state machine and persisted receipts."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

from ..bootstrap import ROOT  # Initialize sibling package paths first.
from ..common import require
from ..settings import TENANT
from preference_agent.store import Store
from preference_agent.service import PreferenceAgent, ProfileService
from preference_agent.llm import ManualOnly
from preference_agent.fields import flatten
from preference_agent.handover import HandoverService
from preference_agent.comparison import compare_current
from rental_agent.engine import fingerprint


class _BorrowedConnection:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *_):
        return False  # The owning adapter transaction alone commits/rolls back.


class JoinedStore(Store):
    """Join profile changes to the adapter transaction without changing Agent1 code.

    Outside join(), member task acceptance/completion use their original independent
    transactions. ContextVar prevents concurrent HTTP worker threads sharing a join.
    """
    def __init__(self, path):
        self._joined = ContextVar('agent1_connection', default=None)
        super().__init__(path)

    def connect(self):
        connection = self._joined.get()
        return _BorrowedConnection(connection) if connection is not None else super().connect()

    @contextmanager
    def transaction(self):
        connection = self._joined.get()
        if connection is not None:
            yield connection
        else:
            with super().transaction() as db:
                yield db

    @contextmanager
    def join(self, connection):
        token = self._joined.set(connection)
        try:
            yield self
        finally:
            self._joined.reset(token)


class _PrepareOnly:
    """Reserve via Agent1's public handover API; acknowledge nothing yet."""
    def __init__(self, store):
        self.store = store

    def routeTask(self, task_id):
        return self.store.task(task_id)


class Agent1Bridge:
    def __init__(self, repository, real=False):
        self.real = real
        self.store = JoinedStore(repository.database)
        self.agent = PreferenceAgent(self.store, ManualOnly())
        if real:
            class RealProfileService(ProfileService):
                def validateDraft(self, session):
                    from ..real_data.profile import real_assess
                    return real_assess(session['draft'],session['search_id'],session['latest_version']+1)
            self.agent.profiles = RealProfileService(self.store)
        self.preparer = HandoverService(self.store, receiver=_PrepareOnly(self.store))
        self.handover = HandoverService(self.store)

    def require_case(self, case):
        require(bool(case.get('agent1_case_id')), 409, 'agent1_upgrade_required',
                'This legacy form-only case remains readable. Start a new case to use Agent1 preferences.')
        return case['agent1_case_id']

    def metadata(self, case):
        session, _ = self.store.load(self.require_case(case))
        case['agent1'] = {
            'case_id': session['case_id'], 'session_id': session['session_id'],
            'state': session['state'], 'latest_version': session['latest_version'],
            'review_token': (session.get('review') or {}).get('token'),
            'draft_revision': session['draft']['revision'],
            'warnings': self.agent.profiles.validateDraft(session)['warnings'],
            'input_mode': 'manual_form', 'live_llm': False,
        }
        return session

    def start(self, case_id, template):
        session = self.agent.startCollection()
        case = {'case_id': case_id, 'search_id': session['search_id'],
                'agent1_case_id': session['case_id'], 'confirmations': [], 'evaluations': [],
                'selection': None, 'reviews': [], 'aftercare_case_id': None}
        if self.real: case['requirements_contract'] = 'supplied-only-v1'
        initial = {'schema_version':'1.0','search_id':session['search_id'],'profile_version':1} if self.real else template
        return self.draft(case, initial, revision=1)

    def draft(self, case, profile, revision):
        identifier = self.require_case(case)
        values = flatten(profile)
        if self.real:
            from preference_agent.fields import FIELDS
            values = {**dict.fromkeys(FIELDS),**values}
        self.agent.setFields(identifier, values)
        reviewed = self.agent.reviewDraft(identifier)
        require(reviewed['valid'], 422, 'invalid_profile', '\n'.join(reviewed['errors']))
        session = self.metadata(case)
        case['draft'] = {'draft_id': session['draft']['draft_id'], 'revision': revision,
                         'profile': reviewed['profile'], 'fingerprint': fingerprint(reviewed['profile'])}
        if self.real: case['requirements_contract'] = 'supplied-only-v1'
        return case

    def confirm(self, case, body):
        identifier = self.require_case(case)
        draft = case['draft']
        require(body['draft_revision'] == draft['revision'] and body['fingerprint'] == draft['fingerprint'],
                409, 'draft_conflict', 'Confirmation must match the exact saved draft')
        session = self.metadata(case)
        previous = case['confirmations'][-1] if case['confirmations'] else None
        if (session['state'] == 'Confirmed' and previous and previous['draft_revision'] == draft['revision']
                and previous['fingerprint'] == draft['fingerprint']):
            require(body['review_token'] == previous['review_token'], 409, 'draft_conflict',
                    'Confirmation token does not match this saved confirmation')
            return case
        require(isinstance(body['review_token'], str) and body['review_token']
                and body['review_token'] == case['agent1']['review_token'],
                409, 'draft_conflict', 'Review token is missing or stale. Reload and review the current draft.')
        record = self.agent.confirmProfile(identifier, body['review_token'], TENANT)
        case['confirmations'].append({
            'version': record['profileVersion'], 'profile': deepcopy(record['profile']),
            'fingerprint': fingerprint(record['profile']), 'confirmed_at': record['confirmedAt'],
            'draft_revision': draft['revision'], 'actor_id': record['confirmedBy'],
            'review_token': body['review_token'], 'source': 'agent1',
            'agent1_draft_revision': record['reviewedDraftRevision'],
            'agent1_draft_id': record['sourceDraftId'],
        })
        self.metadata(case)
        return case

    def current(self, case, confirmation):
        session, _ = self.store.load(self.require_case(case))
        require(session['state'] == 'Confirmed' and session['latest_version'] == confirmation['version'],
                409, 'unconfirmed_profile', 'Confirm the current Agent1 draft before continuing')
        record = self.store.profile(session['case_id'], confirmation['version'])
        require(record['profile'] == confirmation['profile'] and record['searchId'] == case['search_id'],
                409, 'profile_conflict', 'Reload the saved Agent1 version before continuing')

    def prepare(self, case, dataset):
        return self.preparer.submitConfirmed(self.require_case(case), dataset)

    def execute(self, task_id):
        return self.handover.reconcileRetry(task_id)

    def comparison(self, case):
        bundle = compare_current(self.store, self.require_case(case), optional=True)
        return bundle['raw_comparison'] if bundle else None
