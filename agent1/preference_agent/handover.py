"""Local acknowledged delivery and reproducible evaluation; no remote messaging."""
from copy import deepcopy
from uuid import uuid4
from .bridge import evaluate, fingerprint, validate_profile, validate_contract
from .service import now, active
from .store import dumps


def check_record(record):
    profile = record['profile']
    validate_profile(profile)
    if (not record.get('confirmedBy') or not record.get('confirmedAt')
            or not record.get('sourceDraftId') or record.get('reviewedDraftRevision') is None
            or profile['search_id'] != record['searchId']
            or profile['profile_version'] != record['profileVersion']):
        raise ValueError('Missing confirmation metadata or inconsistent profile references.')


def coordination_envelope(record, task):
    """Export the team's proposed envelope; never merge it into RentalProfile.

    This local course prototype always marks exports as exampleOnly. The flag
    describes the deployment/data boundary; confirmation still comes from the UI.
    """
    check_record(record)
    if (task['case_id'] != record['caseId'] or task['search_id'] != record['searchId']
            or task['version'] != record['profileVersion']
            or task['profile_hash'] != fingerprint(record['profile'])
            or not isinstance(task['task_id'], str) or not task['task_id'].strip()
            or task['dataset'].get('data_mode') != 'synthetic_demo'):
        raise ValueError('Handover references do not match the saved profile or supported data mode.')
    return {
        'exampleOnly': True, 'dataMode': 'synthetic_demo',
        'caseId': record['caseId'], 'searchId': record['searchId'],
        'profileVersion': record['profileVersion'], 'taskId': task['task_id'],
        'profileFile': 'rental-profile.json',
        'profileFingerprint': fingerprint(record['profile']),
        'confirmation': {
            'confirmed': True, 'confirmedBy': record['confirmedBy'],
            'confirmedAt': record['confirmedAt'], 'sourceDraftId': record['sourceDraftId'],
            'reviewedDraftRevision': record['reviewedDraftRevision']},
        'note': 'Local course prototype; synthetic listings. Confirmation records a local UI action '
                '(scripted in --demo), not an authenticated identity. This file is not a network delivery receipt.'}


def check_report(report, record, dataset):
    validate_contract('RecommendationReport', report)
    expected_run_id = 'rr-' + fingerprint({
        'profile_fingerprint': fingerprint(record['profile']),
        'dataset_fingerprint': fingerprint(dataset), 'as_of': dataset['as_of'],
        'scoring_version': 'rules-1.0', 'schema_version': '1.1'})
    if (report['search_id'] != record['searchId']
            or report['profile_version'] != record['profileVersion']
            or report['profile'] != record['profile']
            or report['profile_fingerprint'] != fingerprint(record['profile'])
            or report['dataset_fingerprint'] != fingerprint(dataset)
            or report['as_of'] != dataset['as_of']
            or report['recommendation_run_id'] != expected_run_id
            or report['scoring_version'] != 'rules-1.0'):
        raise ValueError('Recommendation report does not match the saved profile and dataset.')


def verified_feedback(store, session, task_id):
    if session.get('latest_task_id') != task_id:
        raise ValueError('Feedback is not from the current task; stale results cannot justify changes.')
    task = store.task(task_id)
    if (task['case_id'] != session['case_id'] or task['version'] != session['latest_version']
            or task['status'] != 'completed' or task.get('report') is None):
        raise ValueError('Feedback is stale, incomplete or failed; it is not a no-match result.')
    record = store.profile(session['case_id'], session['latest_version'])
    check_report(task['report'], record, task['dataset'])
    # Reproduce the local evaluation, not just trust a schema or a claimed hash.
    if task['report'] != evaluate(record['profile'], task['dataset']):
        raise ValueError('Stored feedback differs from reproduced evaluation.')
    return deepcopy(task['report'])


class LocalSupervisor:
    """Receiver adapter around Agent2's pure evaluate function.

    Acceptance is committed before evaluation. A crash after acceptance can safely
    be retried against the same task/dataset: evaluation has no external effects.
    This is not a distributed exactly-once queue or a full multi-agent supervisor.
    """
    def __init__(self, store, evaluator=evaluate):
        self.store, self.evaluator = store, evaluator

    def getTaskStatus(self, task_id):
        return self.store.task(task_id)

    def routeTask(self, task_id):
        with self.store.transaction() as db:
            task = self.store.task(task_id, db)
            session, _ = self.store.load(task['case_id'], db)
            active(session)
            if task['version'] != session['latest_version'] or task_id != session['latest_task_id']:
                raise ValueError('Only the latest confirmed task can be delivered or retried.')
            if task['status'] == 'completed':
                return task
            record = self.store.profile(task['case_id'], task['version'], db)
            check_record(record)
            if task['profile_hash'] != fingerprint(record['profile']) or task['dataset_hash'] != fingerprint(task['dataset']):
                raise ValueError('Stored handover payload is inconsistent.')
            task.update(status='accepted', accepted_at=task.get('accepted_at') or now(),
                        attempts=task['attempts'] + 1, last_error=None)
            self.store.save_task(task, db)
        # The receiver has acknowledged the saved version, not finished evaluation.
        try:
            report = self.evaluator(deepcopy(record['profile']), deepcopy(task['dataset']))
            check_report(report, record, task['dataset'])
        except Exception as exc:
            with self.store.transaction() as db:
                latest = self.store.task(task_id, db)
                if latest['status'] != 'completed':
                    latest.update(status='failed', last_error=f'{type(exc).__name__}: {exc}')
                    self.store.save_task(latest, db)
                return latest
        with self.store.transaction() as db:
            latest = self.store.task(task_id, db)
            if latest['status'] != 'completed':
                latest.update(status='completed', report=report, completed_at=now(), last_error=None)
                self.store.save_task(latest, db)
        return latest


class HandoverService:
    def __init__(self, store, receiver=None):
        self.store = store
        self.receiver = receiver or LocalSupervisor(store)

    def submitConfirmed(self, case_id, dataset):
        dataset_hash = fingerprint(dataset)
        with self.store.transaction() as db:
            session, serial = self.store.load(case_id, db)
            active(session)
            if session['state'] != 'Confirmed':
                raise ValueError('Confirm the current draft before starting a search.')
            version = session['latest_version']
            record = self.store.profile(case_id, version, db)
            check_record(record)
            old = db.execute('SELECT task_id FROM tasks WHERE case_id=? AND version=? AND dataset_hash=?',
                             (case_id, version, dataset_hash)).fetchone()
            if old:
                task_id = old[0]
            else:
                task_id = 'task-' + uuid4().hex
                task = {'task_id': task_id, 'case_id': case_id, 'version': version,
                        'search_id': session['search_id'], 'profile_hash': fingerprint(record['profile']),
                        'dataset_hash': dataset_hash, 'dataset': deepcopy(dataset), 'status': 'prepared',
                        'created_at': now(), 'accepted_at': None, 'completed_at': None,
                        'attempts': 0, 'report': None, 'last_error': None,
                        'transport': 'local_in_process_adapter'}
                db.execute('INSERT INTO tasks VALUES (?, ?, ?, ?, ?)',
                           (task_id, case_id, version, dataset_hash, dumps(task)))
            session['latest_task_id'] = task_id
            self.store.save(session, serial, db)
        return self.reconcileRetry(task_id)

    def reconcileRetry(self, task_id):
        task = self.store.task(task_id)
        session, _ = self.store.load(task['case_id'])
        active(session)
        if session['state'] != 'Confirmed' or task['version'] != session['latest_version'] or task_id != session['latest_task_id']:
            raise ValueError('Cannot retry a stale task or while a revised draft awaits confirmation.')
        try:
            return self.receiver.routeTask(task_id)
        except Exception as exc:
            # Delivery may have succeeded before the reply was lost: reconcile first.
            with self.store.transaction() as db:
                saved = self.store.task(task_id, db)
                if saved['status'] not in ('completed', 'failed'):
                    saved.update(status='unverified', last_error=f'{type(exc).__name__}: {exc}')
                    self.store.save_task(saved, db)
            return saved
