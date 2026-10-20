import copy
import inspect
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from fastapi.testclient import TestClient
from server.tests.ai_fixtures import TestProvider


class AiApiTests(unittest.TestCase):
    def setUp(self):
        from server.app.main import create_app
        self.assertIn('ai_provider', inspect.signature(create_app).parameters, 'AI HTTP integration is missing')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.provider = TestProvider()
        self.app = create_app(runtime_dir=self.tmp.name, ai_provider=self.provider)
        self.client = TestClient(self.app)
        self.case = self.post('/cases',{}).json(); self.cid=self.case['case_id']
        self.case=self.post(f'/cases/{self.cid}/profile-confirmations',{
            'draft_revision':self.case['draft']['revision'],'fingerprint':self.case['draft']['fingerprint'],
            'review_token':self.case['agent1']['review_token']}).json()
        self.run=self.post(f'/cases/{self.cid}/evaluations',{'request_id':'e1','confirmation_version':1}).json()
        self.rid=self.run['run_id']

    def post(self,path,body):
        return self.client.post('/api/v1'+path,json=body)

    def review(self, free_text=True):
        self.post(f'/cases/{self.cid}/selections',{'request_id':'s1','run_id':self.rid,'listing_id':'DEMO-006','confirmed':True})
        consent=self.post(f'/cases/{self.cid}/contract-consents',{'confirmed':True}).json()
        self.consent=consent['consent_id']
        raw=Path('agent3/data/demo/agreements/selection-demo.txt').read_bytes()
        if free_text: raw=raw.replace(b'Weekly rent: $500 per person',b'The weekly rent payable is AUD 500 per person.')
        response=self.client.post(f'/api/v1/cases/{self.cid}/contract-reviews',content=raw,headers={
            'Content-Type':'application/octet-stream','X-Consent-Id':self.consent,'X-Request-Id':'upload','X-Filename':'demo.txt'})
        self.assertEqual(response.status_code,200,response.text)
        self.original=response.json()['review']; self.review_id=self.original['review_id']
        return self.review_id

    def analyze(self,request_id='a1'):
        return self.post(f'/contract-reviews/{self.review_id}/ai-analyses',{
            'request_id':request_id,'expected_version':1,'allow_external_ai':True})

    def test_recommendation_consent_zero_calls_and_report_immutable(self):
        response=self.post(f'/evaluations/{self.rid}/ai-explanations',{'request_id':'a','allow_external_ai':False})
        self.assertEqual(response.status_code,403,response.text); self.assertEqual(self.provider.inputs,[])
        response=self.post(f'/evaluations/{self.rid}/ai-explanations',{'request_id':'a','allow_external_ai':True})
        self.assertEqual(response.status_code,200,response.text)
        result=response.json(); self.assertEqual(result['status'],'success'); self.assertEqual(result['calls'][0]['provider'],'test_stub')
        self.assertEqual(len(result['result']['items']),5)
        self.assertEqual(self.client.get(f'/api/v1/evaluations/{self.rid}').json(),self.run)
        again=self.post(f'/evaluations/{self.rid}/ai-explanations',{'request_id':'a','allow_external_ai':True})
        self.assertEqual(again.json(),result); self.assertEqual(len(self.provider.inputs),1)
        self.assertEqual(self.client.get(f'/api/v1/evaluations/{self.rid}/ai-explanations/latest').json()['analysis_id'],result['analysis_id'])

    def test_contract_candidates_do_not_mutate_until_explicit_apply(self):
        self.review(); response=self.analyze(); self.assertEqual(response.status_code,200,response.text)
        analysis=response.json(); self.assertEqual(analysis['status'],'success',analysis)
        self.assertEqual(self.client.get(f'/api/v1/contract-reviews/{self.review_id}').json(),self.original)
        self.assertTrue(analysis['can_apply'])
        path=f'/contract-reviews/{self.review_id}/ai-analyses/{analysis["analysis_id"]}/apply'
        body={'request_id':'apply1','expected_version':1,'confirmed':False,'fields':['rent_amount','rent_period','rent_scope','currency']}
        self.assertEqual(self.post(path,body).status_code,403)
        body['confirmed']=True; response=self.post(path,body); self.assertEqual(response.status_code,200,response.text)
        applied=response.json(); self.assertEqual(applied['review']['version'],2)
        self.assertEqual(applied['review']['fields']['rent_amount']['value'],500)
        self.assertEqual(applied['review']['questions'],[])
        self.assertEqual(self.post(path,body).json(),applied)
        self.assertEqual(self.post(path,{**body,'fields':['address']}).status_code,409)
        latest=self.client.get(f'/api/v1/contract-reviews/{self.review_id}/ai-analyses/latest').json()
        self.assertFalse(latest['can_apply'])
        self.assertGreaterEqual(len(self.client.get(f'/api/v1/contract-reviews/{self.review_id}/history').json()['history']),2)

    def test_contract_revocation_blocks_generation_and_apply_preserves_history(self):
        self.review(); analysis=self.analyze().json()
        self.post(f'/cases/{self.cid}/contract-consents',{'confirmed':False,'consent_id':self.consent})
        before=len(self.provider.inputs); response=self.analyze('a2')
        self.assertEqual(response.status_code,403,response.text); self.assertEqual(len(self.provider.inputs),before)
        path=f'/contract-reviews/{self.review_id}/ai-analyses/{analysis["analysis_id"]}/apply'
        self.assertEqual(self.post(path,{'request_id':'apply','expected_version':1,'confirmed':True,'fields':['rent_amount']}).status_code,403)
        latest=self.client.get(f'/api/v1/contract-reviews/{self.review_id}/ai-analyses/latest').json()
        self.assertEqual(latest['analysis_id'],analysis['analysis_id']); self.assertFalse(latest['can_apply'])

    def test_changed_review_same_numeric_version_rejects_apply(self):
        self.review(free_text=False); analysis=self.analyze().json()
        self.post(f'/contract-reviews/{self.review_id}/questions',{'expected_version':1})
        path=f'/contract-reviews/{self.review_id}/ai-analyses/{analysis["analysis_id"]}/apply'
        response=self.post(path,{'request_id':'apply','expected_version':1,'confirmed':True,'fields':['address']})
        self.assertEqual(response.status_code,409,response.text)

    def test_provider_failure_preserves_original_and_records_truthful_failure(self):
        self.review(); self.provider.mode='error'; response=self.analyze()
        self.assertEqual(response.status_code,200,response.text)
        result=response.json(); self.assertEqual(result['status'],'failed'); self.assertEqual(result['calls'][0]['error_code'],'ai_timeout')
        self.assertFalse(result['can_apply'])
        self.assertEqual(self.client.get(f'/api/v1/contract-reviews/{self.review_id}').json(),self.original)

    def test_invalid_quotes_are_not_applicable(self):
        self.review(); self.provider.mode='hallucinated'; analysis=self.analyze().json()
        self.assertFalse(analysis['can_apply'])
        self.assertTrue(all(not x['valid'] for x in analysis['result']['candidates']))

    def test_remote_call_does_not_hold_sqlite_write_lock_and_rechecks_revocation(self):
        self.review(); entered=Event(); release=Event()
        def block(context):
            if context['task']=='contract_extract': entered.set(); release.wait(5)
        self.provider.on_call=block
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(self.analyze)
            self.assertTrue(entered.wait(2))
            try:
                response=self.post(f'/cases/{self.cid}/contract-consents',{'confirmed':False,'consent_id':self.consent})
                self.assertEqual(response.status_code,200,response.text)
                duplicate=self.analyze(); self.assertEqual(duplicate.status_code,403)
            finally: release.set()
            response=future.result(timeout=4)
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(self.client.get(f'/api/v1/contract-reviews/{self.review_id}').json(),self.original)

    def test_concurrent_duplicate_is_pending_then_receipt_survives_restart(self):
        from server.app.main import create_app
        self.review(); entered=Event(); release=Event()
        def block(context):
            if context['task']=='contract_extract': entered.set(); release.wait(5)
        self.provider.on_call=block
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(self.analyze)
            self.assertTrue(entered.wait(2))
            try:
                duplicate=self.analyze()
                self.assertEqual(duplicate.status_code,409,duplicate.text)
                self.assertEqual(duplicate.json()['error']['code'],'operation_in_progress')
            finally:
                release.set()
            response=future.result(timeout=4)
        self.assertEqual(response.status_code,200,response.text)
        count=len(self.provider.inputs)
        restored_provider=TestProvider()
        client=TestClient(create_app(runtime_dir=self.tmp.name,ai_provider=restored_provider))
        restored=client.post(f'/api/v1/contract-reviews/{self.review_id}/ai-analyses',json={
            'request_id':'a1','expected_version':1,'allow_external_ai':True})
        self.assertEqual(restored.json(),response.json())
        self.assertEqual(restored_provider.inputs,[])
        self.assertGreaterEqual(count,1)

    def test_older_slow_analysis_cannot_replace_newer_latest(self):
        self.review(); entered=Event(); release=Event()
        def block(context):
            if context['task']=='contract_extract' and not entered.is_set():
                entered.set(); release.wait(5)
        self.provider.on_call=block
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(self.analyze,'older')
            self.assertTrue(entered.wait(2))
            try:
                newer=self.analyze('newer')
                self.assertEqual(newer.status_code,200,newer.text)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=4).status_code,200)
        latest=self.client.get(f'/api/v1/contract-reviews/{self.review_id}/ai-analyses/latest').json()
        self.assertEqual(latest['analysis_id'],newer.json()['analysis_id'])

    def test_unconfigured_provider_and_changed_preference_are_explicit(self):
        from server.app.main import create_app
        from server.app.ai.provider import ModelProvider
        client=TestClient(create_app(runtime_dir=self.tmp.name,ai_provider=ModelProvider(env={})))
        response=client.post(f'/api/v1/evaluations/{self.rid}/ai-explanations',json={'request_id':'missing','allow_external_ai':True})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['status'],'failed')
        self.assertFalse(response.json()['calls'][0]['attempted'])
        profile=copy.deepcopy(self.case['draft']['profile']); profile['budget']['maximum']+=10
        self.post(f'/cases/{self.cid}/profile-drafts',{'expected_revision':1,'profile':profile})
        response=self.post(f'/evaluations/{self.rid}/ai-explanations',{'request_id':'new','allow_external_ai':True})
        self.assertEqual(response.status_code,409,response.text); self.assertEqual(self.provider.inputs,[])


if __name__=='__main__': unittest.main()
