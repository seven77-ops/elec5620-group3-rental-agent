"""Chat proposals share ordinary lease drafts and never save before confirmation."""
from copy import deepcopy
from unittest.mock import patch
import tempfile
import unittest
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.app.common import ApiError
from server.app.lease_drafts.service import LeaseDraftService
from server.tests.test_assistant_api import IntentProvider


class LeaseBridgeTests(unittest.TestCase):
    def setUp(self):
        from server.app.assistant.lease_bridge import LeaseChatBridge
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.provider=IntentProvider();self.provider.by_task['lease_draft_extract']={'fields':[]}
        self.client=TestClient(create_app(runtime_dir=self.temp.name,ai_provider=self.provider))
        self.ctx=next(r.endpoint.__self__.ctx for r in self.client.app.routes if r.path.endswith('/assistant/conversations') and 'POST' in r.methods)
        self.repo=self.ctx.repo;self.bridge=LeaseChatBridge(self.ctx);self.leases=LeaseDraftService(self.ctx)
        self.case=self.client.post('/api/v1/cases',json={}).json();self.cid=self.case['case_id'];self.base='/api/v1/cases/'+self.cid
        self.c=self.client.post(self.base+'/assistant/conversations',json={}).json()
        self.client.post(self.base+'/profile-confirmations',json={'draft_revision':self.case['draft']['revision'],
            'fingerprint':self.case['draft']['fingerprint'],'review_token':self.case['agent1']['review_token']})
        self.run=self.client.post(self.base+'/evaluations',json={'request_id':'run','confirmation_version':1}).json()
        self.rows=self.run['report']['pending_confirmation'];self.select(0)

    def select(self,index):
        r=self.client.post(self.base+'/selections',json={'request_id':'select-'+str(index),'run_id':self.run['run_id'],
            'listing_id':self.rows[index]['listing_id'],'confirmed':True})
        self.assertEqual(r.status_code,200,r.text)

    def prepare(self,entries=None,text='帮我准备租约草稿'):
        self.provider.by_task['lease_draft_extract']={'fields':entries or []}
        return self.bridge.prepare(self.cid,self.c,text)

    def persist(self,result):
        with self.repo.transaction() as db:
            self.bridge.persist(db,result['pending'])
            c=self.repo.get(db,'assistant_conversation',self.c['conversation_id'])
            c['revision']+=1;c['messages'].append({'role':'assistant',**result['answer']})
            self.repo.put(db,'assistant_conversation',c['conversation_id'],c)
        self.c=c;return result['answer']['lease_proposal']

    def body(self,**extra):
        return {'request_id':'apply','expected_revision':self.c['revision'],'confirmed':True,'applicability_confirmed':True,**extra}

    def apply(self,p,body=None,cid=None,conversation=None):
        return self.bridge.apply(cid or self.cid,conversation or self.c['conversation_id'],p['proposal_id'],body or self.body())

    def save(self,fields=None,previous=None):
        source=self.leases.context(self.cid)
        return self.leases.save(self.cid,{'request_id':'manual-'+str(previous['version'] if previous else 0),
            'context_token':source['context_token'],'expected_version':previous['version'] if previous else 0,
            'confirmed':True,'applicability_confirmed':True,'fields':{**source['defaults'],'rental_mode':'whole_property',**(fields or {})},
            **({'draft_id':previous['draft_id']} if previous else {})})

    def assert_error(self,code,callback):
        with self.assertRaises(ApiError) as raised:callback()
        self.assertEqual(raised.exception.status,code)

    def test_prepare_extracts_grounded_partial_fields_and_no_draft_or_proposal_is_saved(self):
        result=self.prepare([{'field':'tenant_names','value':['Zhang San','Alice Chen'],'quote':'租客 Zhang San 和 Alice Chen'},
            {'field':'rent_amount','value':600,'quote':'每周600'},
            {'field':'rent_period','value':'week','quote':'每周600'}],'租客 Zhang San 和 Alice Chen，每周600')
        proposal=result['answer']['lease_proposal'];self.assertEqual(proposal['status'],'pending')
        self.assertEqual(proposal['fields']['tenant_names'],'Zhang San\nAlice Chen')
        self.assertEqual(proposal['fields']['landlord_contact'],'');self.assertIsNone(proposal['fields']['start_date'])
        self.assertIn('landlord_name',[q['field'] for q in proposal['questions']]);self.assertEqual(proposal['base_version'],0)
        self.assertEqual(self.leases.list(self.cid)['items'],[])
        with self.repo.transaction() as db:self.assertIsNone(self.repo.get(db,'assistant_lease_proposal',proposal['proposal_id']))
        self.assertEqual(self.provider.inputs[-1]['task'],'lease_draft_extract')
        self.assertEqual(set(self.provider.inputs[-1]),{'task','message','response_schema'})

    def test_apply_saves_shared_draft_appends_navigation_and_receipt_is_idempotent(self):
        p=self.persist(self.prepare());body=self.body();result=self.apply(p,body)
        self.assertEqual(result['draft']['version'],1);self.assertEqual(len(self.leases.list(self.cid)['items']),1)
        self.assertEqual(result['conversation']['revision'],self.c['revision']+1)
        self.assertEqual(result['conversation']['messages'][-1]['actions'][0]['page'],'contract?mode=draft')
        self.assertEqual(result['conversation']['messages'][0]['lease_proposal']['status'],'applied')
        self.assertEqual(self.apply(p,body),result)
        self.assert_error(409,lambda:self.apply(p,{**body,'expected_revision':0}))
        self.assertEqual(self.leases.read(self.cid,result['draft']['draft_id'])['version'],1)

    def test_missing_explicit_confirmation_never_writes(self):
        p=self.persist(self.prepare())
        for body in (self.body(confirmed=False),self.body(applicability_confirmed=False),self.body(expected_revision=True),{**self.body(),'extra':True}):
            self.assert_error(403 if body.get('confirmed') is False or body.get('applicability_confirmed') is False else 422,lambda:self.apply(p,body))
        self.assertEqual(self.leases.list(self.cid)['items'],[])

    def test_form_saved_version_is_next_chat_base_and_partial_amendment_preserves_contacts(self):
        first=self.save({'tenant_contact':'private@example.com','tenant_names':'Alice Chen','rent_amount':600})
        second=self.save({**first['fields'],'rent_amount':700},first)
        summary=self.bridge.context(self.cid)
        self.assertEqual(summary['base_version'],2);self.assertNotIn('private@example.com',str(summary));self.assertNotIn('Alice Chen',str(summary))
        result=self.prepare([{'field':'bond','value':2800,'quote':'押金2800'}],'押金2800')
        self.assertEqual(result['answer']['lease_proposal']['fields']['rent_amount'],700)
        p=self.persist(result);saved=self.apply(p)['draft']
        self.assertEqual(saved['draft_id'],second['draft_id']);self.assertEqual(saved['version'],3)
        self.assertEqual(saved['fields']['tenant_contact'],'private@example.com')

    def test_changes_during_extraction_or_before_persist_are_rejected(self):
        self.provider.on_call=lambda:self.save()
        self.assert_error(409,lambda:self.prepare());self.provider.on_call=None
        result=self.prepare();self.select(1)
        self.assert_error(409,lambda:self.persist(result))
        with self.repo.transaction() as db:self.assertIsNone(self.repo.get(db,'assistant_lease_proposal',result['pending']['proposal_id']))

    def test_form_save_between_persist_and_apply_obsoletes_card_without_history_write(self):
        p=self.persist(self.prepare());self.save()
        self.assert_error(409,lambda:self.apply(p))
        with self.repo.transaction() as db:
            stored=self.repo.get(db,'assistant_conversation',self.c['conversation_id']);before=deepcopy(stored)
            public=self.bridge.hydrate(db,stored)
            self.assertEqual(public['messages'][0]['lease_proposal']['status'],'obsolete')
            self.assertEqual(stored,before);self.assertEqual(self.repo.get(db,'assistant_conversation',self.c['conversation_id']),before)
        self.assertEqual(len(self.leases.list(self.cid)['items']),1)

    def test_source_revision_and_cross_case_or_conversation_cannot_apply(self):
        p=self.persist(self.prepare());other=self.client.post('/api/v1/cases',json={}).json()['case_id']
        self.assert_error(404,lambda:self.apply(p,cid=other))
        another=self.client.post(self.base+'/assistant/conversations',json={}).json()
        self.assert_error(404,lambda:self.apply(p,conversation=another['conversation_id']))
        self.assert_error(409,lambda:self.apply(p,self.body(expected_revision=0)))
        self.select(1);self.assert_error(409,lambda:self.apply(p))
        self.assertEqual(self.leases.list(self.cid)['items'],[])

    def test_newer_chat_turn_disables_old_pending_proposal(self):
        p=self.persist(self.prepare())
        with self.repo.transaction() as db:
            c=self.repo.get(db,'assistant_conversation',self.c['conversation_id']);c['revision']+=1
            self.repo.put(db,'assistant_conversation',c['conversation_id'],c)
            self.assertEqual(self.bridge.hydrate(db,c)['messages'][0]['lease_proposal']['status'],'obsolete')
        self.assert_error(409,lambda:self.apply(p))

    def test_calendar_month_end_periodic_and_independent_party_fields(self):
        first=self.save({'lease_type':'fixed','lease_term_months':6,'start_date':'2027-08-31','end_date':None,
            'landlord_notice_address':'Owner Street','tenant_notice_address':'Tenant Street'})
        result=self.prepare([{'field':'start_date','value':'2028-02-29','quote':'起租2028-02-29'},
            {'field':'lease_term_months','value':12,'quote':'租期一年'},
            {'field':'agreement_date','value':'2027-10-24','quote':'协议日期2027-10-24'},
            {'field':'landlord_notice_postcode','value':'2016','quote':'房东邮编2016'}],
            '起租2028-02-29，租期一年，协议日期2027-10-24，房东邮编2016')
        fields=result['answer']['lease_proposal']['fields'];self.assertEqual(fields['end_date'],'2029-02-28')
        self.assertEqual(fields['landlord_notice_address'],'Owner Street');self.assertEqual(fields['tenant_notice_address'],'Tenant Street')
        periodic=self.prepare([{'field':'lease_type','value':'periodic','quote':'持续租约，无结束日期'}],'持续租约，无结束日期')
        self.assertIsNone(periodic['answer']['lease_proposal']['fields']['end_date'])
        self.assertIsNone(periodic['answer']['lease_proposal']['fields']['lease_term_months'])

    def test_ungrounded_name_postcode_duration_and_year_are_never_accepted(self):
        cases=[('租客张三',{'field':'tenant_names','value':['Invented Name'],'quote':'租客张三'}),
            ('Unit6903',{'field':'postcode','value':'6903','quote':'Unit6903'}),
            ('租一年半',{'field':'lease_term_months','value':12,'quote':'一年'}),
            ('2027-11-01开始',{'field':'start_date','value':'2026-11-01','quote':'2027-11-01开始'})]
        for text,entry in cases:self.assert_error(502,lambda:self.prepare([entry],text))
        result=self.prepare([], '11月1日开始');self.assertIsNone(result['answer']['lease_proposal']['fields']['start_date'])
        self.assertIn('start_date',[q['field'] for q in result['answer']['lease_proposal']['questions']])

    def test_ambiguous_year_is_clarified_without_accepting_model_guess_or_changing_saved_date(self):
        entry={'field':'start_date','value':'2026-11-01','quote':'11月1日开始'}
        result=self.prepare([entry],'11月1日开始')
        self.assertIsNone(result['answer']['lease_proposal']['fields']['start_date'])
        self.assertNotIn('start_date',result['answer']['lease_proposal']['patch'])
        self.assertIn('年份',result['answer']['content'])
        self.save({'start_date':'2027-08-31'})
        result=self.prepare([entry],'11月1日开始')
        self.assertEqual(result['answer']['lease_proposal']['fields']['start_date'],'2027-08-31')
        self.assertIn('start_date',[q['field'] for q in result['answer']['lease_proposal']['questions']])

    def test_missing_candidate_returns_navigation_without_model_call_or_invention(self):
        case=self.client.post('/api/v1/cases',json={}).json()['case_id']
        c=self.client.post('/api/v1/cases/'+case+'/assistant/conversations',json={}).json();count=len(self.provider.inputs)
        result=self.bridge.prepare(case,c,'帮我生成租约')
        self.assertIsNone(result['pending']);self.assertNotIn('lease_proposal',result['answer'])
        self.assertTrue(result['answer']['actions']);self.assertEqual(len(self.provider.inputs),count)
        self.assertEqual(self.bridge.context(case)['status'],'missing_candidate')

    def tenant_pending(self):
        return self.persist(self.prepare([
            {'field':'tenant_names','value':'Mike','quote':'租客Mike'},
            {'field':'rent_amount','value':650,'quote':'每周650'},
            {'field':'rent_period','value':'week','quote':'每周650'}], '租客Mike，每周650'))

    def test_multiturn_pending_retains_fields_merges_patch_and_latest_explicit_value_wins(self):
        first=self.tenant_pending()
        result=self.prepare([
            {'field':'landlord_name','value':'Austin','quote':'房东Austin'},
            {'field':'rent_amount','value':680,'quote':'每周680'}], '房东Austin，改为每周680')
        proposal=result['answer']['lease_proposal']
        self.assertEqual(proposal['fields']['tenant_names'],'Mike')
        self.assertEqual(proposal['fields']['landlord_name'],'Austin')
        self.assertEqual(proposal['fields']['rent_amount'],680)
        self.assertEqual(proposal['patch'],{'tenant_names':'Mike','rent_amount':680,'rent_period':'week','landlord_name':'Austin'})
        self.assertEqual(proposal['base_version'],0)
        self.assertIn('保留此前待确认的信息',result['answer']['content'])
        self.assertNotIn('Mike',str(self.provider.inputs[-1]))
        self.assertEqual(self.leases.list(self.cid)['items'],[])
        proposal=self.persist(result)
        with self.repo.transaction() as db:
            public=self.bridge.hydrate(db,self.c)
            self.assertEqual(public['messages'][0]['lease_proposal']['status'],'obsolete')
            self.assertEqual(public['messages'][1]['lease_proposal']['status'],'pending')
        self.assert_error(409,lambda:self.apply(first))
        saved=self.apply(proposal)['draft']
        self.assertEqual(saved['version'],1)
        self.assertEqual(saved['fields']['tenant_names'],'Mike')
        self.assertEqual(saved['fields']['landlord_name'],'Austin')
        self.assertEqual(saved['fields']['rent_amount'],680)

    def test_pending_calendar_changes_keep_shared_base_and_unresolved_year_question(self):
        draft=self.save({'start_date':'2027-08-31'})
        first=self.prepare([{'field':'lease_term_months','value':6,'quote':'租期半年'}],'租期半年')
        self.persist(first)
        second=self.prepare([{'field':'start_date','value':'2028-02-29','quote':'改起租2028-02-29'}],'改起租2028-02-29')
        proposal=second['answer']['lease_proposal']
        self.assertEqual(proposal['base_version'],1)
        self.assertEqual(proposal['patch']['lease_term_months'],6)
        self.assertEqual(proposal['patch']['end_date'],'2028-08-29')
        self.assertEqual(proposal['fields']['end_date'],'2028-08-29')
        self.persist(second)
        third=self.prepare([{'field':'start_date','value':'2026-11-01','quote':'11月1日开始'}],'11月1日开始')
        self.persist(third)
        fourth=self.prepare([{'field':'landlord_name','value':'Austin','quote':'房东Austin'}],'房东Austin')
        proposal=self.persist(fourth)
        self.assertEqual(proposal['fields']['start_date'],'2028-02-29')
        self.assertTrue(any(q['field']=='start_date' and '年份' in q['question'] for q in proposal['questions']))
        saved=self.apply(proposal)['draft']
        self.assertEqual(saved['draft_id'],draft['draft_id'])
        self.assertEqual(saved['version'],2)
        self.assertEqual(saved['fields']['end_date'],'2028-08-29')

    def test_pending_fields_do_not_override_newer_form_save(self):
        first=self.save({'tenant_names':'Saved Tenant','rent_amount':600})
        self.tenant_pending()
        self.save({**first['fields'],'tenant_names':'Manual Tenant','rent_amount':700},first)
        result=self.prepare([{'field':'landlord_name','value':'Austin','quote':'房东Austin'}],'房东Austin')
        proposal=result['answer']['lease_proposal']
        self.assertEqual(proposal['base_version'],2)
        self.assertEqual(proposal['fields']['tenant_names'],'Manual Tenant')
        self.assertEqual(proposal['fields']['rent_amount'],700)
        self.assertEqual(proposal['patch'],{'landlord_name':'Austin'})
        self.assertNotIn('保留此前待确认的信息',result['answer']['content'])

    def test_pending_fields_are_not_inherited_after_source_change(self):
        self.tenant_pending();self.select(1)
        proposal=self.prepare()['answer']['lease_proposal']
        self.assertEqual(proposal['fields']['tenant_names'],'')
        self.assertIsNone(proposal['fields']['rent_amount'])
        self.assertEqual(proposal['patch'],{})

    def test_pending_fields_are_not_inherited_after_unrelated_chat_revision(self):
        self.tenant_pending()
        with self.repo.transaction() as db:
            self.c['revision']+=1
            self.repo.put(db,'assistant_conversation',self.c['conversation_id'],self.c)
        proposal=self.prepare()['answer']['lease_proposal']
        self.assertEqual(proposal['fields']['tenant_names'],'')
        self.assertEqual(proposal['patch'],{})

    def test_pending_inheritance_rejects_wrong_case_conversation_and_applied_record(self):
        card=self.tenant_pending()
        with self.repo.transaction() as db:
            original=self.repo.get(db,'assistant_lease_proposal',card['proposal_id'])
        for change in ({'case_id':'other-case'},{'conversation_id':'other-conversation'},{'status':'applied'}):
            with self.subTest(change=change):
                with self.repo.transaction() as db:
                    self.repo.put(db,'assistant_lease_proposal',card['proposal_id'],{**original,**change})
                proposal=self.prepare()['answer']['lease_proposal']
                self.assertEqual(proposal['fields']['tenant_names'],'')
                self.assertEqual(proposal['patch'],{})

    def test_failed_conversation_write_rolls_back_lease_and_both_receipts(self):
        p=self.persist(self.prepare());original=self.repo.put
        def fail(db,kind,key,value):
            if kind=='assistant_conversation':raise RuntimeError('injected conversation write failure')
            return original(db,kind,key,value)
        with patch.object(self.repo,'put',side_effect=fail):
            with self.assertRaises(RuntimeError):self.apply(p)
        self.assertEqual(self.leases.list(self.cid)['items'],[])
        with self.repo.transaction() as db:
            self.assertEqual(self.repo.get(db,'assistant_lease_proposal',p['proposal_id'])['status'],'pending')
            self.assertIsNone(self.repo.get(db,'assistant_lease_apply_receipt',self.cid+':apply'))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM objects WHERE kind IN ('lease_draft','lease_draft_version','lease_draft_receipt')").fetchone()[0],0)
        self.assertEqual(self.apply(p)['draft']['version'],1)
