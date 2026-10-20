"""Profiles orchestration for the local synthetic API."""
from copy import deepcopy

from fastapi.responses import Response
from ..common import require, now, uid, shape, integer, request_id, opaque_ref
from ..settings import TENANT
from .business import validate_profile, render_markdown, build_selected_listing_evidence


class ProfilesAdapter:
    """Profiles orchestration around saved state and original member functions."""
    def __init__(self, ctx):
        self.ctx = ctx

    def create_case(self, body: dict):
        shape(body, ())
        with self.ctx.repo.transaction() as db, self.ctx.preferences.store.join(db):
            case = self.ctx.preferences.start(uid('rental'), self.ctx.settings.template)
            self.ctx.repo.put(db, 'case', case['case_id'], case)
            return case

    def read_case(self, case_id: str):
        with self.ctx.repo.transaction() as db:
            return self.ctx.get(db, 'case', case_id)

    def draft(self, case_id: str, body: dict):
        shape(body, ('expected_revision', 'profile'))
        with self.ctx.repo.transaction() as db, self.ctx.preferences.store.join(db):
            case = self.ctx.get(db, 'case', case_id)
            self.ctx.preferences.require_case(case)
            require(integer(body['expected_revision']) and body['expected_revision'] == case['draft']['revision'],
                    409, 'version_conflict', 'Reload the current saved draft')
            require(isinstance(body['profile'], dict), 422, 'invalid_profile', 'Profile must be an object')
            profile = deepcopy(body['profile'])
            profile.update(search_id=case['search_id'], profile_version=len(case['confirmations']) + 1)
            validate_profile(profile)
            case = self.ctx.preferences.draft(case, profile, revision=case['draft']['revision'] + 1)
            self.ctx.repo.put(db, 'case', case_id, case)
            return case

    def confirm(self, case_id: str, body: dict):
        shape(body, ('draft_revision', 'fingerprint', 'review_token'))
        require(integer(body['draft_revision']), 422, 'invalid_input', 'Draft revision must be an integer')
        with self.ctx.repo.transaction() as db, self.ctx.preferences.store.join(db):
            case = self.ctx.get(db, 'case', case_id)
            case = self.ctx.preferences.confirm(case, body)
            self.ctx.repo.put(db, 'case', case_id, case)
            return case

    def evaluation(self, case_id: str, body: dict):
        shape(body, ('request_id', 'confirmation_version'))
        require(integer(body['confirmation_version']) and body['confirmation_version'] > 0,
                422, 'invalid_input', 'Confirmation version must be a positive integer')
        key = case_id + ':' + request_id(body['request_id'])
        repo, bridge = self.ctx.repo, self.ctx.preferences
        # Reserve the member-owned task and HTTP identity atomically, before execution.
        with repo.transaction() as db, bridge.store.join(db):
            case = self.ctx.get(db, 'case', case_id)
            bridge.require_case(case)
            old = self.ctx.receipt(db, 'evaluation_receipt', key, body)
            if old and 'result' in old:
                return old['result']
            self.ctx.current(case, body['confirmation_version'])
            if old:
                task_id = old['agent1_task_id']
            else:
                task = bridge.prepare(case, self.ctx.settings.dataset)
                task_id = task['task_id']
                repo.put(db, 'evaluation_receipt', key, {'input': body, 'agent1_task_id': task_id})
        # Agent1 independently commits acceptance and completion; no adapter lock is held.
        try:
            task = bridge.execute(task_id)
        except ValueError as exc:
            require(False, 409, 'stale_evaluation', self.ctx.safe_message(exc))
        require(task['status'] == 'completed', 503, 'evaluation_failed',
                'Agent1 evaluation has not completed. Retry the same request; saved versions are retained.')
        with repo.transaction() as db, bridge.store.join(db):
            case = self.ctx.get(db, 'case', case_id)
            confirmation = self.ctx.current(case, body['confirmation_version'])
            session, _ = bridge.store.load(case['agent1_case_id'])
            require(task['version'] == confirmation['version'] and session['latest_task_id'] == task_id,
                    409, 'stale_evaluation', 'A newer confirmed task exists. Read the current version.')
            report = task['report']
            existing = repo.get(db, 'evaluation', report['recommendation_run_id'])
            if existing:
                result = existing['response']
            else:
                result = {'run_id': report['recommendation_run_id'], 'report': report,
                          'comparison': None, 'agent1_task_id': task_id,
                          'comparison_source': 'agent1_verified_versions'}
                try:
                    result['comparison'] = bridge.comparison(case)
                except ValueError as exc:
                    result['comparison_error'] = self.ctx.safe_message(exc)
                repo.put(db, 'evaluation', result['run_id'], {
                    'case_id': case_id, 'response': result, 'dataset': task['dataset'],
                    'profile': report['profile']})
            if not any(item['run_id'] == result['run_id'] for item in case['evaluations']):
                case['evaluations'].append({'run_id': result['run_id'], 'profile_version': confirmation['version'],
                    'created_at': now(), 'agent1_task_id': task_id})
            bridge.metadata(case)
            repo.put(db, 'case', case_id, case)
            self.ctx.save_receipt(db, 'evaluation_receipt', key, body, result)
            return result

    def read_evaluation(self, run_id: str):
        get = self.ctx.get
        repo = self.ctx.repo
        with repo.transaction() as db:
            return get(db, 'evaluation', run_id)['response']

    def export_evaluation(self, run_id: str, format: str = 'json'):
        download = self.ctx.download
        read_evaluation = self.read_evaluation
        report = read_evaluation(run_id)['report']
        require(format in {'json', 'markdown'}, 422, 'invalid_format', 'Choose json or markdown')
        if format == 'markdown':
            return Response(render_markdown(report), media_type='text/markdown', headers={'Content-Disposition': 'attachment; filename="evaluation.md"'})
        return download(report, 'evaluation')

    def select(self, case_id: str, body: dict):
        current = self.ctx.current
        expected = self.ctx.settings.expected
        get = self.ctx.get
        receipt = self.ctx.receipt
        repo = self.ctx.repo
        save_receipt = self.ctx.save_receipt
        shape(body, ('request_id', 'run_id', 'listing_id', 'confirmed'))
        opaque_ref(body['run_id'])
        opaque_ref(body['listing_id'])
        key = case_id + ':' + request_id(body['request_id'])
        with repo.transaction() as db:
            case = get(db, 'case', case_id)
            old = receipt(db, 'selection_receipt', key, body)
            if old:
                return old['result']
            confirmed = current(case)
            run = get(db, 'evaluation', body['run_id'])
            require(run['case_id'] == case_id and run['profile'] == confirmed['profile'],
                    409, 'stale_evaluation', 'Evaluate the current confirmed preferences before selecting')
            require(body['confirmed'] is True, 422, 'selection_confirmation_required', 'Explicitly confirm this listing choice')
            evidence = build_selected_listing_evidence(run['response']['report'], run['dataset'], body['listing_id'],
                        selected_at=expected['selectedAt'], user_confirmed=True)
            case['selection'] = evidence
            repo.put(db, 'case', case_id, case)
            save_receipt(db, 'selection_receipt', key, body, evidence)
            return evidence

    def export_selection(self, case_id: str):
        download = self.ctx.download
        get = self.ctx.get
        repo = self.ctx.repo
        with repo.transaction() as db:
            value = get(db, 'case', case_id)['selection']
            require(value is not None, 404, 'not_found', 'No selection has been saved')
            return download(value, 'selection')
