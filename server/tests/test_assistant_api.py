"""Assistant integration tests use real catalogue + Agent1; only model transport is injected."""
from copy import deepcopy
import tempfile
import unittest
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.app.ai.provider import ProviderError


class IntentProvider:
    def __init__(self):
        self.result = {'intent':'search','filters':{'suburb':'Rhodes','max_weekly_rent':1500}}
        self.inputs = []
        self.on_call = None
        self.fail = False
        self.by_task = {}

    def public_config(self):
        return {'enabled':True,'configured':True,'provider':'test','model':'test','timeout_seconds':1}

    def call(self, context):
        self.inputs.append(deepcopy(context))
        if self.on_call: self.on_call()
        meta = {'task':context['task'],'provider':'test','model':'test','status':'succeeded','attempted':True}
        if self.fail: raise ProviderError('ai_timeout', {**meta,'status':'failed'})
        return deepcopy(self.by_task.get(context['task'],self.result)), meta


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.provider = IntentProvider()
        self.client = TestClient(create_app(runtime_dir=self.temp.name, ai_provider=self.provider))
        self.case = self.client.post('/api/v1/cases',json={}).json()
        self.base = '/api/v1/cases/'+self.case['case_id']+'/assistant'

    def conversation(self):
        r = self.client.post(self.base+'/conversations',json={})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def send(self,c,request='one',message='找 Rhodes 的房源',**extra):
        return self.client.post(self.base+'/conversations/'+c['conversation_id']+'/messages',json={
            'request_id':request,'expected_revision':c['revision'],'message':message,'allow_external_ai':True,**extra})

    def apply(self,pid,request='apply',confirmed=True):
        return self.client.post(self.base+'/proposals/'+pid+'/apply',json={'request_id':request,'confirmed':confirmed})

    def test_history_real_cards_retries_and_case_ownership(self):
        c = self.conversation(); self.assertEqual(c['revision'],0)
        r = self.send(c); self.assertEqual(r.status_code,200,r.text)
        updated = r.json(); self.assertEqual(updated['revision'],1)
        self.assertEqual(len(updated['messages']),2)
        cards = updated['messages'][-1]['listings']; self.assertTrue(cards)
        for row in cards:
            self.assertEqual(row,self.client.get('/api/v1/listings/'+row['listing_id']).json())
        self.assertEqual(self.send(c).json(),updated); self.assertEqual(len(self.provider.inputs),1)
        self.assertEqual(self.send(c,message='不同输入').status_code,409)
        self.assertEqual(self.send(c,request='stale').status_code,409)
        summaries = self.client.get(self.base+'/conversations').json()['items']
        self.assertEqual(summaries[0]['message_count'],2)
        fresh = TestClient(create_app(runtime_dir=self.temp.name,ai_provider=self.provider))
        path = self.base+'/conversations/'+c['conversation_id']
        self.assertEqual(fresh.get(path).json(),updated)
        other = self.client.post('/api/v1/cases',json={}).json()['case_id']
        self.assertEqual(self.client.get(path.replace(self.case['case_id'],other)).status_code,404)

    def test_intake_remembers_explicit_conditions_and_only_asks_missing_budget_units(self):
        c=self.conversation()
        self.provider.result={'intent':'collect_preferences','brief_patch':{}}
        r=self.send(c,message='我想租房，帮我整理预算、区域和房屋条件。')
        self.assertEqual(r.status_code,200,r.text)
        c=r.json(); self.assertEqual(c['messages'][-1]['agent'],'agent1')
        self.assertIn('区域',c['messages'][-1]['content'])
        self.provider.result={'intent':'collect_preferences','brief_patch':{
            'suburb':'Rhodes','budget_amount':800,'occupants':1,
            'min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':0}}
        r=self.send(c,'details','Rhodes 预算最高800 人数一人 要2b2b 车位无所谓')
        self.assertEqual(r.status_code,200,r.text); c=r.json()
        self.assertEqual(c['rental_brief']['suburb'],'Rhodes')
        self.assertEqual(c['rental_brief']['budget_amount'],800)
        answer=c['messages'][-1]
        self.assertEqual(answer['intent'],'collect_preferences')
        self.assertIn('整套每周',answer['content']); self.assertIn('每人每周',answer['content'])
        self.assertNotIn('请补充区域',answer['content']); self.assertFalse(answer['actions'])
        self.provider.result={'intent':'collect_preferences','brief_patch':{
            'budget_period':'week','budget_scope':'whole_property','rental_mode':'whole_property'}}
        r=self.send(c,'units','整套，每周')
        self.assertEqual(r.status_code,200,r.text); c=r.json()
        self.assertEqual(self.provider.inputs[-1]['rental_brief']['min_bathrooms'],2)
        text=c['messages'][-1]['content']
        for expected in ('Rhodes','890','90','30'): self.assertIn(expected,text)
        self.assertNotIn('展示前 0',text)
        actions=c['messages'][-1]['actions']
        proposal=next(a for a in actions if a['type']=='apply_preferences')
        self.assertIn('整套',' '.join(proposal['summary']))
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)
        # Confirming, rather than merely discussing, is the only durable profile edit.
        applied=self.apply(proposal['proposal_id'])
        self.assertEqual(applied.status_code,200,applied.text)
        profile=applied.json()['case']['draft']['profile']
        self.assertEqual(profile['housing_preferences']['suburb'],'Rhodes')
        self.assertEqual(profile['budget']['scope'],'whole_property')

    def test_preview_changes_update_conversation_brief_without_saving_profile(self):
        self.provider.result={'intent':'collect_preferences','brief_patch':{
            'suburb':'Rhodes','budget_amount':800,'budget_period':'week','budget_scope':'whole_property',
            'occupants':1,'min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':0}}
        c=self.send(self.conversation()).json()
        self.provider.result={'intent':'search','filters':{'max_weekly_rent':900}}
        c=self.send(c,'preview','那900呢？').json()
        self.assertEqual(c['rental_brief']['budget_amount'],900)
        self.provider.result={'intent':'collect_preferences','brief_patch':{}}
        c=self.send(c,'collect-again','把刚才这套条件整理好给我确认').json()
        action=next(a for a in c['messages'][-1]['actions'] if a['type']=='apply_preferences')
        self.assertIn('上限 900',' '.join(action['summary']))
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)

    def test_no_results_alternatives_are_catalogue_backed_and_do_not_relax_conditions(self):
        c=self.conversation()
        self.provider.result={'intent':'search','filters':{
            'suburb':'Rhodes','min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':0,'max_weekly_rent':800}}
        r=self.send(c); self.assertEqual(r.status_code,200,r.text)
        answer=r.json()['messages'][-1]
        for expected in ('890','90','30'): self.assertIn(expected,answer['content'])
        self.assertFalse(answer['listings'])
        suggestions=[a for a in answer['actions'] if a['type']=='suggestion']
        self.assertEqual(len(suggestions),2)
        self.assertIn('890',suggestions[0]['message'])
        self.assertIn('800',suggestions[1]['message']); self.assertIn('不限区域',suggestions[1]['message'])
        self.assertEqual(r.json()['last_search_filters']['max_weekly_rent'],800)
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)

    def test_short_followup_preserves_last_search_constraints_and_can_clear_region(self):
        self.provider.result={'intent':'search','filters':{
            'suburb':'Rhodes','min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':0,'max_weekly_rent':800}}
        c=self.send(self.conversation()).json()
        self.provider.result={'intent':'search','filters':{'max_weekly_rent':900}}
        r=self.send(c,'higher','那900呢？'); self.assertEqual(r.status_code,200,r.text)
        c=r.json(); rows=c['messages'][-1]['listings']
        self.assertTrue(rows)
        self.assertTrue(all(row['suburb']=='Rhodes' and row['bedrooms']>=2 and row['bathrooms']>=2 and row['weekly_rent']<=900 for row in rows))
        self.assertEqual(self.provider.inputs[-1]['last_search_filters']['max_weekly_rent'],800)
        self.provider.result={'intent':'search','filters':{'suburb':None,'max_weekly_rent':800}}
        r=self.send(c,'all-areas','还是800，不限区域'); self.assertEqual(r.status_code,200,r.text)
        c=r.json(); self.assertNotIn('suburb',c['last_search_filters'])
        self.assertTrue(c['messages'][-1]['listings'])
        self.assertTrue(all(row['bathrooms']>=2 and row['weekly_rent']<=800 for row in c['messages'][-1]['listings']))

    def test_brief_schema_rejects_invented_fields_and_invalid_counts(self):
        for index,patch in enumerate(({'occupants':True},{'min_bedrooms':-1},{'budget_period':'fortnight'},
                      {'suburb':'not-a-real-suburb'},{'availability':'verified'})):
            self.provider.result={'intent':'collect_preferences','brief_patch':patch}
            self.assertEqual(self.send(self.conversation(),'bad-brief-'+str(index)).status_code,502,patch)

    def test_monthly_intake_never_runs_a_weekly_search_with_monthly_amount(self):
        self.provider.result={'intent':'collect_preferences','brief_patch':{
            'suburb':'Rhodes','budget_amount':3200,'budget_period':'month','budget_scope':'whole_property',
            'occupants':1,'min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':0}}
        r=self.send(self.conversation()); self.assertEqual(r.status_code,200,r.text)
        c=r.json(); answer=c['messages'][-1]
        self.assertIn('月预算',answer['content']); self.assertIn('每周最高',answer['content'])
        self.assertFalse(answer['listings']); self.assertFalse(answer['actions'])
        self.assertNotIn('last_search_filters',c)

    def test_older_conversation_requests_explicit_history_reconstruction(self):
        c=self.conversation(); repo=self.client.app.state.repository
        with repo.transaction() as db:
            old=repo.get(db,'assistant_conversation',c['conversation_id'])
            old['messages']=[{'message_id':'old-user','role':'user','content':'Rhodes 最高800 1人 2b2b 车位不限',
                'agent':'assistant','created_at':'2026-10-22T00:00:00Z','listings':[],'actions':[]}]
            repo.put(db,'assistant_conversation',c['conversation_id'],old)
        self.provider.result={'intent':'collect_preferences','brief_patch':{'budget_period':'week','budget_scope':'whole_property'}}
        self.provider.by_task['assistant_brief']={'intent':'collect_preferences','brief_patch':{
            'suburb':'Rhodes','budget_amount':800,'occupants':1,'min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':0}}
        r=self.send(c,message='整套，每周'); self.assertEqual(r.status_code,200,r.text)
        self.assertIs(self.provider.inputs[0].get('brief_reconstruction_required'),True)
        self.assertEqual(r.json()['rental_brief']['suburb'],'Rhodes')
        self.assertEqual(r.json()['rental_brief']['budget_scope'],'whole_property')
        self.assertEqual(self.provider.inputs[1]['user_messages'],['Rhodes 最高800 1人 2b2b 车位不限'])

    def test_confirmed_new_profile_replaces_the_old_preview_query(self):
        self.provider.result={'intent':'search','filters':{'suburb':'Rhodes','max_weekly_rent':800}}
        c=self.send(self.conversation()).json()
        self.provider.result={'intent':'update_preferences','preference_patch':{
            'budget':{'maximum':1500},'housing_preferences':{'suburb':'Burwood','min_bedrooms':1}}}
        c=self.send(c,'new-profile').json()
        action=c['messages'][-1]['actions'][0]
        r=self.apply(action['proposal_id']); self.assertEqual(r.status_code,200,r.text)
        c=r.json()['conversation']
        self.provider.result={'intent':'search','filters':{}}
        r=self.send(c,'use-confirmed','按刚确认的条件找房'); self.assertEqual(r.status_code,200,r.text)
        value=r.json(); rows=value['messages'][-1]['listings']
        self.assertEqual(value['last_search_filters']['suburb'],'Burwood')
        self.assertEqual(value['last_search_filters']['max_weekly_rent'],1500)
        self.assertTrue(rows); self.assertTrue(all(row['suburb']=='Burwood' for row in rows))

    def test_consent_and_malformed_result_do_not_persist(self):
        c=self.conversation()
        self.assertEqual(self.send(c,allow_external_ai=False).status_code,422)
        self.assertFalse(self.provider.inputs)
        for result in ({'intent':'invent'}, {'intent':'search','filters':{'max_weekly_rent':True}},
                       {'intent':'search','unexpected':'yes'},{'intent':'search','preference_patch':{'occupants':True}}):
            self.provider.result=result
            self.assertEqual(self.send(c).status_code,502,result)
        self.provider.result={'intent':'search'}
        self.assertEqual(self.send(c).status_code,200)

    def test_proposal_is_explicit_agent1_atomic_and_idempotent(self):
        c=self.conversation()
        self.provider.result={'intent':'update_preferences','preference_patch':{
            'budget':{'maximum':1500},'housing_preferences':{'suburb':'Rhodes','min_bedrooms':2}}}
        r=self.send(c); self.assertEqual(r.status_code,200,r.text)
        action=r.json()['messages'][-1]['actions'][0]; pid=action['proposal_id']
        before=self.client.get('/api/v1/cases/'+self.case['case_id']).json()
        self.assertEqual(before,self.case)
        self.assertEqual(self.apply(pid,confirmed=False).status_code,422)
        applied=self.apply(pid); self.assertEqual(applied.status_code,200,applied.text)
        result=applied.json(); case=result['case']
        self.assertEqual(case['confirmations'][-1]['source'],'agent1')
        self.assertEqual(case['draft']['profile']['budget']['maximum'],1500)
        self.assertEqual(len(case['evaluations']),1)
        run=self.client.get('/api/v1/evaluations/'+case['evaluations'][-1]['run_id']).json()
        self.assertEqual(run['report']['data_mode'],'real_listings')
        self.assertEqual(result['conversation']['revision'],2)
        self.assertEqual(self.apply(pid).json(),result)
        self.assertEqual(self.apply(pid,'another').status_code,409)

    def test_model_task_is_registered_and_proposal_summarizes_inherited_defaults(self):
        from server.app.ai.provider import TASKS
        self.assertIn('assistant_intent',TASKS)
        c=self.conversation(); self.provider.result={'intent':'update_preferences','preference_patch':{'occupants':2}}
        r=self.send(c); self.assertEqual(r.status_code,200,r.text)
        summary=r.json()['messages'][-1]['actions'][0]['summary']
        text=' '.join(summary)
        for expected in ('550','450','AUD/周','按人','含账单','2','2027-02-01','40','12'):
            self.assertIn(expected,text)

    def test_history_is_bounded_and_pending_identity_is_exclusive(self):
        c=self.conversation()
        for index in range(12):
            c=self.send(c,str(index)).json()
        self.assertEqual(len(self.provider.inputs[-1]['history']),20)
        # A simultaneous duplicate reaches the durable reservation before the provider returns.
        snapshot=c
        def duplicate():
            self.assertEqual(self.send(snapshot,'duplicate').status_code,409)
        self.provider.on_call=duplicate
        r=self.send(c,'duplicate'); self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(len(self.provider.inputs),13)

    def test_superseded_slow_attempt_does_not_overwrite_durable_retry(self):
        c=self.conversation(); result=[]
        def takeover():
            self.provider.on_call=None
            repo=self.client.app.state.repository
            with repo.transaction() as db:
                key=self.case['case_id']+':one'
                receipt=repo.get(db,'assistant_turn_receipt',key)
                receipt['started_at']-=61
                repo.put(db,'assistant_turn_receipt',key,receipt)
            result.append(self.send(c))
        self.provider.on_call=takeover
        self.assertEqual(self.send(c).status_code,409)
        self.assertEqual(result[0].status_code,200,result[0].text)
        self.assertEqual(self.send(c).json(),result[0].json())

    def test_model_receives_authoritative_schema_rejecting_observed_qwen_wrong_shape(self):
        from jsonschema import Draft202012Validator
        c=self.conversation(); self.send(c)
        schema=self.provider.inputs[-1]['response_schema']
        validator=Draft202012Validator(schema)
        self.assertTrue(validator.is_valid(self.provider.result))
        bad={'intent':'search','search':{'suburb':'Rhodes','min_bedrooms':2,'sort':'rent_low_to_high'}}
        self.assertFalse(validator.is_valid(bad))
        self.assertFalse(validator.is_valid({'intent':'search','filters':{'sort':'rent_low_to_high'}}))
        self.provider.result=bad
        current=self.client.get(self.base+'/conversations/'+c['conversation_id']).json()
        self.assertEqual(self.send(current,'bad-schema').status_code,502)

    def test_unverified_noise_question_does_not_imply_metrics_exist(self):
        c=self.conversation(); self.provider.result={'intent':'clarify','clarification':'请提供隔音分数。'}
        r=self.send(c,message='哪套房隔音好噪音小？')
        self.assertEqual(r.status_code,200,r.text)
        self.assertIn('没有已核实的噪音',r.json()['messages'][-1]['content'])
        self.assertNotIn('提供隔音分数',r.json()['messages'][-1]['content'])

    def test_explicit_card_selection_overrides_other_valid_model_references(self):
        c=self.send(self.conversation()).json()
        rows=c['messages'][-1]['listings']
        for name in ('compare','explain','select'):
            selected=[rows[2]['listing_id'],rows[1]['listing_id']] if name=='compare' else [rows[2]['listing_id']]
            self.provider.result={'intent':name,'listing_ids':[rows[0]['listing_id']]}
            r=self.send(c,'selected-'+name,listing_ids=selected)
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual([r['listing_id'] for r in r.json()['messages'][-1]['listings']],selected)
            c=r.json()

    def test_clarification_cannot_publish_model_fact_claims(self):
        c=self.conversation()
        self.provider.result={'intent':'clarify','clarification':'这套已经确认免账单，通勤10分钟，可以直接签约。'}
        r=self.send(c,message='请继续')
        self.assertEqual(r.status_code,200,r.text)
        text=r.json()['messages'][-1]['content']
        self.assertNotIn('免账单',text); self.assertNotIn('10分钟',text); self.assertNotIn('直接签约',text)
        self.assertIn('请',text)

    def test_model_card_context_uses_catalogue_facts_and_retains_display_positions(self):
        c=self.send(self.conversation()).json(); original=c['messages'][-1]['listings']
        repo=self.client.app.state.repository
        with repo.transaction() as db:
            saved=repo.get(db,'assistant_conversation',c['conversation_id'])
            saved['messages'][-1]['listings'][0]['address']='stale fake address'
            saved['messages'][-1]['listings'][0]['weekly_rent']=1
            repo.put(db,'assistant_conversation',c['conversation_id'],saved)
        self.provider.result={'intent':'other'}
        self.assertEqual(self.send(c,'context').status_code,200)
        context=self.provider.inputs[-1]
        by_id={r['listing_id']:r for r in context['displayed_listings']}
        for row in original:
            facts=by_id[row['listing_id']]
            for key in ('address','bedrooms','bathrooms','car_spaces','weekly_rent','source_url','rent_scope'):
                self.assertEqual(facts[key],row[key])
        self.assertEqual(context['history'][-1]['display_order'],[
            {'position':index+1,'listing_id':row['listing_id']} for index,row in enumerate(original)])

    def test_context_and_reference_validation_share_latest_hundred_catalogue_ids(self):
        c=self.conversation()
        rows=[]
        for page in (1,2):
            rows.extend(self.client.get(f'/api/v1/listings?page={page}&page_size=100').json()['items'])
        rows=rows[:105]
        repo=self.client.app.state.repository
        with repo.transaction() as db:
            saved=repo.get(db,'assistant_conversation',c['conversation_id'])
            for index in range(0,105,5):
                saved['messages'].append({'message_id':f'card-{index}','role':'assistant','content':'广告',
                    'agent':'agent2','created_at':'2026-10-22T00:00:00Z','listings':rows[index:index+5],'actions':[]})
            repo.put(db,'assistant_conversation',c['conversation_id'],saved)
        self.provider.result={'intent':'other'}
        r=self.send(c,'bounded'); self.assertEqual(r.status_code,200,r.text)
        context=self.provider.inputs[-1]; ids=[row['listing_id'] for row in rows[5:]]
        self.assertEqual(context['displayed_listing_ids'],ids)
        self.assertEqual([row['listing_id'] for row in context['displayed_listings']],ids)
        for entry in context['history']:
            self.assertLessEqual(set(entry['listing_ids']),set(ids))
            self.assertLessEqual({row['listing_id'] for row in entry['display_order']},set(ids))
        # Old cards are deliberately outside both the context and permitted references.
        self.assertEqual(self.send(r.json(),'too-old',listing_ids=[rows[0]['listing_id']]).status_code,422)

    def test_proposal_summary_uses_readable_labels_without_repeating_conditions(self):
        c=self.conversation(); self.provider.result={'intent':'update_preferences','preference_patch':{'occupants':2}}
        r=self.send(c); self.assertEqual(r.status_code,200,r.text)
        answer=r.json()['messages'][-1]; text=' '.join(answer['actions'][0]['summary'])
        for raw in ('private_bedroom','public_transport','walk','demo-usyd','furnished','amenities',"{'",': 0.6'):
            self.assertNotIn(raw,text)
        for label in ('独立卧室','公共交通','步行','家具','费用','设施'):
            self.assertIn(label,text)
        self.assertEqual(answer['content'],'已整理新的租房条件。请核对下方摘要；确认后保存偏好并生成候选。')

    def test_structured_clarification_reason_handles_unknowns_without_keyword_guessing(self):
        c=self.conversation()
        self.provider.result={'intent':'clarify','clarification_reason':'unknown_fact','clarification':'该房源最安静且离学校最近。'}
        r=self.send(c,message='最安静、去学校最近的是哪套？')
        self.assertEqual(r.status_code,200,r.text)
        self.assertIn('没有已核实的噪音',r.json()['messages'][-1]['content'])
        self.assertNotIn('该房源最安静',r.json()['messages'][-1]['content'])
        c=r.json(); self.provider.result={'intent':'clarify','clarification_reason':'reference'}
        r=self.send(c,'reference'); self.assertEqual(r.status_code,200,r.text)
        self.assertIn('房源编号',r.json()['messages'][-1]['content'])
        self.provider.result={'intent':'clarify','clarification_reason':'invented'}
        self.assertEqual(self.send(r.json(),'invalid-reason').status_code,502)

    def test_newer_conversation_turn_invalidates_old_proposal(self):
        c=self.conversation(); self.provider.result={'intent':'update_preferences','preference_patch':{'occupants':2}}
        c=self.send(c).json(); pid=c['messages'][-1]['actions'][0]['proposal_id']
        self.provider.result={'intent':'other'}
        self.assertEqual(self.send(c,'next').status_code,200)
        self.assertEqual(self.apply(pid).status_code,409)

    def test_apply_rolls_back_agent1_when_real_report_fails(self):
        from unittest.mock import patch
        c=self.conversation(); self.provider.result={'intent':'update_preferences','preference_patch':{'occupants':2}}
        c=self.send(c).json(); pid=c['messages'][-1]['actions'][0]['proposal_id']
        with patch('server.app.adapters.real_agent2.RealProfilesAdapter.evaluation',side_effect=ValueError('test failure')):
            self.assertEqual(self.apply(pid).status_code,422)
        after=self.client.get('/api/v1/cases/'+self.case['case_id']).json()
        self.assertEqual(after,self.case)
        self.assertEqual(self.apply(pid).status_code,200)

    def test_proposal_and_request_cross_case_guards(self):
        c=self.conversation(); self.provider.result={'intent':'update_preferences','preference_patch':{'occupants':2}}
        c=self.send(c).json(); pid=c['messages'][-1]['actions'][0]['proposal_id']
        other=self.client.post('/api/v1/cases',json={}).json()['case_id']
        path=self.base.replace(self.case['case_id'],other)+'/proposals/'+pid+'/apply'
        self.assertEqual(self.client.post(path,json={'request_id':'apply','confirmed':True}).status_code,404)
        second=self.conversation()
        self.assertEqual(self.send(second).status_code,409)

    def test_stale_profile_and_conversation_invalidate_proposal(self):
        c=self.conversation(); self.provider.result={'intent':'update_preferences','preference_patch':{'occupants':2}}
        c=self.send(c).json(); pid=c['messages'][-1]['actions'][0]['proposal_id']
        profile=deepcopy(self.case['draft']['profile']); profile['occupants']=3
        self.client.post('/api/v1/cases/'+self.case['case_id']+'/profile-drafts',json={'expected_revision':1,'profile':profile})
        self.assertEqual(self.apply(pid).status_code,409)
        self.assertFalse(self.client.get('/api/v1/cases/'+self.case['case_id']).json()['confirmations'])

    def test_model_outside_transaction_rejects_changed_input(self):
        c=self.conversation()
        def modify():
            p=deepcopy(self.case['draft']['profile']); p['occupants']=2
            result=self.client.post('/api/v1/cases/'+self.case['case_id']+'/profile-drafts',json={'expected_revision':1,'profile':p})
            self.assertEqual(result.status_code,200,result.text)
        self.provider.on_call=modify
        self.assertEqual(self.send(c).status_code,409)
        self.assertEqual(self.client.get(self.base+'/conversations/'+c['conversation_id']).json()['messages'],[])

    def test_recoverable_failure_and_history_context(self):
        c=self.conversation(); self.provider.fail=True
        self.assertEqual(self.send(c).status_code,503)
        self.provider.fail=False; c=self.send(c).json()
        self.provider.result={'intent':'explain','listing_ids':[c['messages'][-1]['listings'][0]['listing_id']]}
        r=self.send(c,'two','第一套怎么样'); self.assertEqual(r.status_code,200,r.text)
        context=self.provider.inputs[-1]
        self.assertEqual(context['task'],'assistant_intent')
        self.assertEqual(len(context['history']),2)
        self.assertIn('draft_profile',context); self.assertIn('confirmed_profile',context)
        self.assertIn('计价',r.json()['messages'][-1]['content'])

    def test_comparison_scoped_references_and_market_coverage(self):
        c=self.send(self.conversation()).json(); rows=c['messages'][-1]['listings'][:2]
        self.provider.result={'intent':'compare','listing_ids':[r['listing_id'] for r in rows]}
        r=self.send(c,'compare','比较这两套'); self.assertEqual(r.status_code,200,r.text)
        self.assertIn(f"{abs(rows[0]['weekly_rent']-rows[1]['weekly_rent']):g}",r.json()['messages'][-1]['content'])
        c=r.json(); self.provider.result={'intent':'compare','listing_ids':['domain:123456']}
        r=self.send(c,'bad-reference'); self.assertEqual(r.status_code,502)
        self.provider.result={'intent':'market','market':{'postcode':'9999','bedrooms':2,'rent_scope':'whole_property'}}
        r=self.send(c,'market'); self.assertEqual(r.status_code,200,r.text)
        self.assertIn('覆盖',r.json()['messages'][-1]['content'])

    def test_clarification_is_targeted_and_stale_confirmation_is_not_current_context(self):
        c=self.conversation()
        confirm={'draft_revision':self.case['draft']['revision'],'fingerprint':self.case['draft']['fingerprint'],'review_token':self.case['agent1']['review_token']}
        self.client.post('/api/v1/cases/'+self.case['case_id']+'/profile-confirmations',json=confirm)
        p=deepcopy(self.case['draft']['profile']); p['occupants']=2
        self.client.post('/api/v1/cases/'+self.case['case_id']+'/profile-drafts',json={'expected_revision':1,'profile':p})
        self.provider.result={'intent':'clarify','clarification':'你说的500是每周还是每月？'}
        r=self.send(c); self.assertEqual(r.status_code,200,r.text)
        self.assertIn('每周还是每月',r.json()['messages'][-1]['content'])
        self.assertIsNone(self.provider.inputs[-1]['confirmed_profile'])

    def test_search_reports_filters_and_rejects_malformed_market_container(self):
        c=self.conversation(); r=self.send(c)
        self.assertIn('Rhodes',r.json()['messages'][-1]['content'])
        self.assertIn('1500',r.json()['messages'][-1]['content'])
        c=r.json()
        for value in ([],{},True):
            self.provider.result={'intent':'market','market':{'postcode':'2000','bedrooms':2,'rent_scope':value}}
            self.assertEqual(self.send(c,'bad-market').status_code,502)

    def test_followup_uses_saved_candidate_and_never_claims_contact_or_verification(self):
        c=self.conversation(); self.provider.result={'intent':'followup'}
        r=self.send(c,message='选好之后该问中介什么？')
        self.assertEqual(r.status_code,200,r.text)
        self.assertIn('先保存',r.json()['messages'][-1]['content'])
        case=self.case
        root='/api/v1/cases/'+case['case_id']
        self.client.post(root+'/profile-confirmations',json={'draft_revision':case['draft']['revision'],
            'fingerprint':case['draft']['fingerprint'],'review_token':case['agent1']['review_token']})
        run=self.client.post(root+'/evaluations',json={'request_id':'run','confirmation_version':1}).json()
        row=run['report']['pending_confirmation'][0]
        selected=self.client.post(root+'/selections',json={'request_id':'select','run_id':run['run_id'],
            'listing_id':row['listing_id'],'confirmed':True}).json()
        r=self.send(r.json(),'follow','就这套，下一步问什么？')
        self.assertEqual(r.status_code,200,r.text)
        turn=r.json()['messages'][-1]
        self.assertIn(row['address'],turn['content'])
        self.assertIn('账单',turn['content'])
        self.assertEqual(turn['actions'][0]['page'],'recommendations?followup=1')
        self.assertEqual(self.provider.inputs[-1]['saved_candidate']['listing_id'],row['listing_id'])
        self.assertEqual(self.client.get(root).json()['selection'],selected)

    def test_ambiguous_profile_and_module_routes(self):
        c=self.conversation()
        self.provider.result={'intent':'update_preferences','preference_patch':{'budget':{'maximum':100}}}
        r=self.send(c); self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['messages'][-1]['intent'],'clarify')
        self.assertFalse(r.json()['messages'][-1]['actions'])
        for intent,page in [('contract','contract?mode=review'),('aftercare','aftercare')]:
            c=r.json(); self.provider.result={'intent':intent}
            r=self.send(c,intent); self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json()['messages'][-1]['actions'][0]['page'],page)


if __name__=='__main__': unittest.main()
