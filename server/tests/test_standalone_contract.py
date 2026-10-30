"""Standalone document processing stays explicitly consented and privately scoped."""
from io import BytesIO
from zipfile import ZipFile
from xml.sax.saxutils import escape
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from server.tests.legacy_app import create_app
from server.tests.ai_fixtures import TestProvider
from server.tests.test_contract_rag import synthetic_pdf

TEXT = ('Address: 1 Example Street, Sydney NSW 2000\nRent: AUD 650 per week whole property\n'
        'Bond: AUD 2600\nStart date: 2026-11-01\nEnd date: 2027-11-01\n'
        '6. Cleaning\nThe tenant must leave the premises reasonably clean, except for fair wear and tear.\n')


class StandaloneContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.provider = TestProvider()
        self.app = create_app(runtime_dir=self.tmp.name, ai_provider=self.provider)
        self.client = TestClient(self.app)
        self.case = self.client.post('/api/v1/cases', json={}).json()
        self.root = '/api/v1/cases/' + self.case['case_id']

    def consent(self):
        response = self.client.post(self.root + '/contract-consents', json={'confirmed': True, 'scope': 'document'})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['consent_id']

    def upload(self, consent, kind='txt', request='upload'):
        raw = TEXT.encode()
        if kind == 'pdf': raw = synthetic_pdf()
        elif kind == 'docx':
            stream = BytesIO()
            with ZipFile(stream, 'w') as archive:
                paragraphs = ''.join('<w:p><w:r><w:t>' + escape(line) + '</w:t></w:r></w:p>' for line in TEXT.splitlines())
                archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + paragraphs + '</w:body></w:document>')
            raw = stream.getvalue()
        return self.client.post(self.root + '/contract-reviews', content=raw, headers={
            'Content-Type': 'application/octet-stream', 'X-Consent-Id': consent,
            'X-Request-Id': request, 'X-Filename': 'standalone.' + kind})

    def test_explicit_document_consent_uploads_without_preferences_or_selection_in_all_formats(self):
        self.assertNotEqual(self.client.post(self.root + '/contract-consents', json={'confirmed': True}).status_code, 200)
        self.assertEqual(self.upload('missing').status_code, 403)
        for kind in ('txt', 'pdf', 'docx'):
            with self.subTest(kind=kind):
                consent = self.consent(); response = self.upload(consent, kind, kind)
                self.assertEqual(response.status_code, 200, response.text)
                review = response.json()['review']
                self.assertIsNone(review['selection_evidence'])
                self.assertTrue(review['fields']['rent_amount']['evidence']['quote'])
                self.assertIn('findings', review)
                context = self.client.get('/api/v1/contract-reviews/' + review['review_id'] + '/context').json()
                self.assertTrue(context['consent_active']); self.assertNotIn('real_context', context)
                again = self.upload(consent, kind, kind)
                self.assertEqual(again.json()['review'], review); self.assertFalse(again.json()['newly_created'])
        state = self.client.get(self.root).json()
        self.assertIsNone(state['selection']); self.assertFalse(state['confirmations'])

    def test_private_search_ai_gate_and_revocation_are_scoped_to_originating_document_consent(self):
        consent = self.consent(); uploaded = self.upload(consent)
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        review = uploaded.json()['review']; rid = review['review_id']
        base = self.root + '/rag/contracts/' + rid
        status = self.client.get(base + '/status'); self.assertEqual(status.status_code, 200, status.text)
        token = status.json()['context_token']
        enabled = self.client.post(base + '/index', json={'request_id':'enable', 'context_token':token,
            'expected_version':1, 'confirmed':True, 'allow_external_ai':False})
        self.assertEqual(enabled.status_code, 200, enabled.text)
        body = {'question':'合同清洁条款怎么写？', 'context_token':token, 'allow_external_ai':False, 'language':'zh'}
        found = self.client.post(base + '/answers', json=body)
        self.assertEqual(found.status_code, 200, found.text)
        self.assertTrue(any(c['source_type']=='user_contract' for c in found.json()['citations']))
        self.assertFalse(self.provider.inputs)
        self.assertEqual(self.client.post(base + '/answers', json={**body, 'allow_external_ai':True}).status_code,403)
        # A later selection is unrelated to this explicitly standalone document.
        with self.app.state.repository.transaction() as db:
            case = self.app.state.repository.get(db, 'case', self.case['case_id'])
            case['selection'] = {'profile_version':999}
            self.app.state.repository.put(db, 'case', self.case['case_id'], case)
        self.assertEqual(self.client.get(base + '/status').status_code,200)
        ai = self.client.post('/api/v1/contract-reviews/' + rid + '/ai-analyses', json={
            'request_id':'ai', 'expected_version':1, 'allow_external_ai':True})
        self.assertEqual(ai.status_code,200,ai.text)
        other = self.client.post('/api/v1/cases', json={}).json()['case_id']
        self.assertEqual(self.client.get(base.replace(self.case['case_id'],other) + '/status').status_code,404)
        self.client.post(self.root + '/contract-consents', json={'confirmed':False, 'consent_id':consent})
        self.assertEqual(self.client.post(base + '/answers', json=body).status_code,403)
        self.assertFalse(list((Path(self.tmp.name)/'rag-private').rglob('*.sqlite3')))
        self.assertEqual(self.client.post('/api/v1/contract-reviews/' + rid + '/corrections',
            json={'expected_version':1, 'corrections':{'rent_amount':660}}).status_code,403)
        self.assertEqual(self.client.get('/api/v1/contract-reviews/' + rid).status_code,200)

    def test_standalone_chat_guidance_is_english(self):
        service = next(route.endpoint.__self__ for route in self.app.routes if route.path.endswith('/rag/contracts/{review_id}/status'))
        reply = service.chat_answer(self.case['case_id'], '帮我看一下合同')
        self.assertIn('Upload', reply['content'])
        self.assertNotIn('Open the contract', reply['content'])
