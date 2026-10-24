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
        self.provider.by_task['lease_draft_extract']={'fields':[]}
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

    def test_calendar_month_terms_derive_end_validate_contradictions_and_preserve_versions(self):
        from server.app.lease_drafts import fields as module
        add_months=getattr(module,'add_months',None)
        self.assertIsNotNone(add_months,'calendar month helper is required')
        for start,months,end in [('2026-08-31',6,'2027-02-28'),('2027-08-31',6,'2028-02-29'),
                                 ('2028-02-29',12,'2029-02-28'),('2026-01-31',24,'2028-01-31')]:
            self.assertEqual(add_months(start,months),end)
        c=self.context()
        fields={**self.complete(),'start_date':'2027-08-31','lease_term_months':6,'end_date':None}
        r=self.save(c,fields);self.assertEqual(r.status_code,200,r.text)
        draft=r.json();self.assertEqual(draft['fields']['end_date'],'2028-02-29')
        self.assertEqual(self.save(c,fields).json(),draft)
        changed={**draft['fields'],'start_date':'2027-09-30','end_date':None}
        r=self.save(c,changed,request_id='term-v2',draft_id=draft['draft_id'],expected_version=1)
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['fields']['end_date'],'2028-03-30')
        self.assertEqual(self.client.get(self.root+'/'+draft['draft_id']+'?version=1').json(),draft)
        for bad in ({**fields,'end_date':'2028-03-01'},{**fields,'lease_term_months':7},
                    {**fields,'lease_term_months':True},{**fields,'lease_term_months':6.0},
                    {**fields,'lease_type':'periodic'},{**fields,'lease_type':'periodic','lease_term_months':None,'end_date':'2028-02-29'}):
            self.assertEqual(self.save(c,bad,request_id='contradiction').status_code,422,bad)
        self.assertEqual(self.save(c,{'lease_type':'periodic','lease_term_months':None,'end_date':None},request_id='periodic').status_code,200)

    def test_optional_metadata_fields_map_to_canonical_values_widgets_and_property_address(self):
        c=self.context(); extras={
            'address':'3 Example Street','suburb':'Redfern','state':'NSW','postcode':'2016',
            'landlord_notice_address':'1 Example Road','landlord_notice_suburb':'Burwood',
            'landlord_notice_state':'NSW','landlord_notice_postcode':'2134',
            'tenant_notice_address':'2 Sample Street','tenant_notice_suburb':'Redfern','tenant_notice_state':'NSW','tenant_notice_postcode':'2016',
            'agent_notice_address':'4 Sample Street','agent_notice_suburb':'Burwood','agent_notice_state':'NSW','agent_notice_postcode':'2134',
            'agreement_date':'2026-10-23','agreement_place':'Sydney','landlord_name_2':'Second Owner',
            'landlord_residence':'2 Owner Road','landlord_phone':'0400000001',
            'electrical_repair_name':'Electric Co','electrical_repair_phone':'0400000002',
            'plumbing_repair_name':'Plumber Co','plumbing_repair_phone':'0400000003',
            'other_repair_name':'Repair Co','other_repair_phone':'0400000004'}
        r=self.save(c,{**self.complete(),**extras,'start_date':'2027-08-31','lease_term_months':6,'end_date':None})
        self.assertEqual(r.status_code,200,r.text);draft=r.json()
        expected={'Text field 3.11':'3 Example Street, Redfern NSW 2016','Text field 1.12':'Burwood','Text field 1.13':'NSW','Text field 1.14':'2134',
            'Text field 2.11':'Redfern','Text field 2.12':'NSW','Text field 2.13':'2016',
            'Text field 2.17':'Burwood','Text field 2.18':'NSW','Text field 2.19':'2134',
            'Text field 1.1':'23/10/2026','Text field 1.2':'Sydney','Text field 1.5':'Second Owner',
            'Text field 1.7':'2 Owner Road','Text field 1.8':'0400000001','Text field 4.5':'Electric Co',
            'Text field 4.6':'0400000002','Text field 4.7':'Plumber Co','Text field 4.8':'0400000003',
            'Text field 4.9':'Repair Co','Text field 4.10':'0400000004','Check Box 3.1':'/6 months','Text field 3.10':'29/02/2028'}
        response=self.client.get(self.root+'/'+draft['draft_id']+'/pdf?version=1')
        self.assertEqual(response.status_code,200,response.text[:200] if response.headers.get('content-type')!='application/pdf' else '')
        reader=PdfReader(BytesIO(response.content)); saved=reader.get_fields()
        from server.app.lease_drafts.pdf import widget_name
        for name,value in expected.items():self.assertEqual(str(saved[name].get('/V')),value,name)
        witnessed=set()
        for page in reader.pages:
            for ref in page.get('/Annots',[]):
                obj=ref.get_object();name=widget_name(obj)
                if name not in expected:continue
                node=obj
                while '/V' not in node and node.get('/Parent'):node=node['/Parent'].get_object()
                if name.startswith('Check Box'):
                    expected_widget=expected[name] if expected[name] in obj['/AP']['/N'] else '/Off'
                    self.assertEqual(str(node.get('/V')),expected_widget,name)
                    self.assertEqual(str(obj.get('/AS')),expected_widget,name)
                else:self.assertEqual(str(node.get('/V')),expected[name],name)
                self.assertTrue(obj['/AP']['/N'])
                if not name.startswith('Check Box'):self.assertTrue(obj['/AP']['/N'].get_data())
                witnessed.add(name)
        self.assertEqual(witnessed,set(expected))
        self.assertTrue(all(not f.get('/V') for f in saved.values() if f.get('/FT')=='/Sig'))
        self.assertEqual(self.client.get(self.root+'/'+draft['draft_id']+'?version=1').json()['fields']['postcode'],'2016')

    def test_pdf_calendar_custom_natural_months_and_legacy_missing_new_fields(self):
        from server.app.lease_drafts.pdf import field_values,generate_pdf
        c=self.context();r=self.save(c,self.complete());self.assertEqual(r.status_code,200,r.text)
        draft=r.json()
        from server.app.lease_drafts.fields import DEFAULTS
        old_keys=set(DEFAULTS)-{'suburb','state','postcode','landlord_notice_suburb','landlord_notice_state','landlord_notice_postcode',
            'tenant_notice_suburb','tenant_notice_state','tenant_notice_postcode','agent_notice_suburb','agent_notice_state','agent_notice_postcode',
            'agreement_place','landlord_name_2','landlord_residence','landlord_phone','electrical_repair_name','electrical_repair_phone',
            'plumbing_repair_name','plumbing_repair_phone','other_repair_name','other_repair_phone','agreement_date','lease_term_months'}
        old={k:v for k,v in draft['fields'].items() if k in old_keys}
        # Legacy payload remains accepted; legacy saved record is not rewritten on read/download.
        self.assertEqual(self.client.post(self.root,json={'request_id':'legacy-payload','context_token':c['context_token'],
            'expected_version':0,'confirmed':True,'applicability_confirmed':True,'fields':old}).status_code,200)
        legacy={**draft,'fields':old};repo=self.client.app.state.repository
        with repo.transaction() as db:repo.put(db,'lease_draft_version',draft['draft_id']+':1',legacy)
        before=self.client.get(self.root+'/'+draft['draft_id']+'?version=1').json()
        self.assertEqual(self.client.get(self.root+'/'+draft['draft_id']+'/pdf?version=1').status_code,200)
        self.assertEqual(self.client.get(self.root+'/'+draft['draft_id']+'?version=1').json(),before)
        for start,end,term,text in [('2027-08-31','2028-02-29','/6 months',None),
                                  ('2026-11-01','2028-03-01','/Other','16 months'),
                                  ('2026-11-01','2026-11-20','/Other','19 days')]:
            values=field_values({**old,'lease_type':'fixed','start_date':start,'end_date':end})
            self.assertEqual(values['Check Box 3.1'],term)
            if text:self.assertEqual(values['Text field 3.2'],text)
        # Already-complete freeform addresses are not duplicated by optional structured fields.
        values=field_values({**old,'address':'3 Example Street, Redfern NSW 2016','suburb':'Redfern','state':'NSW','postcode':'2016'})
        self.assertEqual(values['Text field 3.11'],'3 Example Street, Redfern NSW 2016')

    def test_new_field_validation_and_ai_calendar_patches_remain_grounded(self):
        c=self.context()
        current={**c['defaults'],'lease_type':'fixed','start_date':'2027-08-31','lease_term_months':6,'end_date':'2028-02-29'}
        for message,entries,end,months in [
            ('起租2028-02-29，固定租期一年',[{'field':'start_date','value':'2028-02-29','quote':'起租2028-02-29'},
                {'field':'lease_term_months','value':12,'quote':'固定租期一年'}],'2029-02-28',12),
            ('改起租日期为2027-09-30',[{'field':'start_date','value':'2027-09-30','quote':'改起租日期为2027-09-30'}],'2028-03-30',6),
            ('改为三年固定租期',[{'field':'lease_term_months','value':36,'quote':'三年固定租期'}],'2030-08-31',36),
            ('结束日期改为2029-01-01',[{'field':'end_date','value':'2029-01-01','quote':'结束日期改为2029-01-01'}],'2029-01-01',None),
            ('持续租约，无结束日期',[{'field':'lease_type','value':'periodic','quote':'持续租约，无结束日期'}],None,None)]:
            self.provider.by_task['lease_draft_extract']={'fields':entries}
            r=self.proposal(c,message=message,current_fields=current,request_id='calendar-'+str(months)+'-'+str(end))
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json()['patch']['end_date'],end)
            self.assertEqual(r.json()['patch']['lease_term_months'],months)
        self.provider.by_task['lease_draft_extract']={'fields':[{'field':'lease_term_months','value':12,'quote':'每周12澳元'}]}
        self.assertEqual(self.proposal(c,message='每周12澳元',request_id='ungrounded-duration').status_code,502)
        self.provider.by_task['lease_draft_extract']={'fields':[{'field':'lease_term_months','value':6,'quote':'租期12个月'}]}
        self.assertEqual(self.proposal(c,message='租期12个月',request_id='contradicting-duration').status_code,502)
        for extra in ({'postcode':'201'},{'postcode':'abcd'},{'agreement_date':'2026-02-30'},{'landlord_phone':True}):
            self.assertEqual(self.save(c,extra,request_id='bad-new-field').status_code,422)
        # Explicit optional strings are quoted; an address suggestion does not bypass AI grounding.
        self.provider.by_task['lease_draft_extract']={'fields':[{'field':'suburb','value':'Redfern','quote':'住在Burwood'}]}
        self.assertEqual(self.proposal(c,message='住在Burwood',request_id='ungrounded-suburb').status_code,502)
        self.assertEqual(self.client.get(self.root).json()['items'],[])

    def test_preset_checkbox_without_dates_and_explicit_end_switches_periodic_to_custom(self):
        from server.app.lease_drafts.fields import DEFAULTS
        from server.app.lease_drafts.pdf import field_values
        values=field_values({**DEFAULTS,'lease_type':'fixed','lease_term_months':12})
        self.assertEqual(values['Check Box 3.1'],'/12 months')
        c=self.context();current={**c['defaults'],'lease_type':'periodic','start_date':'2026-11-01'}
        self.provider.by_task['lease_draft_extract']={'fields':[{'field':'end_date','value':'2027-11-01','quote':'结束日期2027-11-01'}]}
        r=self.proposal(c,message='结束日期2027-11-01',current_fields=current)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['patch']['lease_type'],'fixed')
        self.assertIsNone(r.json()['patch']['lease_term_months'])
        self.provider.by_task['lease_draft_extract']={'fields':[{'field':'lease_term_months','value':12,'quote':'租期十一年'}]}
        self.assertEqual(self.proposal(c,message='租期十一年',request_id='wrong-chinese-duration').status_code,502)

    def test_partial_metadata_never_duplicates_an_existing_full_property_address(self):
        from server.app.lease_drafts.fields import DEFAULTS
        from server.app.lease_drafts.pdf import field_values
        address='3 Example Street, Redfern NSW 2016'
        for metadata in ({'suburb':'Redfern'},{'state':'NSW'},{'postcode':'2016'},
                         {'suburb':'Redfern','postcode':'2016'},{'suburb':'Redfern','state':'NSW'}):
            self.assertEqual(field_values({**DEFAULTS,'address':address,**metadata})['Text field 3.11'],address)
        self.assertEqual(field_values({**DEFAULTS,'address':'Unit 2016, 3 Example Street','postcode':'2016'})['Text field 3.11'],
            'Unit 2016, 3 Example Street, 2016')

    def test_ai_postcodes_need_postal_semantics_never_unit_numbers(self):
        c=self.context()
        for field in ('postcode','landlord_notice_postcode','tenant_notice_postcode','agent_notice_postcode'):
            self.provider.by_task['lease_draft_extract']={'fields':[{'field':field,'value':'6903','quote':'Unit6903'}]}
            self.assertEqual(self.proposal(c,message='Unit6903',request_id='unit-'+field).status_code,502)
        for index,(quote,field) in enumerate((('邮编2016','postcode'),('郵編：2016','landlord_notice_postcode'),
                ('postcode is 2016','tenant_notice_postcode'),('postal code: 2016','agent_notice_postcode'),
                ('Redfern NSW2016','postcode'),('Redfern NSW 2016','postcode'))):
            self.provider.by_task['lease_draft_extract']={'fields':[{'field':field,'value':'2016','quote':quote}]}
            r=self.proposal(c,message=quote,request_id='postal-'+str(index))
            self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['patch'][field],'2016')
        self.provider.by_task['lease_draft_extract']={'fields':[{'field':'postcode','value':'6903','quote':'Unit6903，邮编2016'}]}
        self.assertEqual(self.proposal(c,message='Unit6903，邮编2016',request_id='wrong-postal-token').status_code,502)

    def test_context_prefills_only_selected_property_locality_from_explicit_source_fields(self):
        before=self.client.get(self.case_root).json();context=self.context();snapshot=before['selection']['listing_snapshot']
        self.assertEqual(context['defaults']['suburb'],snapshot['suburb'])
        self.assertEqual(context['defaults']['state'],'NSW')
        self.assertEqual(context['defaults']['postcode'],snapshot['postcode'])
        for name in ('suburb','state','postcode'):
            self.assertIn('候选',context['prefill_sources'][name])
        for prefix in ('landlord_notice','tenant_notice','agent_notice'):
            for name in ('suburb','state','postcode'):
                self.assertEqual(context['defaults'][prefix+'_'+name],'')
        from server.app.lease_drafts.pdf import field_values
        self.assertIn('NSW '+snapshot['postcode'],field_values(context['defaults'])['Text field 3.11'])
        self.assertEqual(self.client.get(self.case_root).json(),before)

    def test_ai_literal_tenant_name_arrays_normalize_without_accepting_invented_names(self):
        c=self.context();message='租客 Zhang San 和 Alice Chen，每周600澳元'
        self.provider.by_task['lease_draft_extract']={'fields':[
            {'field':'tenant_names','value':['Zhang San','Alice Chen'],'quote':'租客 Zhang San 和 Alice Chen'},
            {'field':'rent_amount','value':600,'quote':'每周600澳元'},
            {'field':'rent_period','value':'week','quote':'每周600澳元'}]}
        r=self.proposal(c,message=message)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['patch']['tenant_names'],'Zhang San\nAlice Chen')
        self.assertEqual(r.json()['patch']['rent_period'],'week')
        self.assertEqual(self.proposal(c,message=message).json(),r.json())
        self.assertEqual(len(self.provider.inputs),1)
        for index,value in enumerate((['Invented Person'],['Zhang San',True],['Zhang San',None],[],[''],[' '*3],['Zhang San']*7,['X'*81])):
            self.provider.by_task['lease_draft_extract']={'fields':[{'field':'tenant_names','value':value,'quote':'租客 Zhang San 和 Alice Chen'}]}
            self.assertEqual(self.proposal(c,message=message,request_id='bad-tenant-array-'+str(index)).status_code,502)
        self.assertEqual(self.client.get(self.root).json()['items'],[])

    def test_compound_durations_never_truncate_into_supported_calendar_presets(self):
        from server.app.lease_drafts.ai import duration_grounded,grounded_patch
        from server.app.common import ApiError
        for quote in ('1 year and a half','租一年半','租两年半','租一年六个月','租两年三个月','租1年半','租2年3个月','租一年又半年',
                      '1 year and a half','1 year 6 months','2 years and 3 months','1year6months','one year plus 6 months'):
            for months in (6,12,24,36,60):
                self.assertFalse(duration_grounded(months,quote),(months,quote))
            for months in (12,24):
                with self.assertRaises(ApiError):
                    grounded_patch({'fields':[{'field':'lease_term_months','value':months,'quote':quote}]},quote)
        for months,quote,message in ((12,'一年','租一年半'),(24,'两年','租两年半'),
                                     (6,'六个月','租一年六个月'),(24,'两年','租两年三个月'),
                                     (12,'1 year','1 year and a half'),(12,'1 year','1 year 6 months'),
                                     (6,'6 months','1 year 6 months')):
            with self.assertRaises(ApiError):
                grounded_patch({'fields':[{'field':'lease_term_months','value':months,'quote':quote}]},message)
        changed=grounded_patch({'fields':[{'field':'lease_term_months','value':12,'quote':'改为一年'}]},'原来一年半，改为一年')
        self.assertEqual(changed['lease_term_months'],12)
        for months,quote in ((6,'租半年'),(6,'租六个月'),(12,'租一年'),(24,'租两年'),
                             (36,'租三年'),(60,'租五年'),(12,'租12个月'),(24,'租2年'),
                             (12,'1 year'),(6,'6 months')):
            self.assertTrue(duration_grounded(months,quote),(months,quote))
