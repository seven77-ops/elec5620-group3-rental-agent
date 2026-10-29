import asyncio
from contextlib import closing
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(Path('server/app/main.py').exists(), 'HTTP adapter has not been implemented')
        from server.tests.legacy_app import create_app
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app(runtime_dir=self.temp.name, operator_key='test-private-key')
        self.client = TestClient(self.app)
        self.config = self.client.get('/api/v1/demo-config').json()
        self.case = self.client.post('/api/v1/cases', json={}).json()
        self.cid = self.case['case_id']

    def post(self, path, data):
        return self.client.post('/api/v1/' + path, json=data)

    def confirm(self):
        self.case = self.post(f'cases/{self.cid}/profile-confirmations', {
            'draft_revision': self.case['draft']['revision'], 'fingerprint': self.case['draft']['fingerprint'],
            'review_token': self.case['agent1']['review_token']}).json()
        return self.case['confirmations'][-1]['version']

    def selected(self):
        version = self.confirm()
        run = self.post(f'cases/{self.cid}/evaluations', {'request_id':'evaluate-1', 'confirmation_version':version}).json()
        self.assertEqual(run['report']['counts']['eligible'], 15)
        selection = self.post(f'cases/{self.cid}/selections', {
            'request_id':'select-1','run_id':run['run_id'],'listing_id':'DEMO-006','confirmed':True})
        self.assertEqual(selection.status_code, 200, selection.text)
        return run, selection.json()

    def review(self, conflict=False):
        self.selected()
        consent = self.post(f'cases/{self.cid}/contract-consents', {'confirmed':True}).json()
        data = self.client.get('/api/v1/demo-agreements/' + ('rent_conflict' if conflict else 'normal')).content
        headers={'X-Consent-Id':consent['consent_id'],'X-Request-Id':'upload-1','X-Filename':'agreement.txt','Content-Type':'application/octet-stream'}
        response=self.client.post(f'/api/v1/cases/{self.cid}/contract-reviews', content=data, headers=headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json(), data, headers

    def test_confirmation_versions_and_restart(self):
        self.assertEqual(self.post(f'cases/{self.cid}/evaluations', {'request_id':'e','confirmation_version':1}).status_code,409)
        self.confirm()
        original=copy.deepcopy(self.case['confirmations'][0])
        profile=copy.deepcopy(self.case['draft']['profile']); profile['weights']['commute'] += 1
        saved=self.post(f'cases/{self.cid}/profile-drafts',{'expected_revision':1,'profile':profile})
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(saved.json()['confirmations'][0],original)
        self.assertEqual(self.post(f'cases/{self.cid}/evaluations', {'request_id':'e','confirmation_version':1}).status_code,409)
        self.assertEqual(self.post(f'cases/{self.cid}/profile-drafts',{'expected_revision':1,'profile':profile}).status_code,409)
        from server.tests.legacy_app import create_app
        restarted=TestClient(create_app(runtime_dir=self.temp.name))
        self.assertEqual(restarted.get(f'/api/v1/cases/{self.cid}').json()['draft']['revision'],2)

    def test_real_evaluate_selection_and_export(self):
        run, selected=self.selected()
        self.assertEqual(selected['listing_id'],'DEMO-006')
        self.assertEqual(self.client.get(f'/api/v1/cases/{self.cid}/exports/selection').json(),selected)
        repeated=self.post(f'cases/{self.cid}/evaluations',{'request_id':'evaluate-1','confirmation_version':1})
        self.assertEqual(repeated.json(),run)
        bad=self.post(f'cases/{self.cid}/selections',{'request_id':'select-1','run_id':run['run_id'],'listing_id':'DEMO-002','confirmed':True})
        self.assertEqual(bad.status_code,409)

    def test_upload_retries_conflict_and_revoke(self):
        result,data,headers=self.review()
        self.assertEqual(result['review']['status'],'Reviewed')
        url=f'/api/v1/cases/{self.cid}/contract-reviews'
        retry=self.client.post(url,content=data,headers=headers).json()
        self.assertEqual(retry['review'],result['review']); self.assertFalse(retry['newly_created'])
        self.assertEqual(self.client.post(url,content=data+b'changed',headers=headers).status_code,409)
        self.post(f'cases/{self.cid}/contract-consents',{'confirmed':False,'consent_id':headers['X-Consent-Id']})
        self.assertEqual(self.client.post(url,content=data,headers=headers).status_code,403)

    def test_consent_checked_before_asgi_receive(self):
        calls=[]
        async def receive():
            calls.append(True)
            return {'type':'http.request','body':b'private','more_body':False}
        messages=[]
        async def send(message): messages.append(message)
        scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST','scheme':'http','path':f'/api/v1/cases/{self.cid}/contract-reviews','raw_path':b'/','query_string':b'','root_path':'','headers':[], 'server':('test',80),'client':('test',123)}
        asyncio.run(self.app(scope,receive,send))
        self.assertEqual(calls,[])
        self.assertEqual(messages[0]['status'],403)
        self.assertEqual(list(Path(self.temp.name).glob('uploads/*')),[])

    def test_upload_limits_and_paths(self):
        self.selected()
        consent=self.post(f'cases/{self.cid}/contract-consents',{'confirmed':True}).json()['consent_id']
        headers={'X-Consent-Id':consent,'X-Request-Id':'big','X-Filename':'../../secret.txt','Content-Type':'application/octet-stream'}
        self.assertEqual(self.client.post(f'/api/v1/cases/{self.cid}/contract-reviews',content=b'a'*2000001,headers=headers).status_code,413)
        self.assertEqual(list(Path(self.temp.name).glob('uploads/*')),[])

    def test_operator_gate_corrections_and_durable_reviews(self):
        result,_,_=self.review(True); review=result['review']; rid=review['review_id']
        self.assertEqual(review['status'],'Awaiting Human Review')
        self.assertEqual(self.post(f'contract-reviews/{rid}/questions',{'expected_version':1}).status_code,409)
        decision={'expected_version':1,'decision':'approve','note':'Demo operator reviewed the conflict'}
        self.assertEqual(self.post(f'contract-reviews/{rid}/decisions',decision).status_code,403)
        approved=self.client.post(f'/api/v1/contract-reviews/{rid}/decisions',json=decision,headers={'X-Operator-Key':'test-private-key'})
        self.assertEqual(approved.status_code,200,approved.text)
        questions=self.post(f'contract-reviews/{rid}/questions',{'expected_version':1})
        self.assertEqual(questions.json()['status'],'Questions Ready')
        changed=self.post(f'contract-reviews/{rid}/corrections',{'expected_version':1,'corrections':{'rent_amount':500}})
        self.assertEqual(changed.json()['version'],2); self.assertEqual(changed.json()['questions'],[])
        self.assertEqual(self.post(f'contract-reviews/{rid}/corrections',{'expected_version':1,'corrections':{'rent_amount':501}}).status_code,409)
        self.assertNotIn('test-private-key',str(self.config))

    def test_aftercare_confirmation_identity_retries_and_clock(self):
        tenancy=copy.deepcopy(self.config['tenancy_template'])
        templates=self.client.get('/api/v1/aftercare/template-commands').json()
        payload=copy.deepcopy(templates['create']); payload['tenancy']=tenancy
        command={'case_id':self.cid,'request_id':'m4-create','expected_version':0,'operation':'create','payload':payload}
        self.assertEqual(self.post('aftercare/commands',command).status_code,422)
        tenancy['confirmed']=True
        created=self.post('aftercare/commands',command)
        self.assertEqual(created.status_code,200,created.text)
        aftercare=created.json(); self.assertNotEqual(aftercare['case_id'],self.cid)
        self.assertEqual(self.post('aftercare/commands',dict(command,actor_role='operator')).status_code,422)
        plan={'case_id':self.cid,'request_id':'m4-plan','expected_version':1,'operation':'create_plan','payload':templates['create_plan']}
        planned=self.post('aftercare/commands',plan)
        self.assertEqual(planned.status_code,200,planned.text)
        self.assertGreater(planned.json()['case']['updated_at'],aftercare['case']['updated_at'])
        self.assertEqual(self.post('aftercare/commands',command).json(),aftercare)
        self.assertEqual(self.post('aftercare/commands',dict(plan,request_id='wrong-version')).status_code,409)
        self.assertEqual(self.post('aftercare/commands',dict(plan,operation='operator_decision')).status_code,403)
        self.assertEqual(self.client.get('/api/v1/aftercare/cases/arbitrary').status_code,404)

    def test_repeated_evaluation_never_overwrites_saved_run(self):
        self.confirm()
        first=self.post(f'cases/{self.cid}/evaluations',{'request_id':'first','confirmation_version':1}).json()
        second=self.post(f'cases/{self.cid}/evaluations',{'request_id':'second','confirmation_version':1}).json()
        self.assertEqual(second,first)
        self.assertEqual(self.client.get('/api/v1/evaluations/'+first['run_id']).json(),first)

    def test_strict_json_duplicate_keys_and_nonfinite(self):
        for raw in ('{"request_id":"a","request_id":"b"}', '{"value":NaN}', '{"value":Infinity}'):
            response=self.client.post('/api/v1/cases',content=raw,headers={'Content-Type':'application/json'})
            self.assertEqual(response.status_code,422,response.text)
            self.assertEqual(response.json()['error']['code'],'invalid_json')

    def test_boolean_version_rejected(self):
        self.confirm()
        response=self.post(f'cases/{self.cid}/evaluations',{'request_id':'bool','confirmation_version':True})
        self.assertEqual(response.status_code,422)

    def test_stale_selection_and_immutable_comparison(self):
        first, _ = self.selected()
        self.case=self.client.get(f'/api/v1/cases/{self.cid}').json()
        profile=copy.deepcopy(self.case['draft']['profile']); profile['weights']={'commute':1,'cost':9,'housing':1,'amenities':1}
        self.case=self.post(f'cases/{self.cid}/profile-drafts',{'expected_revision':1,'profile':profile}).json()
        self.confirm()
        stale=self.post(f'cases/{self.cid}/selections',{'request_id':'stale','run_id':first['run_id'],'listing_id':'DEMO-006','confirmed':True})
        self.assertEqual(stale.status_code,409)
        evaluated=self.post(f'cases/{self.cid}/evaluations',{'request_id':'second','confirmation_version':2}).json()
        self.assertIsNotNone(evaluated['comparison'])
        self.assertEqual(self.client.get('/api/v1/evaluations/'+first['run_id']).json(),first)

    def test_streamed_upload_limit_has_no_partial_file(self):
        self.selected()
        consent=self.post(f'cases/{self.cid}/contract-consents',{'confirmed':True}).json()['consent_id']
        headers={'X-Consent-Id':consent,'X-Request-Id':'stream','X-Filename':'agreement.txt','Content-Type':'application/octet-stream'}
        response=self.client.post(f'/api/v1/cases/{self.cid}/contract-reviews',content=iter([b'x'*1000000,b'y'*1000001]),headers=headers)
        self.assertEqual(response.status_code,413,response.text)
        self.assertEqual(list(Path(self.temp.name).glob('uploads/*')),[])

    def test_module_receipts_survive_adapter_receipt_recovery(self):
        templates=self.client.get('/api/v1/aftercare/template-commands').json()
        payload=copy.deepcopy(templates['create']); payload['tenancy']['confirmed']=True
        command={'case_id':self.cid,'request_id':'recover','expected_version':0,'operation':'create','payload':payload}
        first=self.post('aftercare/commands',command).json()
        repo=self.app.state.repository
        with repo.transaction() as db:
            saved=repo.get(db,'aftercare_receipt',self.cid+':recover')
            saved.pop('result'); repo.put(db,'aftercare_receipt',self.cid+':recover',saved)
        retry=self.post('aftercare/commands',command)
        self.assertEqual(retry.status_code,200,retry.text)
        self.assertEqual(retry.json(),first)

    def test_full_aftercare_workflow_with_original_payloads(self):
        fixtures=Path('agent4/data/demo/requests')
        case=None
        for path in sorted(fixtures.glob('*.json')):
            original=__import__('json').loads(path.read_text(encoding='utf-8'))
            payload=copy.deepcopy(original['payload'])
            if original['operation']=='create':
                payload['tenancy'].pop('tenant_id'); payload['tenancy'].pop('tenancy_id')
            command={'case_id':self.cid,'request_id':original['request_id'],
                     'expected_version':case['version'] if case else 0,
                     'operation':original['operation'],'payload':payload}
            headers={'X-Operator-Key':'test-private-key'} if original['operation']=='operator_decision' else {}
            response=self.client.post('/api/v1/aftercare/commands',json=command,headers=headers)
            if path.name=='11-request_draft.json':
                self.assertEqual(response.status_code,409,response.text)
                self.assertEqual(response.json()['error']['code'],'review_required')
                continue
            self.assertEqual(response.status_code,200,(path.name,response.text))
            case=response.json()['case']
            if path.name=='10-bond_update.json': self.assertEqual(case['bond']['state'],'UnderReview')
            if path.name=='13-operator_decision.json': self.assertNotEqual(case['bond']['state'],'UnderReview')
            if path.name=='16-poll_reminders.json':
                self.assertTrue(any(item['state']=='delivered' for item in case['reminders']))
        self.assertEqual(case['bond']['state'],'Resolved')
        exported=self.client.get('/api/v1/aftercare/cases/'+case['case_id']+'/export')
        self.assertEqual(exported.json(),case)


    def test_concurrent_create_cannot_leave_orphan_module_case(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch
        import sqlite3
        from aftercare_agent.store import AftercareAgent
        payload=copy.deepcopy(self.client.get('/api/v1/aftercare/template-commands').json()['create'])
        payload['tenancy']['confirmed']=True
        command={'case_id':self.cid,'request_id':'parallel-a','expected_version':0,'operation':'create','payload':payload}
        entered,release=Event(),Event()
        original=AftercareAgent.submit
        def paused(agent, binding):
            if not entered.is_set():
                entered.set(); release.wait(5)
            return original(agent,binding)
        with patch.object(AftercareAgent,'submit',paused),ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(self.post,'aftercare/commands',command)
            self.assertTrue(entered.wait(5))
            try:
                second=self.post('aftercare/commands',dict(command,request_id='parallel-b'))
            finally:
                release.set()
            self.assertEqual(first.result().status_code,200)
        self.assertEqual(second.status_code,409)
        with closing(sqlite3.connect(Path(self.temp.name)/'aftercare.sqlite3')) as db:
            self.assertEqual(db.execute('select count(*) from cases').fetchone()[0],1)


    def test_empty_question_packet_is_prepared_not_sent(self):
        # Without its special condition the normal agreement has no findings, so no questions.
        self.selected()
        consent=self.post(f'cases/{self.cid}/contract-consents',{'confirmed':True}).json()
        data=b'\n'.join(line for line in self.client.get('/api/v1/demo-agreements/normal').content.splitlines()
                        if not line.startswith(b'Special condition'))
        response=self.client.post(f'/api/v1/cases/{self.cid}/contract-reviews',content=data,headers={
            'X-Consent-Id':consent['consent_id'],'X-Request-Id':'upload-1','X-Filename':'agreement.txt',
            'Content-Type':'application/octet-stream'})
        self.assertEqual(response.status_code,200,response.text)
        review=response.json()['review']; rid=review['review_id']
        generated=self.post(f'contract-reviews/{rid}/questions',{'expected_version':1})
        self.assertEqual(generated.status_code,200,generated.text)
        self.assertEqual(generated.json()['questions'],[])
        packet=self.client.get(f'/api/v1/contract-reviews/{rid}/questions/export')
        self.assertEqual(packet.status_code,200,packet.text)
        self.assertEqual(packet.json()['handoff_status'],'prepared_not_sent')
        self.assertEqual(packet.json()['questions'],[])


    def test_upload_wrong_content_type_still_authorizes_before_receive(self):
        calls=[]; messages=[]
        async def receive():
            calls.append(True)
            return {'type':'http.request','body':b'{}','more_body':False}
        async def send(message): messages.append(message)
        scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST','scheme':'http',
               'path':f'/api/v1/cases/{self.cid}/contract-reviews','raw_path':b'/','query_string':b'','root_path':'',
               'headers':[(b'content-type',b'application/json')], 'server':('test',80),'client':('test',123)}
        asyncio.run(self.app(scope,receive,send))
        self.assertEqual(messages[0]['status'],403)
        self.assertEqual(calls,[])


    def test_revocation_blocks_all_review_followups_preserves_reads(self):
        result,_,headers=self.review(True)
        review=result['review']; rid=review['review_id']
        self.post(f'cases/{self.cid}/contract-consents',{'confirmed':False,'consent_id':headers['X-Consent-Id']})
        commands=[('corrections',{'expected_version':1,'corrections':{'rent_amount':500}},{}),
                  ('questions',{'expected_version':1},{}),
                  ('decisions',{'expected_version':1,'decision':'approve','note':'Checked'},{'X-Operator-Key':'test-private-key'})]
        for operation,body,auth in commands:
            response=self.client.post(f'/api/v1/contract-reviews/{rid}/{operation}',json=body,headers=auth)
            self.assertEqual(response.status_code,403,(operation,response.text))
            self.assertEqual(response.json()['error']['code'],'consent_required')
        self.assertEqual(self.client.get(f'/api/v1/contract-reviews/{rid}').json(),review)
        self.assertEqual(self.client.get(f'/api/v1/contract-reviews/{rid}/export').json(),review)

    def test_json_media_type_and_size_limits_are_consistent(self):
        for media in ('application/json','application/problem+json','application/vnd.demo+json'):
            duplicate=self.client.post('/api/v1/cases',content=b'{"a":1,"a":2}',headers={'Content-Type':media})
            self.assertEqual(duplicate.status_code,422,(media,duplicate.text))
            self.assertEqual(duplicate.json()['error']['code'],'invalid_json')
            large=self.client.post('/api/v1/cases',content=b' '*256001+b'{}',headers={'Content-Type':media})
            self.assertEqual(large.status_code,413,(media,large.text))
        overflow=self.client.post('/api/v1/cases',content=b'{"value":1e999}',headers={'Content-Type':'application/problem+json'})
        self.assertEqual(overflow.status_code,422)
        self.assertEqual(overflow.json()['error']['code'],'invalid_json')
        missing=self.client.post('/api/v1/cases',content=b'{"a":1,"a":2}')
        self.assertEqual(missing.status_code,422)
        self.assertEqual(missing.json()['error']['code'],'invalid_json')

    def test_malformed_opaque_refs_return_422(self):
        self.confirm()
        for bad in ([],{},42,True,None):
            selection=self.post(f'cases/{self.cid}/selections',{'request_id':'bad','run_id':bad,'listing_id':'DEMO-006','confirmed':True})
            self.assertEqual(selection.status_code,422,(bad,selection.text))
            consent=self.post(f'cases/{self.cid}/contract-consents',{'confirmed':False,'consent_id':bad})
            self.assertEqual(consent.status_code,422,(bad,consent.text))
            command={'case_id':bad,'request_id':'bad-case','expected_version':0,'operation':'poll_reminders','payload':{}}
            response=self.post('aftercare/commands',command)
            self.assertEqual(response.status_code,422,(bad,response.text))

    def test_history_exposes_immutable_original_snapshots(self):
        result,_,headers=self.review()
        rid=result['review']['review_id']
        first=self.client.get(f'/api/v1/contract-reviews/{rid}/history')
        self.assertEqual(first.status_code,200,first.text)
        original=first.json()['history'][0]
        self.assertEqual(original['review'],result['review'])
        self.post(f'contract-reviews/{rid}/corrections',{'expected_version':1,'corrections':{'landlord':'Corrected example'}})
        latest=self.client.get(f'/api/v1/contract-reviews/{rid}/history').json()['history']
        self.assertEqual(len(latest),2)
        self.assertEqual(latest[0],original)
        self.assertEqual(latest[-1]['review']['version'],2)
        self.post(f'cases/{self.cid}/contract-consents',{'confirmed':False,'consent_id':headers['X-Consent-Id']})
        self.assertEqual(self.client.get(f'/api/v1/contract-reviews/{rid}/history').json()['history'],latest)


    def test_consent_references_restore_after_restart_and_remain_revocable(self):
        self.selected()
        consent=self.post(f'cases/{self.cid}/contract-consents',{'confirmed':True}).json()
        from server.tests.legacy_app import create_app
        resumed=TestClient(create_app(runtime_dir=self.temp.name))
        pending=resumed.get(f'/api/v1/cases/{self.cid}/contract-consents')
        self.assertEqual(pending.status_code,200,pending.text)
        records=pending.json()['consents']
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['consent_id'],consent['consent_id'])
        self.assertTrue(records[0]['active']); self.assertTrue(records[0]['selection_current'])
        self.assertEqual(set(records[0]),{'consent_id','active','recorded_at','selection_current'})
        data=self.client.get('/api/v1/demo-agreements/normal').content
        headers={'X-Consent-Id':consent['consent_id'],'X-Request-Id':'restore-upload',
                 'X-Filename':'agreement.txt','Content-Type':'application/octet-stream'}
        review=resumed.post(f'/api/v1/cases/{self.cid}/contract-reviews',content=data,headers=headers).json()['review']
        rid=review['review_id']
        reloaded=TestClient(create_app(runtime_dir=self.temp.name))
        context=reloaded.get(f'/api/v1/contract-reviews/{rid}/context')
        self.assertEqual(context.status_code,200,context.text)
        self.assertEqual(context.json(),{'case_id':self.cid,'consent_id':consent['consent_id'],'consent_active':True})
        revoked=reloaded.post(f'/api/v1/cases/{self.cid}/contract-consents',json={'confirmed':False,'consent_id':consent['consent_id']})
        self.assertEqual(revoked.status_code,200,revoked.text)
        self.assertFalse(reloaded.get(f'/api/v1/contract-reviews/{rid}/context').json()['consent_active'])
        record=reloaded.get(f'/api/v1/cases/{self.cid}/contract-consents').json()['consents'][0]
        self.assertFalse(record['active']); self.assertIn('revoked_at',record)
        self.assertEqual(reloaded.get(f'/api/v1/contract-reviews/{rid}').json(),review)

    def test_consent_read_context_rechecks_current_confirmed_selection(self):
        result,_,_=self.review()
        rid=result['review']['review_id']
        case=self.client.get(f'/api/v1/cases/{self.cid}').json()
        profile=copy.deepcopy(case['draft']['profile']); profile['weights']['commute']+=1
        self.assertEqual(self.post(f'cases/{self.cid}/profile-drafts',{'expected_revision':1,'profile':profile}).status_code,200)
        record=self.client.get(f'/api/v1/cases/{self.cid}/contract-consents')
        self.assertEqual(record.status_code,200,record.text)
        self.assertTrue(record.json()['consents'][0]['active'])
        self.assertFalse(record.json()['consents'][0]['selection_current'])
        context=self.client.get(f'/api/v1/contract-reviews/{rid}/context').json()
        self.assertFalse(context['consent_active'])


    def assert_stale_review_writes_denied(self, review):
        rid=review['review_id']
        commands=[('corrections',{'expected_version':1,'corrections':{'rent_amount':500}},{}),
                  ('questions',{'expected_version':1},{}),
                  ('decisions',{'expected_version':1,'decision':'approve','note':'Reviewed'},{'X-Operator-Key':'test-private-key'})]
        for operation,body,headers in commands:
            response=self.client.post(f'/api/v1/contract-reviews/{rid}/{operation}',json=body,headers=headers)
            self.assertEqual(response.status_code,403,(operation,response.text))
            self.assertEqual(response.json()['error']['code'],'consent_required')
        self.assertEqual(self.client.get(f'/api/v1/contract-reviews/{rid}').json(),review)
        self.assertEqual(self.client.get(f'/api/v1/contract-reviews/{rid}/export').json(),review)
        history=self.client.get(f'/api/v1/contract-reviews/{rid}/history').json()['history']
        self.assertEqual(len(history),1)
        self.assertEqual(history[0]['review'],review)

    def test_unconfirmed_profile_blocks_all_review_writes_in_same_context(self):
        result,_,_=self.review(True)
        case=self.client.get(f'/api/v1/cases/{self.cid}').json()
        profile=copy.deepcopy(case['draft']['profile']); profile['weights']['commute']+=1
        saved=self.post(f'cases/{self.cid}/profile-drafts',{'expected_revision':1,'profile':profile})
        self.assertEqual(saved.status_code,200,saved.text)
        self.assert_stale_review_writes_denied(result['review'])

    def test_changed_selection_blocks_all_review_writes_in_same_context(self):
        result,_,_=self.review(True)
        case=self.client.get(f'/api/v1/cases/{self.cid}').json()
        run_id=case['evaluations'][-1]['run_id']
        report=self.client.get(f'/api/v1/evaluations/{run_id}').json()['report']
        listing_id=next(item['listing_id'] for item in report['eligible'] if item['listing_id']!='DEMO-006')
        changed=self.post(f'cases/{self.cid}/selections',{'request_id':'reselect','run_id':run_id,'listing_id':listing_id,'confirmed':True})
        self.assertEqual(changed.status_code,200,changed.text)
        self.assert_stale_review_writes_denied(result['review'])


if __name__=='__main__': unittest.main()
