"""Contract intake for independently consented real candidates and legacy demos."""
from hashlib import sha256
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from copy import deepcopy
from contract_agent.review import review_agreement
from .candidate_followup import followup_value
from .real_contract import real_context
from urllib.parse import unquote
import json

from fastapi import Request
from ..common import ApiError, require, now, uid, shape, integer, request_id
from ..settings import OPERATOR
from .business import load_document, MAX_BYTES, receive_review, validate_review, question_list, correct_review, approve_review, generate_questions


class ContractsAdapter:
    """Contracts orchestration around saved state and original member functions."""
    def __init__(self, ctx):
        self.ctx = ctx

    def consent(self, case_id: str, body: dict):
        get = self.ctx.get
        repo = self.ctx.repo
        selected = self.ctx.contract_selection
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

    def selection_is_current(self, case, consent):
        if consent is None or consent['case_id'] != case['case_id']:
            return False
        try:
            return self.ctx.contract_selection(case) == consent['selection']
        except ApiError:
            # Saved consent remains readable while its former selection is historical.
            return False

    def list_consents(self, case_id: str):
        with self.ctx.repo.transaction() as db:
            case = self.ctx.get(db, 'case', case_id)
            consents = []
            for consent_id, raw in db.execute(
                    'SELECT id,body FROM objects WHERE kind=? ORDER BY rowid', ('consent',)):
                consent = json.loads(raw)
                if consent['case_id'] != case_id:
                    continue
                item = {'consent_id': consent_id, 'active': consent['active'],
                        'recorded_at': consent['recorded_at'],
                        'selection_current': self.selection_is_current(case, consent)}
                if 'revoked_at' in consent:
                    item['revoked_at'] = consent['revoked_at']
                consents.append(item)
            return {'consents': consents}

    def review_context(self, review_id: str):
        with self.ctx.repo.transaction() as db:
            saved = self.ctx.get(db, 'review', review_id)
            case = self.ctx.get(db, 'case', saved['case_id'])
            consent_id = saved.get('consent_id')
            consent = self.ctx.repo.get(db, 'consent', consent_id) if consent_id else None
            result = {'case_id': saved['case_id'], 'consent_id': consent_id,
                      'consent_active': bool(consent and consent['active'] and self.selection_is_current(case, consent))}
            context = real_context(saved, saved['review'])
            if context is not None:
                result['real_context'] = context
            return result

    def upload_authorized(self, db, case_id, consent_id):
        get = self.ctx.get
        repo = self.ctx.repo
        selected = self.ctx.contract_selection
        # Called before the route touches Request.stream()/body(), and again before disk writes.
        value = repo.get(db, 'consent', consent_id)
        require(value is not None and value['active'] and value['case_id'] == case_id,
                403, 'consent_required', 'Active independent contract-processing consent is required')
        case = get(db, 'case', case_id)
        require(selected(case) == value['selection'], 409, 'stale_selection', 'Consent must bind the current saved selection')
        return case, value

    async def upload(self, case_id: str, request: Request):
        expected = self.ctx.settings.expected
        receipt = self.ctx.receipt
        repo = self.ctx.repo
        save_receipt = self.ctx.save_receipt
        upload_authorized = self.upload_authorized
        consent_id = request.headers.get('X-Consent-Id', '')
        with repo.transaction() as db:
            initial_case, _ = upload_authorized(db, case_id, consent_id)
        real = initial_case['selection'].get('data_mode') == 'real_listings'
        as_of = datetime.now(ZoneInfo('Australia/Sydney')).date().isoformat() if real else expected['contractReferenceDate']
        logical_id = request_id(request.headers.get('X-Request-Id', ''))
        name = unquote(request.headers.get('X-Filename', ''))
        suffix = Path(name).suffix.lower()
        require(suffix in {'.txt', '.pdf', '.docx'}, 422, 'unsupported_format', 'Use a TXT, DOCX or PDF agreement')
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
                    'as_of': as_of}
        key = case_id + ':' + logical_id
        with repo.transaction() as db:
            case, consent = upload_authorized(db, case_id, consent_id)
            identity['selection'] = consent['selection']
            # Retry the same logical upload against its original reference date.
            prior = repo.get(db, 'contract_receipt', key)
            if real and prior:
                identity['as_of'] = prior['input']['as_of']
            old = receipt(db, 'contract_receipt', key, identity)
            if old:
                return {'review': old['result'], 'newly_created': False}
            directory = repo.directory / 'uploads'
            directory.mkdir(exist_ok=True)
            file_ref = uid('agreement') + suffix
            path = directory / file_ref
            try:
                path.write_bytes(content)
                document = load_document(path, consent=True, max_pdf_pages=30 if real else 10)
                # Uploaded filenames are presentation data, never filesystem paths.
                document['source_name'] = Path(name.replace('\\', '/')).name[:200]
                if real:
                    # A public ad is contextual material, never a SelectedListingEvidence certificate.
                    review = review_agreement(document, consent=True, selection=None, as_of=as_of,
                                              gateway=None, allow_external_ai=False)
                    review['data_limitations'].append('房源广告及用户补充记录未经独立核实；事实比对单独保存，不代表在租、申请或签约确认。')
                    created = True
                else:
                    review, created = receive_review(document, consent=True, selection=consent['selection'],
                        request_id='web-' + sha256(key.encode()).hexdigest(), as_of=as_of,
                        store=repo.directory / 'intake.sqlite3', gateway=None, allow_external_ai=False)
                validate_review(review)
                saved = {'case_id': case_id, 'review': review, 'file_ref': file_ref, 'consent_id': consent_id}
                if real:
                    saved['real_context'] = {'selection': deepcopy(consent['selection']),
                        'profile': deepcopy(self.ctx.current(case)),
                        'followup': deepcopy(followup_value(self.ctx, db, case)), 'captured_at': now()}
                repo.put(db, 'review', review['review_id'], saved)
                repo.put(db, 'review_version', review['review_id'] + ':1:' + uid('revision'), review)
                case['reviews'].append({'review_id': review['review_id'], 'version': review['version'], 'status': review['status']})
                repo.put(db, 'case', case_id, case)
                save_receipt(db, 'contract_receipt', key, identity, review)
            except BaseException:
                path.unlink(missing_ok=True)
                raise
            return {'review': review, 'newly_created': created}

    def read_review(self, review_id: str):
        get = self.ctx.get
        repo = self.ctx.repo
        with repo.transaction() as db:
            return get(db, 'review', review_id)['review']

    def export_review(self, review_id: str):
        download = self.ctx.download
        with self.ctx.repo.transaction() as db:
            saved = self.ctx.get(db, 'review', review_id)
            value = deepcopy(saved['review'])
            context = real_context(saved, value)
            if context is not None:
                value = {'review': value, 'real_context': context}
            return download(value, 'contract-review')

    def export_questions(self, review_id: str):
        download = self.ctx.download
        read_review = self.read_review
        return download(question_list(read_review(review_id)), 'contract-questions')

    def review_history(self, review_id: str):
        get = self.ctx.get
        repo = self.ctx.repo
        with repo.transaction() as db:
            get(db, 'review', review_id)
            return {'history': [{'snapshot_id': row[0], 'review': json.loads(row[1])} for row in db.execute(
                'SELECT id,body FROM objects WHERE kind=? AND id LIKE ? ORDER BY rowid',
                ('review_version', review_id + ':%'))]}

    def mutate_review(self, review_id, body, action):
        get = self.ctx.get
        repo = self.ctx.repo
        with repo.transaction() as db:
            saved = get(db, 'review', review_id)
            origin = repo.get(db, 'consent', saved.get('consent_id', ''))
            case = get(db, 'case', saved['case_id'])
            require(origin is not None and origin['active'] and self.selection_is_current(case, origin),
                    403, 'consent_required', 'Active originating consent must match the current confirmed selection')
            previous = saved['review']
            require(integer(body['expected_version']) and body['expected_version'] == previous['version'],
                    409, 'version_conflict', 'Reload the current contract review')
            review = action(previous)
            validate_review(review)
            self.save_review(db, saved, review)
            return review

    def save_review(self, db, saved, review):
        """Persist original module output and immutable history inside caller transaction."""
        validate_review(review)
        saved['review'] = review
        review_id = review['review_id']
        self.ctx.repo.put(db, 'review', review_id, saved)
        self.ctx.repo.put(db, 'review_version', review_id + ':' + str(review['version']) + ':' + uid('revision'), review)
        case = self.ctx.get(db, 'case', saved['case_id'])
        for item in case['reviews']:
            if item['review_id'] == review_id:
                item.update(version=review['version'], status=review['status'])
        self.ctx.repo.put(db, 'case', case['case_id'], case)

    def correction(self, review_id: str, body: dict):
        mutate_review = self.mutate_review
        shape(body, ('expected_version', 'corrections'))
        return mutate_review(review_id, body, lambda prior: correct_review(prior, body['corrections']))

    async def decision(self, review_id: str, request: Request):
        mutate_review = self.mutate_review
        operator = self.ctx.operator
        operator(request)
        body = await request.json()
        shape(body, ('expected_version', 'decision', 'note'))
        return mutate_review(review_id, body, lambda prior: approve_review(prior, reviewer=OPERATOR, decision=body['decision'], note=body['note']))

    def questions(self, review_id: str, body: dict):
        mutate_review = self.mutate_review
        shape(body, ('expected_version',))
        return mutate_review(review_id, body, generate_questions)
