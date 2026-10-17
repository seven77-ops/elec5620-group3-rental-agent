"""Contracts orchestration for the local synthetic API."""
from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote
import json

from fastapi import Request
from ..common import require, now, uid, shape, integer, request_id
from ..settings import OPERATOR
from .business import load_document, MAX_BYTES, receive_review, validate_review, question_list, correct_review, approve_review, generate_questions


class ContractsAdapter:
    """Contracts orchestration around saved state and original member functions."""
    def __init__(self, ctx):
        self.ctx = ctx

    def consent(self, case_id: str, body: dict):
        get = self.ctx.get
        repo = self.ctx.repo
        selected = self.ctx.selected
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

    def upload_authorized(self, db, case_id, consent_id):
        get = self.ctx.get
        repo = self.ctx.repo
        selected = self.ctx.selected
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
                repo.put(db, 'review', review['review_id'], {'case_id': case_id, 'review': review, 'file_ref': file_ref, 'consent_id': consent_id})
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
        read_review = self.read_review
        return download(read_review(review_id), 'contract-review')

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
            require(origin is not None and origin['active'] and origin['case_id'] == saved['case_id'],
                    403, 'consent_required', 'The originating contract-processing consent must remain active')
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
