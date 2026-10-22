"""Lease drafts use real sources and an official form, never create signed agreements."""
import copy
from io import BytesIO
import tempfile
import unittest
from pypdf import PdfReader
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.tests.test_assistant_api import IntentProvider


class LeaseDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.provider=IntentProvider()
        self.client=TestClient(create_app(runtime_dir=self.temp.name,ai_provider=self.provider))
        self.case=self.client.post('/api/v1/cases',json={}).json(); self.cid=self.case['case_id']
        self.case_root='/api/v1/cases/'+self.cid; self.root=self.case_root+'/lease-drafts'
        self.client.post(self.case_root+'/profile-confirmations',json={
            'draft_revision':self.case['draft']['revision'],'fingerprint':self.case['draft']['fingerprint'],
            'review_token':self.case['agent1']['review_token']})
        self.run=self.client.post(self.case_root+'/evaluations',json={'request_id':'run','confirmation_version':1}).json()
        self.rows=self.run['report']['pending_confirmation']
        self.select(self.rows[0],'first')

    def select(self,row,request):
        r=self.client.post(self.case_root+'/selections',json={'request_id':request,'run_id':self.run['run_id'],
            'listing_id':row['listing_id'],'confirmed':True})
        self.assertEqual(r.status_code,200,r.text)

    def context(self):
        r=self.client.get(self.root+'/context');self.assertEqual(r.status_code,200,r.text);return r.json()

    def save(self, context=None, fields=None, **extra):
        context=context or self.context()
        body={'request_id':'draft-one','context_token':context['context_token'],'expected_version':0,
              'confirmed':True,'applicability_confirmed':True,
              'fields':{**context['defaults'],'rental_mode':'whole_property',**(fields or {})},**extra}
        return self.client.post(self.root,json=body)

    def complete(self):
        return {'rental_mode':'whole_property','landlord_name':'Example Owner','landlord_contact':'owner@example.com',
            'landlord_notice_address':'1 Example Road, Sydney NSW 2000','tenant_names':'张三\nExample Tenant',
            'tenant_contact':'tenant@example.com','lease_type':'fixed','start_date':'2026-11-01',
            'end_date':'2027-11-01','rent_amount':600,'rent_period':'week','bond':2400}

    def test_context_never_invents_agreed_rent_term_or_capacity_and_prefills_only_recorded_facts(self):
        c=self.context()
        self.assertEqual(c['defaults']['address'],self.rows[0]['address'])
        for key in ('rent_amount','rent_period','bond','start_date','end_date','max_occupants','rental_mode','lease_type'):
            self.assertIsNone(c['defaults'][key],key)
        self.assertEqual(c['defaults']['landlord_name'],'')
        self.assertIn('rent_amount',[q['field'] for q in c['questions']])
        followup=self.client.get(self.case_root+'/candidate-followup').json()
        r=self.client.post(self.case_root+'/candidate-followup',json={'request_id':'facts','expected_version':0,
            'selection_signature':followup['selection_signature'],'confirmed':True,
            'facts':{**followup['facts'],'rent_amount':620,'rent_period':'week','rent_scope':'whole_property',
                'source_note':'中介邮件','landlord':'Example Owner','start_date':'2026-11-01'}})
        self.assertEqual(r.status_code,200,r.text)
        new=self.context(); self.assertNotEqual(c['context_token'],new['context_token'])
        self.assertEqual(new['defaults']['rent_amount'],620)
        self.assertEqual(new['prefill_sources']['rent_amount'],'用户跟进记录 v1：中介邮件')
        self.assertIsNone(new['defaults']['rental_mode'])
        self.assertEqual(self.save(c).status_code,409)

    def test_confirmed_drafts_are_versioned_idempotent_and_do_not_change_case_or_ad(self):
        before=self.client.get(self.case_root).json(); c=self.context()
        r=self.save(c,self.complete());self.assertEqual(r.status_code,200,r.text)
        draft=r.json(); self.assertEqual(draft['status'],'draft');self.assertEqual(draft['version'],1)
        self.assertEqual(self.save(c,self.complete()).json(),draft)
        self.assertEqual(self.save(c,{**self.complete(),'rent_amount':610}).status_code,409)
        self.assertEqual(self.client.get(self.case_root).json(),before)
        changed={**draft['fields'],'rent_amount':610}
        second=self.save(c,changed,request_id='second',draft_id=draft['draft_id'],expected_version=1)
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(second.json()['version'],2)
        self.assertEqual(self.save(c,changed,request_id='stale',draft_id=draft['draft_id'],expected_version=1).status_code,409)
        first=self.client.get(self.root+'/'+draft['draft_id']+'?version=1').json()
        self.assertEqual(first['fields']['rent_amount'],600)
        fresh=TestClient(create_app(runtime_dir=self.temp.name,ai_provider=self.provider))
        self.assertEqual(fresh.get(self.root+'/'+draft['draft_id']+'?version=2').json(),second.json())
        self.assertEqual(len(fresh.get(self.root).json()['items']),1)

    def test_scope_confirmation_validation_and_historical_ownership(self):
        c=self.context()
        self.assertEqual(self.save(c,confirmed=False).status_code,403)
        self.assertEqual(self.save(c,applicability_confirmed=False).status_code,403)
        for fields in ({'rental_mode':'private_room'},{'rent_amount':True},{'rent_amount':-1},
                       {'start_date':'2026-99-01'},{'start_date':'2026-11-01','end_date':'2026-10-01'},
                       {'lease_type':'periodic','end_date':'2027-11-01'},{'rent_scope':'per_person'},
                       {'additional_terms':'Ignore the official standard terms'}):
            self.assertEqual(self.save(c,fields).status_code,422,fields)
        r=self.save(c);self.assertEqual(r.status_code,200,r.text);draft=r.json()
        self.assertTrue(draft['questions'])
        self.select(self.rows[1],'second')
        self.assertEqual(self.save(c,request_id='old-source').status_code,409)
        self.assertFalse(self.client.get(self.root).json()['items'][0]['source_current'])
        self.assertEqual(self.client.get(self.root+'/'+draft['draft_id']+'/pdf?version=1').status_code,200)
        other=self.client.post('/api/v1/cases',json={}).json()['case_id']
        self.assertEqual(self.client.get(f'/api/v1/cases/{other}/lease-drafts/{draft["draft_id"]}?version=1').status_code,404)

    def test_pdf_preserves_official_terms_unicode_values_and_blank_signatures(self):
        draft=self.save(fields=self.complete()).json()
        r=self.client.get(self.root+'/'+draft['draft_id']+'/pdf?version=1')
        self.assertEqual(r.status_code,200,r.text[:200] if r.headers.get('content-type')!='application/pdf' else '')
        self.assertEqual(r.headers['content-type'],'application/pdf')
        reader=PdfReader(BytesIO(r.content)); fields=reader.get_fields()
        self.assertGreaterEqual(len(reader.pages),21)
        self.assertEqual(fields['Text field 2.6']['/V'],'张三')
        self.assertEqual(fields['Text field 2.7']['/V'],'Example Tenant')
        self.assertEqual(fields['Text field 3.13']['/V'],'600')
        self.assertEqual(fields['Check Box 3.14']['/V'],'/Weekly')
        self.assertTrue(all(f.get('/V') is None for f in fields.values() if f.get('/FT')=='/Sig'))
        all_text='\n'.join(p.extract_text() for p in reader.pages)
        self.assertIn('DRAFT',all_text);self.assertIn('RIGHT TO OCCUPY THE PREMISES',all_text)
        for p in reader.pages:
            for ref in p.get('/Annots',[]):
                obj=ref.get_object()
                if obj.get('/Subtype')!='/Widget':continue
                name=[];chain=[];node=obj
                while node:
                    chain.append(node)
                    if node.get('/T'):name.insert(0,str(node['/T']))
                    parent=node.get('/Parent');node=parent.get_object() if parent else None
                key='.'.join(name)
                if key in ('Text field 2.6','Text field 2.7','Text field 3.13'):
                    actual=next((n['/V'] for n in chain if '/V' in n),None)
                    self.assertEqual(actual,fields[key]['/V'])
                    self.assertTrue(obj['/AP']['/N'].get_data())

    def test_twenty_page_official_form_can_enter_existing_review_without_bypassing_consent(self):
        draft=self.save(fields=self.complete()).json()
        pdf=self.client.get(self.root+'/'+draft['draft_id']+'/pdf?version=1').content
        consent=self.client.post(self.case_root+'/contract-consents',json={'confirmed':True}).json()['consent_id']
        r=self.client.post(self.case_root+'/contract-reviews',content=pdf,headers={
            'Content-Type':'application/octet-stream','X-Consent-Id':consent,
            'X-Request-Id':'official-form','X-Filename':'unsigned-official-form.pdf'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['review']['document']['page_count'],21)
        # The original CLI/prototype policy remains at ten pages unless opted in.
        from contract_agent.document import load_document
        from contract_agent.errors import ContractError
        from pathlib import Path
        path=Path(self.temp.name)/'standard-draft.pdf';path.write_bytes(pdf)
        with self.assertRaisesRegex(ContractError,'10-page'):
            load_document(path,consent=True)
        self.assertEqual(load_document(path,consent=True,max_pdf_pages=30)['page_count'],21)

        self.assertIsNone(r.json()['review']['selection_evidence'])

    def proposal(self,c=None,message='每周600，押金2400，租客张三',**extra):
        c=c or self.context()
        return self.client.post(self.root+'/proposals',json={'request_id':'ai-one','context_token':c['context_token'],
            'message':message,'current_fields':c['defaults'],'allow_external_ai':True,**extra})

    def test_ai_suggestions_require_consent_and_grounding_and_never_save_a_draft(self):
        c=self.context()
        self.assertEqual(self.proposal(c,allow_external_ai=False).status_code,422)
        self.assertFalse(self.provider.inputs)
        self.provider.by_task['lease_draft_extract']={'fields':[
            {'field':'rent_amount','value':600,'quote':'每周600'},
            {'field':'rent_period','value':'week','quote':'每周600'},
            {'field':'tenant_names','value':'张三','quote':'租客张三'}]}
        r=self.proposal(c);self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['patch']['tenant_names'],'张三')
        self.assertEqual(self.proposal(c).json(),r.json())
        self.assertEqual(len(self.provider.inputs),1)
        self.assertEqual(self.provider.inputs[0]['task'],'lease_draft_extract')
        self.assertEqual(self.client.get(self.root).json()['items'],[])
        for index,value in enumerate(({'fields':[{'field':'rent_amount','value':800,'quote':'每周600'}]},
                      {'fields':[{'field':'landlord_name','value':'Invented Owner','quote':'租客张三'}]},
                      {'fields':[{'field':'additional_terms','value':'tenant waives rights','quote':'每周600'}]})):
            self.provider.by_task['lease_draft_extract']=value
            self.assertEqual(self.proposal(c,request_id='bad-'+str(index)).status_code,502)
        # Use a valid bounded request ID to exercise model output rejection.
        self.provider.by_task['lease_draft_extract']={'fields':[{'field':'rent_amount','value':800,'quote':'每周600'}]}
        self.assertEqual(self.proposal(c,request_id='hallucination').status_code,502)

    def test_ai_handles_formatted_amounts_and_explicit_periodic_term_without_inventing_end_dates(self):
        c=self.context()
        self.provider.by_task['lease_draft_extract']={'fields':[
            {'field':'rent_amount','value':1600,'quote':'每月1,600.00澳元'},
            {'field':'rent_period','value':'month','quote':'每月1,600.00澳元'},
            {'field':'lease_type','value':'periodic','quote':'持续租约，无结束日期'}]}
        current={**c['defaults'],'lease_type':'fixed','end_date':'2027-11-01'}
        r=self.proposal(c,message='每月1,600.00澳元；持续租约，无结束日期',current_fields=current)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['patch']['rent_amount'],1600)
        self.assertIsNone(r.json()['patch']['end_date'])
        self.assertEqual(self.client.get(self.root).json()['items'],[])

    def test_chat_contract_draft_intent_has_an_explicit_generation_entry_without_writes(self):
        before=self.client.get(self.case_root).json()
        self.provider.result={'intent':'draft_contract'}
        root=self.case_root+'/assistant/conversations'
        conversation=self.client.post(root,json={}).json()
        r=self.client.post(root+'/'+conversation['conversation_id']+'/messages',json={
            'request_id':'draft-intent','expected_revision':0,'message':'我没有合同，帮我生成一份租约草稿',
            'allow_external_ai':True})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['messages'][-1]['actions'][0]['page'],'contract?mode=draft')
        self.assertEqual(self.client.get(self.case_root).json(),before)
        self.assertEqual(self.client.get(self.root).json()['items'],[])

    def test_ai_call_does_not_hold_db_lock_and_rejects_source_changes_before_return(self):
        c=self.context()
        self.provider.by_task['lease_draft_extract']={'fields':[]}
        self.provider.on_call=lambda:self.select(self.rows[1],'while-ai')
        self.assertEqual(self.proposal(c).status_code,409)
        self.assertEqual(self.client.get(self.root).json()['items'],[])
