"""Profiles orchestration for the local synthetic API."""
from copy import deepcopy

from fastapi.responses import Response
from ..common import require, now, uid, shape, integer, request_id, opaque_ref
from ..settings import TENANT
from .business import evaluate, fingerprint, validate_profile, compare_reports, render_markdown, build_selected_listing_evidence


class ProfilesAdapter:
    """Profiles orchestration around saved state and original member functions."""
    def __init__(self, ctx):
        self.ctx = ctx

    def create_case(self, body: dict):
        repo = self.ctx.repo
        template = self.ctx.settings.template
        shape(body, ())
        case_id = uid('rental')
        profile = deepcopy(template)
        profile.update(search_id=uid('search'), profile_version=1)
        case = {'case_id': case_id, 'search_id': profile['search_id'],
                'draft': {'draft_id': uid('draft'), 'revision': 1, 'profile': profile, 'fingerprint': fingerprint(profile)},
                'confirmations': [], 'evaluations': [], 'selection': None, 'reviews': [], 'aftercare_case_id': None}
        with repo.transaction() as db:
            repo.put(db, 'case', case_id, case)
        return case

    def read_case(self, case_id: str):
        get = self.ctx.get
        repo = self.ctx.repo
        with repo.transaction() as db:
            return get(db, 'case', case_id)

    def draft(self, case_id: str, body: dict):
        get = self.ctx.get
        repo = self.ctx.repo
        shape(body, ('expected_revision', 'profile'))
        with repo.transaction() as db:
            case = get(db, 'case', case_id)
            require(integer(body['expected_revision']) and body['expected_revision'] == case['draft']['revision'],
                    409, 'version_conflict', 'Reload the current saved draft')
            require(isinstance(body['profile'], dict), 422, 'invalid_profile', 'Profile must be an object')
            profile = deepcopy(body['profile'])
            profile.update(search_id=case['search_id'], profile_version=len(case['confirmations']) + 1)
            validate_profile(profile)
            case['draft'] = {'draft_id': uid('draft'), 'revision': case['draft']['revision'] + 1,
                             'profile': profile, 'fingerprint': fingerprint(profile)}
            repo.put(db, 'case', case_id, case)
            return case

    def confirm(self, case_id: str, body: dict):
        get = self.ctx.get
        repo = self.ctx.repo
        shape(body, ('draft_revision', 'fingerprint'))
        with repo.transaction() as db:
            case = get(db, 'case', case_id)
            draft = case['draft']
            require(integer(body['draft_revision']) and body['draft_revision'] == draft['revision'] and body['fingerprint'] == draft['fingerprint'],
                    409, 'draft_conflict', 'Confirmation must match the exact saved draft')
            validate_profile(draft['profile'])
            if not case['confirmations'] or case['confirmations'][-1]['draft_revision'] != draft['revision']:
                case['confirmations'].append({'version': len(case['confirmations']) + 1, 'fingerprint': draft['fingerprint'],
                    'profile': deepcopy(draft['profile']), 'confirmed_at': now(), 'draft_revision': draft['revision'], 'actor_id': TENANT})
                repo.put(db, 'case', case_id, case)
            return case

    def evaluation(self, case_id: str, body: dict):
        current = self.ctx.current
        dataset = self.ctx.settings.dataset
        get = self.ctx.get
        receipt = self.ctx.receipt
        repo = self.ctx.repo
        safe_message = self.ctx.safe_message
        save_receipt = self.ctx.save_receipt
        shape(body, ('request_id', 'confirmation_version'))
        require(integer(body['confirmation_version']) and body['confirmation_version'] > 0, 422, 'invalid_input', 'Confirmation version must be a positive integer')
        key = case_id + ':' + request_id(body['request_id'])
        with repo.transaction() as db:
            case = get(db, 'case', case_id)
            old = receipt(db, 'evaluation_receipt', key, body)
            if old:
                return old['result']
            confirmation = current(case, body['confirmation_version'])
            report = evaluate(confirmation['profile'], dataset, as_of=dataset['as_of'])
            existing = repo.get(db, 'evaluation', report['recommendation_run_id'])
            if existing:
                result = existing['response']
                save_receipt(db, 'evaluation_receipt', key, body, result)
                return result
            result = {'run_id': report['recommendation_run_id'], 'report': report, 'comparison': None}
            if case['evaluations']:
                previous = get(db, 'evaluation', case['evaluations'][-1]['run_id'])['response']['report']
                try:
                    result['comparison'] = compare_reports(previous, report)
                except ValueError as exc:
                    result['comparison_error'] = safe_message(exc)
            repo.put(db, 'evaluation', result['run_id'], {'case_id': case_id, 'response': result, 'dataset': dataset,
                                                       'profile': confirmation['profile']})
            if not any(item['run_id'] == result['run_id'] for item in case['evaluations']):
                case['evaluations'].append({'run_id': result['run_id'], 'profile_version': confirmation['version'], 'created_at': now()})
            repo.put(db, 'case', case_id, case)
            save_receipt(db, 'evaluation_receipt', key, body, result)
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
