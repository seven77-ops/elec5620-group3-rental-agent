"""Loopback synthetic demonstration API around the original Agent 2/3/4 code."""
from .bootstrap import ROOT
from .repository import Repository, canonical
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import hmac
import json
import os
import re
from urllib.parse import unquote
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException
from rental_agent.engine import evaluate, fingerprint
from rental_agent.validation import validate_profile, ValidationError
from rental_agent.handoff import build_selected_listing_evidence
from rental_agent.report import compare_reports, render_markdown
from contract_agent.document import load_document, MAX_BYTES
from contract_agent.intake import receive_review
from contract_agent.review import correct_review, approve_review, generate_questions
from contract_agent.contracts import validate_review, question_list
from contract_agent.errors import ContractError
from aftercare_agent.store import AftercareAgent
from aftercare_agent.contracts import validate as validate_aftercare
from aftercare_agent.errors import AftercareError

TENANT = 'web-demo-tenant'
OPERATOR = 'web-demo-operator'
AFTERCARE_CLOCK = '2026-10-15T10:00:00+11:00'


class ApiError(Exception):
    def __init__(self, status, code, message, fields=None):
        self.status, self.code, self.message, self.fields = status, code, message, fields


def require(condition, status, code, message):
    if not condition:
        raise ApiError(status, code, message)


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix):
    return prefix + '-' + uuid4().hex


def load(relative):
    return json.loads((ROOT / relative).read_text())


def shape(body, required, optional=()):
    require(isinstance(body, dict) and set(required) <= set(body) and set(body) <= set(required) | set(optional),
            422, 'invalid_input', 'Supply the required fields only: ' + ', '.join(required))


def integer(value):
    return type(value) is int and value >= 0


def request_id(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', value),
            422, 'invalid_request_id', 'Request ID must contain 1–80 letters, digits, dots, underscores or hyphens')
    return value


def create_app(runtime_dir=None, operator_key=None):
    class StrictRoute(APIRoute):
        def get_route_handler(self):
            original = super().get_route_handler()
            async def strict(request):
                # Operator decision routes reject before parsing their JSON body.
                if request.url.path.endswith('/decisions'):
                    operator(request)
                raw_contract_upload = self.path == '/api/v1/cases/{case_id}/contract-reviews'
                if not raw_contract_upload and request.headers.get('Content-Type', '').split(';')[0] == 'application/json':
                    def unique(items):
                        result = {}
                        for key, value in items:
                            require(key not in result, 422, 'invalid_json', 'Duplicate JSON keys are not allowed')
                            result[key] = value
                        return result
                    def constant(value):
                        raise ApiError(422, 'invalid_json', 'Non-finite numbers are not allowed')
                    try:
                        raw = await request.body()
                        require(len(raw) <= 256_000, 413, 'request_too_large', 'JSON request exceeds the local limit')
                        json.loads(raw, object_pairs_hook=unique, parse_constant=constant)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        raise ApiError(422, 'invalid_json', 'Supply valid UTF-8 JSON')
                return await original(request)
            return strict

    app = FastAPI(title='Rental journey synthetic demo', version='1.0')
    app.router.route_class = StrictRoute
    repo = Repository(runtime_dir or os.environ.get('RENTAL_RUNTIME_DIR', ROOT / '.runtime'))
    operator_secret = operator_key if operator_key is not None else os.environ.get('RENTAL_OPERATOR_KEY', '')
    aftercare = AftercareAgent(repo.directory / 'aftercare.sqlite3', operator_ids={OPERATOR}, gateway=None)
    expected = load('integration/agent1-to-agent2/expected.json')
    dataset = load('agent2/data/demo/listings.json')
    template = load('integration/agent1-to-agent2/confirmed-profile.json')
    templates = {}
    fixture_clocks = {}
    for path in sorted((ROOT / 'agent4/data/demo/requests').glob('*.json')):
        command = json.loads(path.read_text())
        templates.setdefault(command['operation'], command['payload'])
        fixture_clocks.setdefault(command['operation'], command['as_of'])
    for operation in ('create', 'revise_tenancy'):
        if operation in templates:
            templates[operation]['tenancy'].pop('tenancy_id', None)
            templates[operation]['tenancy'].pop('tenant_id', None)
            templates[operation]['tenancy']['confirmed'] = False
    tenancy_template = deepcopy(templates['create']['tenancy'])
    normal_agreement = (ROOT / 'agent3/data/demo/agreements/selection-demo.txt').read_bytes()
    examples = {'normal': normal_agreement, 'rent_conflict': normal_agreement.replace(b'$500', b'$650')}
    app.state.repository = repo

    def safe_message(message):
        result = str(message).replace(str(repo.directory), '[runtime]').replace(str(ROOT), '[application]')
        return result[:1500]

    def failure(request, status, code, message, fields=None):
        error = {'code': code, 'message': safe_message(message), 'request_id': request.headers.get('X-Request-Id', uid('error'))}
        if fields:
            error['fields'] = fields
        return JSONResponse({'error': error}, status_code=status)

    @app.exception_handler(ApiError)
    async def api_failure(request, exc):
        return failure(request, exc.status, exc.code, exc.message, exc.fields)

    @app.exception_handler(RequestValidationError)
    async def validation_failure(request, exc):
        return failure(request, 422, 'invalid_input', 'Request parameters are invalid')

    @app.exception_handler(HTTPException)
    async def http_failure(request, exc):
        return failure(request, exc.status_code, 'not_found' if exc.status_code == 404 else 'invalid_request', exc.detail)

    @app.exception_handler(AftercareError)
    async def aftercare_failure(request, exc):
        code = exc.code
        status = 403 if code == 'access_denied' else 404 if code == 'not_found' else 503 if code == 'storage_error' else 422 if code == 'invalid_input' else 409
        return failure(request, status, code, str(exc))

    @app.exception_handler(ContractError)
    async def contract_failure(request, exc):
        code = exc.code
        return failure(request, 409 if code in {'duplicate_request_conflict', 'invalid_request'} else 422, code, str(exc))

    @app.exception_handler(ValidationError)
    async def profile_failure(request, exc):
        return failure(request, 422, 'invalid_profile', str(exc), {'profile': safe_message(exc)})

    @app.exception_handler(ValueError)
    async def value_failure(request, exc):
        return failure(request, 422, 'invalid_input', str(exc))

    @app.exception_handler(Exception)
    async def unknown_failure(request, exc):
        return failure(request, 500, 'service_failure', 'The local operation failed. Previous saved results remain available.')

    def get(db, kind, identifier):
        value = repo.get(db, kind, identifier)
        require(value is not None, 404, 'not_found', 'The saved object was not found')
        return value

    def operator(request):
        supplied = request.headers.get('X-Operator-Key', '')
        require(bool(operator_secret) and hmac.compare_digest(supplied, operator_secret), 403, 'access_denied',
                'A locally configured operator key is required')

    def current(case, version=None):
        latest = case['confirmations'][-1] if case['confirmations'] else None
        require(latest is not None and latest['fingerprint'] == case['draft']['fingerprint'] and
                latest['draft_revision'] == case['draft']['revision'] and (version is None or latest['version'] == version),
                409, 'unconfirmed_profile', 'Confirm the exact current saved draft before continuing')
        return latest

    def selected(case):
        latest = current(case)
        require(case['selection'] is not None and case['selection']['profile_version'] == latest['version'],
                409, 'selection_required', 'Choose and confirm a listing from the current confirmed preferences')
        return case['selection']

    def receipt(db, kind, key, body):
        saved = repo.get(db, kind, key)
        if saved:
            require(saved['input'] == body, 409, 'request_conflict', 'This request ID belongs to different input')
        return saved

    def save_receipt(db, kind, key, body, result):
        repo.put(db, kind, key, {'input': body, 'result': result})

    def download(value, name):
        return Response(canonical(value), media_type='application/json', headers={'Content-Disposition': f'attachment; filename="{name}.json"'})

    @app.get('/api/v1/health')
    def health():
        return {'status': 'ok', 'mode': 'synthetic_demo'}

    @app.get('/api/v1/demo-config')
    def config():
        return {'mode': 'synthetic_demo', 'clocks': {'evaluation': dataset['as_of'], 'selection': expected['selectedAt'],
                'contract': expected['contractReferenceDate'], 'aftercare': AFTERCARE_CLOCK},
                'profile_template': template, 'tenancy_template': tenancy_template,
                'agreement_examples': [{'id': key, 'name': key + '.txt'} for key in examples],
                'capabilities': {'agent1': 'simulated_form', 'agent2': True, 'agent3': True, 'agent4': True,
                                 'external_ai': False, 'synthetic_contract_only': True, 'max_upload_bytes': MAX_BYTES,
                                 'aftercare_evidence_template': templates['create']['evidence'],
                                 'aftercare_clock_policy': 'Per-case monotonic; poll advances to 2026-11-03T09:00:00+11:00; close to 09:01; original retries retain original time'}}

    @app.get('/api/v1/demo-agreements/{example_id}')
    def agreement(example_id: str):
        require(example_id in examples, 404, 'not_found', 'Unknown synthetic agreement example')
        return Response(examples[example_id], media_type='text/plain', headers={'Content-Disposition': f'attachment; filename="{example_id}.txt"'})

    @app.post('/api/v1/cases')
    def create_case(body: dict):
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

    @app.get('/api/v1/cases/{case_id}')
    def read_case(case_id: str):
        with repo.transaction() as db:
            return get(db, 'case', case_id)

    @app.post('/api/v1/cases/{case_id}/profile-drafts')
    def draft(case_id: str, body: dict):
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

    @app.post('/api/v1/cases/{case_id}/profile-confirmations')
    def confirm(case_id: str, body: dict):
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

    @app.post('/api/v1/cases/{case_id}/evaluations')
    def evaluation(case_id: str, body: dict):
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

    @app.get('/api/v1/evaluations/{run_id}')
    def read_evaluation(run_id: str):
        with repo.transaction() as db:
            return get(db, 'evaluation', run_id)['response']

    @app.get('/api/v1/evaluations/{run_id}/export')
    def export_evaluation(run_id: str, format: str = 'json'):
        report = read_evaluation(run_id)['report']
        require(format in {'json', 'markdown'}, 422, 'invalid_format', 'Choose json or markdown')
        if format == 'markdown':
            return Response(render_markdown(report), media_type='text/markdown', headers={'Content-Disposition': 'attachment; filename="evaluation.md"'})
        return download(report, 'evaluation')

    @app.post('/api/v1/cases/{case_id}/selections')
    def select(case_id: str, body: dict):
        shape(body, ('request_id', 'run_id', 'listing_id', 'confirmed'))
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

    @app.get('/api/v1/cases/{case_id}/exports/selection')
    def export_selection(case_id: str):
        with repo.transaction() as db:
            value = get(db, 'case', case_id)['selection']
            require(value is not None, 404, 'not_found', 'No selection has been saved')
            return download(value, 'selection')

    @app.post('/api/v1/cases/{case_id}/contract-consents')
    def consent(case_id: str, body: dict):
        shape(body, ('confirmed',), ('consent_id',))
        require(type(body['confirmed']) is bool, 422, 'invalid_input', 'Consent confirmation must be true or false')
        with repo.transaction() as db:
            case = get(db, 'case', case_id)
            if body['confirmed']:
                selection = selected(case)
                consent_id = uid('consent')
                repo.put(db, 'consent', consent_id, {'case_id': case_id, 'selection': selection, 'active': True, 'recorded_at': now()})
            else:
                require(isinstance(body.get('consent_id'), str), 422, 'invalid_input', 'Supply the consent reference to revoke')
                consent_id = body['consent_id']
                value = get(db, 'consent', consent_id)
                require(value['case_id'] == case_id, 403, 'invalid_consent', 'Consent is not bound to this case')
                value.update(active=False, revoked_at=now())
                repo.put(db, 'consent', consent_id, value)
            return {'consent_id': consent_id, 'active': body['confirmed']}

    def upload_authorized(db, case_id, consent_id):
        # Called before the route touches Request.stream()/body(), and again before disk writes.
        value = repo.get(db, 'consent', consent_id)
        require(value is not None and value['active'] and value['case_id'] == case_id,
                403, 'consent_required', 'Active independent contract-processing consent is required')
        case = get(db, 'case', case_id)
        require(selected(case) == value['selection'], 409, 'stale_selection', 'Consent must bind the current saved selection')
        return case, value

    @app.post('/api/v1/cases/{case_id}/contract-reviews', openapi_extra={
        'requestBody': {'required': True, 'content': {'application/octet-stream': {
            'schema': {'type': 'string', 'format': 'binary'}}}},
        'parameters': [{'in': 'header', 'name': key, 'required': True, 'schema': {'type': 'string'}}
                       for key in ('X-Consent-Id', 'X-Request-Id', 'X-Filename')]})
    async def upload(case_id: str, request: Request):
        consent_id = request.headers.get('X-Consent-Id', '')
        with repo.transaction() as db:
            upload_authorized(db, case_id, consent_id)
        logical_id = request_id(request.headers.get('X-Request-Id', ''))
        name = unquote(request.headers.get('X-Filename', ''))
        suffix = Path(name).suffix.lower()
        require(suffix in {'.txt', '.pdf', '.docx'}, 422, 'unsupported_format', 'Use a TXT, DOCX or PDF synthetic agreement')
        require(request.headers.get('Content-Type', '').split(';')[0] == 'application/octet-stream',
                415, 'unsupported_media_type', 'Send raw agreement bytes as application/octet-stream')
        size_header = request.headers.get('Content-Length')
        if size_header:
            require(size_header.isdigit(), 422, 'invalid_input', 'Invalid upload length')
            require(int(size_header) <= MAX_BYTES, 413, 'upload_too_large', 'Agreement exceeds the 2,000,000-byte limit')
        content = bytearray()
        async for chunk in request.stream():
            require(len(content) + len(chunk) <= MAX_BYTES, 413, 'upload_too_large', 'Agreement exceeds the 2,000,000-byte limit')
            content.extend(chunk)
        identity = {'sha256': sha256(content).hexdigest(), 'format': suffix, 'consent_id': consent_id,
                    'as_of': expected['contractReferenceDate']}
        key = case_id + ':' + logical_id
        with repo.transaction() as db:
            case, consent = upload_authorized(db, case_id, consent_id)
            identity['selection'] = consent['selection']
            old = receipt(db, 'contract_receipt', key, identity)
            if old:
                return {'review': old['result'], 'newly_created': False}
            directory = repo.directory / 'uploads'
            directory.mkdir(exist_ok=True)
            file_ref = uid('agreement') + suffix
            path = directory / file_ref
            try:
                path.write_bytes(content)
                document = load_document(path, consent=True)
                # Uploaded filenames are presentation data, never filesystem paths.
                document['source_name'] = Path(name.replace('\\', '/')).name[:200]
                review, created = receive_review(document, consent=True, selection=consent['selection'],
                    request_id='web-' + sha256(key.encode()).hexdigest(), as_of=expected['contractReferenceDate'],
                    store=repo.directory / 'intake.sqlite3', gateway=None, allow_external_ai=False)
                validate_review(review)
                repo.put(db, 'review', review['review_id'], {'case_id': case_id, 'review': review, 'file_ref': file_ref})
                repo.put(db, 'review_version', review['review_id'] + ':1:' + uid('revision'), review)
                case['reviews'].append({'review_id': review['review_id'], 'version': review['version'], 'status': review['status']})
                repo.put(db, 'case', case_id, case)
                save_receipt(db, 'contract_receipt', key, identity, review)
            except BaseException:
                path.unlink(missing_ok=True)
                raise
            return {'review': review, 'newly_created': created}

    @app.get('/api/v1/contract-reviews/{review_id}')
    def read_review(review_id: str):
        with repo.transaction() as db:
            return get(db, 'review', review_id)['review']

    @app.get('/api/v1/contract-reviews/{review_id}/export')
    def export_review(review_id: str):
        return download(read_review(review_id), 'contract-review')

    @app.get('/api/v1/contract-reviews/{review_id}/questions/export')
    def export_questions(review_id: str):
        return download(question_list(read_review(review_id)), 'contract-questions')

    def mutate_review(review_id, body, action):
        with repo.transaction() as db:
            saved = get(db, 'review', review_id)
            previous = saved['review']
            require(integer(body['expected_version']) and body['expected_version'] == previous['version'],
                    409, 'version_conflict', 'Reload the current contract review')
            review = action(previous)
            validate_review(review)
            saved['review'] = review
            repo.put(db, 'review', review_id, saved)
            repo.put(db, 'review_version', review_id + ':' + str(review['version']) + ':' + uid('revision'), review)
            case = get(db, 'case', saved['case_id'])
            for item in case['reviews']:
                if item['review_id'] == review_id:
                    item.update(version=review['version'], status=review['status'])
            repo.put(db, 'case', case['case_id'], case)
            return review

    @app.post('/api/v1/contract-reviews/{review_id}/corrections')
    def correction(review_id: str, body: dict):
        shape(body, ('expected_version', 'corrections'))
        return mutate_review(review_id, body, lambda prior: correct_review(prior, body['corrections']))

    @app.post('/api/v1/contract-reviews/{review_id}/decisions')
    async def decision(review_id: str, request: Request):
        operator(request)
        body = await request.json()
        shape(body, ('expected_version', 'decision', 'note'))
        return mutate_review(review_id, body, lambda prior: approve_review(prior, reviewer=OPERATOR, decision=body['decision'], note=body['note']))

    @app.post('/api/v1/contract-reviews/{review_id}/questions')
    def questions(review_id: str, body: dict):
        shape(body, ('expected_version',))
        return mutate_review(review_id, body, generate_questions)

    @app.get('/api/v1/aftercare/template-commands')
    def command_templates():
        return templates

    @app.post('/api/v1/aftercare/commands')
    def aftercare_command(body: dict, request: Request):
        shape(body, ('case_id', 'request_id', 'expected_version', 'operation', 'payload'))
        logical_id = request_id(body['request_id'])
        require(integer(body['expected_version']), 422, 'invalid_input', 'Expected version must be a nonnegative integer')
        require(isinstance(body['operation'], str) and isinstance(body['payload'], dict), 422, 'invalid_input', 'Operation and payload must be valid')
        role = 'operator' if body['operation'] == 'operator_decision' else 'tenant'
        if role == 'operator':
            operator(request)
        key = str(body['case_id']) + ':' + logical_id
        with repo.transaction() as db:
            case = get(db, 'case', body['case_id'])
            old = receipt(db, 'aftercare_receipt', key, body)
            if old and 'result' in old:
                return old['result']
            binding = old.get('command') if old else None
            pending = case.get('aftercare_pending')
            require(pending is None or pending['request_key'] == key, 409, 'creation_in_progress',
                    'Another tenancy creation is in progress; retry its original request')
            if binding:
                require(case['aftercare_case_id'] in (None, binding['case_id']), 409, 'mapping_conflict',
                        'This request belongs to another saved tenancy creation')
            if binding is None:
                m4_id = case['aftercare_case_id']
                payload = deepcopy(body['payload'])
                if body['operation'] == 'create':
                    require(m4_id is None, 409, 'already_exists', 'An aftercare case is already linked')
                    require(isinstance(payload.get('tenancy'), dict) and payload['tenancy'].get('confirmed') is True,
                            422, 'tenancy_confirmation_required', 'Explicitly confirm tenancy details first')
                    m4_id = uid('aftercare')
                    payload['tenancy'].update(tenant_id=TENANT, tenancy_id=uid('tenancy'))
                else:
                    require(m4_id is not None, 409, 'aftercare_required', 'Create the confirmed tenancy case first')
                    if body['operation'] == 'revise_tenancy' and isinstance(payload.get('tenancy'), dict):
                        previous = aftercare.get(m4_id, TENANT)
                        payload['tenancy'].update(tenant_id=TENANT, tenancy_id=previous['tenancy']['tenancy_id'])
                if body['operation'] == 'request_draft':
                    require(payload.get('use_model') is False and payload.get('allow_external_ai') is False,
                            422, 'external_ai_disabled', 'This synthetic demo uses deterministic drafts only')
                previous_clock = repo.get(db, 'clock', case['case_id'])
                base = datetime.fromisoformat(previous_clock['at'] if previous_clock else AFTERCARE_CLOCK)
                candidate = base + timedelta(seconds=1) if previous_clock else base
                # Poll/close progress to allowlisted scenario checkpoints, never a browser-supplied clock.
                checkpoint = datetime.fromisoformat(fixture_clocks.get(body['operation'], AFTERCARE_CLOCK))
                clock = max(candidate, checkpoint).isoformat()
                binding = {'schema_version': '1.0', 'case_id': m4_id, 'request_id': 'web-' + sha256(key.encode()).hexdigest(),
                    'actor_id': OPERATOR if role == 'operator' else TENANT, 'actor_role': role,
                    'expected_version': body['expected_version'], 'operation': body['operation'], 'payload': payload, 'as_of': clock}
                validate_aftercare('command', binding)
                # Persist the generated clock/IDs before module submission, including recoverable failures.
                repo.put(db, 'clock', case['case_id'], {'at': clock})
                repo.put(db, 'aftercare_receipt', key, {'input': body, 'command': binding})
            if body['operation'] == 'create' and case['aftercare_case_id'] is None:
                case['aftercare_pending'] = {'request_key': key, 'case_id': binding['case_id']}
                repo.put(db, 'case', case['case_id'], case)
        # The module owns its atomic receipts. A lost adapter response is recovered with this frozen command.
        try:
            result = aftercare.submit(binding)
        except AftercareError:
            with repo.transaction() as db:
                case = get(db, 'case', body['case_id'])
                if case.get('aftercare_pending', {}).get('request_key') == key:
                    case.pop('aftercare_pending')
                    repo.put(db, 'case', case['case_id'], case)
            raise
        with repo.transaction() as db:
            case = get(db, 'case', body['case_id'])
            require(case['aftercare_case_id'] in (None, binding['case_id']), 409, 'mapping_conflict', 'Reload the mapped aftercare case')
            case['aftercare_case_id'] = binding['case_id']
            case.pop('aftercare_pending', None)
            repo.put(db, 'case', case['case_id'], case)
            repo.put(db, 'aftercare_mapping', binding['case_id'], {'case_id': case['case_id']})
            repo.put(db, 'aftercare_receipt', key, {'input': body, 'command': binding, 'result': result})
        return result

    @app.get('/api/v1/aftercare/cases/{aftercare_id}')
    def read_aftercare(aftercare_id: str):
        with repo.transaction() as db:
            get(db, 'aftercare_mapping', aftercare_id)
        return aftercare.get(aftercare_id, TENANT)

    @app.get('/api/v1/aftercare/cases/{aftercare_id}/export')
    def export_aftercare(aftercare_id: str):
        return download(read_aftercare(aftercare_id), 'aftercare-case')

    return app


app = create_app()
