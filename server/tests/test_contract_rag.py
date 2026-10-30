"""Synthetic contracts only: private RAG scope, page provenance and revocation."""
from pathlib import Path
import copy,tempfile,unittest
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.tests.test_assistant_api import IntentProvider


def synthetic_pdf():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    from io import BytesIO
    writer=PdfWriter()
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    for lines in (["Synthetic rental agreement - TEST ONLY","1. Rent","Weekly rent: AUD 650 per week","Bond: AUD 2600","Start date: 2026-11-01","End date: 2027-11-01"],
                  ["6. Cleaning","The tenant must leave the premises reasonably clean, except for fair wear and tear.","7. Repairs","Notify Example Agent promptly when repairs are needed."]):
        page=writer.add_blank_page(width=612,height=792)
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(('BT /F1 10 Tf 40 740 Td '+ ' '.join(('0 -18 Td ' if i else '')+'('+line+') Tj' for i,line in enumerate(lines))+' ET').encode())
        page[NameObject('/Contents')]=writer._add_object(stream)
    output=BytesIO();writer.write(output);return output.getvalue()


class ContractRagTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=IntentProvider();self.app=create_app(runtime_dir=self.tmp.name,ai_provider=self.p);self.client=TestClient(self.app)
        self.case=self.client.post('/api/v1/cases',json={}).json();self.root='/api/v1/cases/'+self.case['case_id']
        r=self.client.post(self.root+'/profile-confirmations',json={'draft_revision':self.case['draft']['revision'],'fingerprint':self.case['draft']['fingerprint'],'review_token':self.case['agent1']['review_token']});self.assertEqual(r.status_code,200,r.text)
        run=self.client.post(self.root+'/evaluations',json={'request_id':'eval','confirmation_version':1}).json()
        self.client.post(self.root+'/selections',json={'request_id':'select','run_id':run['run_id'],'listing_id':run['report']['pending_confirmation'][0]['listing_id'],'confirmed':True})
        self.consent=self.client.post(self.root+'/contract-consents',json={'confirmed':True}).json()['consent_id']
        r=self.client.post(self.root+'/contract-reviews',content=synthetic_pdf(),headers={'Content-Type':'application/octet-stream','X-Consent-Id':self.consent,'X-Request-Id':'upload','X-Filename':'synthetic-contract.pdf'})
        self.assertEqual(r.status_code,200,r.text);self.review=r.json()['review'];self.rid=self.review['review_id'];self.base=self.root+'/rag/contracts/'+self.rid

    def status(self):
        r=self.client.get(self.base+'/status');self.assertEqual(r.status_code,200,r.text);return r.json()

    def enable(self,external=False,**extra):
        s=self.status();return self.client.post(self.base+'/index',json={'request_id':'enable','context_token':s['context_token'],'expected_version':self.review['version'],'confirmed':True,'allow_external_ai':external,**extra})

    def search(self,external=False,question='What does the cleaning clause say?',**extra):
        return self.client.post(self.base+'/search',json={'question':question,'allow_external_ai':external,'context_token':self.status()['context_token'],**extra})

    def test_separate_consent_local_search_page_and_clause_and_no_business_mutation(self):
        before=self.client.get(self.root).json()
        s=self.status();self.assertEqual(s['status'],'not_enabled')
        self.assertEqual(self.search().status_code,403)
        self.assertEqual(self.enable(confirmed=False).status_code,403)
        r=self.enable();self.assertEqual(r.status_code,200,r.text)
        result=self.search();self.assertEqual(result.status_code,200,result.text)
        rows=result.json()['evidence'];self.assertTrue(rows)
        cleaning=next(row for row in rows if 'reasonably clean' in row['text'])
        self.assertEqual(cleaning['page'],2);self.assertIn('6. Cleaning',cleaning['section'])
        self.assertEqual(cleaning['source_type'],'user_contract');self.assertEqual(cleaning['review_version'],1)
        self.assertIn('fair wear and tear',cleaning['text'])
        self.assertFalse(self.p.inputs);self.assertEqual(self.client.get(self.root).json(),before)
        r=self.client.post(self.base+'/answers',json={'question':'What does the cleaning clause say?','allow_external_ai':False,'context_token':self.status()['context_token']})
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['status'],'sources_only')
        private=[c for c in r.json()['citations'] if c['source_type']=='user_contract'];self.assertTrue(private);self.assertEqual(private[0]['page'],2)

    def test_contract_document_preview_is_scoped_and_not_cached(self):
        self.enable();token=self.status()['context_token']
        path=self.base+'/document?context_token='+token
        r=self.client.get(path);self.assertEqual(r.status_code,200,r.text[:100])
        self.assertEqual(r.headers['content-type'],'application/pdf')
        self.assertIn('no-store',r.headers['cache-control']);self.assertTrue(r.content.startswith(b'%PDF'))
        self.client.post(self.base+'/revoke',json={})
        self.assertEqual(self.client.get(path).status_code,403)

    def test_public_guidance_cannot_fill_in_a_missing_private_clause(self):
        self.enable(external=True)
        for question in ('What does my contract say about pets?','我的合同是否允许养宠物？'):
            with self.subTest(question=question):
                r=self.client.post(self.base+'/answers',json={'question':question,'allow_external_ai':True,'context_token':self.status()['context_token']})
                self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['status'],'insufficient_evidence')
                self.assertFalse(r.json()['claims']);self.assertFalse(self.p.inputs)
        self.assertTrue(self.search(question='我的合同关于清洁是怎么写的？').json()['evidence'])

    def test_other_case_and_external_scope_cannot_be_escalated(self):
        self.assertEqual(self.enable().status_code,200)
        other=self.client.post('/api/v1/cases',json={}).json()['case_id'];otherbase=self.base.replace(self.case['case_id'],other)
        for suffix in ('status','sources/unknown'):
            self.assertEqual(self.client.get(otherbase+'/'+suffix).status_code,404)
        self.assertEqual(self.client.post(otherbase+'/search',json={'question':'cleaning','allow_external_ai':False,'context_token':'fake'}).status_code,404)
        self.assertEqual(self.search(external=True).status_code,403);self.assertFalse(self.p.inputs)
        self.assertEqual(self.search(case_id=other).status_code,422)

    def test_revocation_deletes_derived_index_and_blocks_old_sources(self):
        self.enable();hit=self.search().json()['evidence'][0];source=self.base+'/sources/'+hit['chunk_id']
        self.assertEqual(self.client.get(source).status_code,200)
        files=list((Path(self.tmp.name)/'rag-private').rglob('*.sqlite3'));self.assertTrue(files)
        r=self.client.post(self.base+'/revoke',json={});self.assertEqual(r.status_code,200,r.text)
        self.assertFalse(list((Path(self.tmp.name)/'rag-private').rglob('*.sqlite3')))
        self.assertEqual(self.search().status_code,403);self.assertEqual(self.client.get(source).status_code,403)
        self.assertEqual(self.client.get('/api/v1/contract-reviews/'+self.rid).status_code,200)

    def test_original_consent_revocation_cleans_private_indexes(self):
        self.enable();self.assertTrue(list((Path(self.tmp.name)/'rag-private').rglob('*.sqlite3')))
        r=self.client.post(self.root+'/contract-consents',json={'confirmed':False,'consent_id':self.consent});self.assertEqual(r.status_code,200)
        self.assertFalse(list((Path(self.tmp.name)/'rag-private').rglob('*.sqlite3')))
        self.assertEqual(self.client.post(self.base+'/answers',json={'question':'cleaning','allow_external_ai':False,'context_token':'old'}).status_code,403)

    def test_same_version_review_change_and_file_change_block_old_results(self):
        self.enable();token=self.status()['context_token'];repo=self.app.state.repository
        with repo.transaction() as db:
            saved=repo.get(db,'review',self.rid);saved['review']['data_limitations'].append('Synthetic new note');repo.put(db,'review',self.rid,saved)
        r=self.client.post(self.base+'/search',json={'question':'rent','allow_external_ai':False,'context_token':token});self.assertEqual(r.status_code,409,r.text)
        self.assertEqual(self.enable(request_id='reindex').status_code,200)
        with repo.transaction() as db:saved=repo.get(db,'review',self.rid)
        (Path(self.tmp.name)/'uploads'/saved['file_ref']).write_bytes(b'Changed synthetic source')
        self.assertEqual(self.client.get(self.base+'/status').status_code,409)
