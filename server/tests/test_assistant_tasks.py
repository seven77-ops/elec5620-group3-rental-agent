"""Read-only assistant tasks use current catalogue facts and explicit user context."""
from copy import deepcopy
import unittest
from jsonschema import Draft202012Validator
from server.tests import test_assistant_api as harness
from server.app.assistant.intents import response_schema


class AssistantTaskTests(unittest.TestCase):
    setUp=harness.AssistantTests.setUp
    conversation=harness.AssistantTests.conversation
    send=harness.AssistantTests.send

    def shown(self):
        result=self.send(self.conversation()).json()
        return result,result['messages'][-1]['listings']

    def test_comparison_uses_explicit_query_and_parking_is_not_a_personal_advantage(self):
        self.provider.result={'intent':'search','filters':{'suburb':'Rhodes','max_weekly_rent':1500,'min_car_spaces':0}}
        c,rows=self.shown(); selected=[r['listing_id'] for r in rows[:2]]
        self.provider.result={'intent':'compare','listing_ids':selected}
        response=self.send(c,'compare','比较这两套，我不需要车位')
        self.assertEqual(response.status_code,200,response.text)
        comparison=response.json()['messages'][-1]['comparison']
        self.assertIn('查询',comparison['basis'])
        self.assertEqual([i['listing_id'] for i in comparison['items']],selected)
        self.assertTrue(all(any('车位无要求' in x for x in i['matches']) for i in comparison['items']))
        self.assertTrue(all(i['to_verify'] for i in comparison['items']))
        self.assertNotIn('%',str(comparison))
        self.assertIn('计价对象',comparison['summary'])
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)

    def test_comparison_without_explicit_context_never_uses_example_profile(self):
        c,rows=self.shown(); repo=self.client.app.state.repository
        with repo.transaction() as db:
            stored=repo.get(db,'assistant_conversation',c['conversation_id'])
            stored.pop('last_search_filters',None)
            repo.put(db,'assistant_conversation',c['conversation_id'],stored)
        self.provider.result={'intent':'compare','listing_ids':[r['listing_id'] for r in rows[:2]]}
        response=self.send(c,'compare')
        self.assertEqual(response.status_code,200,response.text)
        value=response.json()['messages'][-1]['comparison']
        self.assertIsNone(value['recommended_listing_id'])
        self.assertIn('未提供',value['basis'])
        self.assertNotIn('550',str(value)); self.assertNotIn('450',str(value))

    def test_comparison_current_brief_overrides_old_query_and_monthly_budget_is_not_weekly(self):
        c,rows=self.shown(); repo=self.client.app.state.repository
        with repo.transaction() as db:
            stored=repo.get(db,'assistant_conversation',c['conversation_id'])
            stored.update(dialogue_mode='collect_preferences',rental_brief={'suburb':'Burwood','budget_amount':5000,'budget_period':'month','min_car_spaces':0})
            repo.put(db,'assistant_conversation',c['conversation_id'],stored)
        self.provider.result={'intent':'compare','listing_ids':[r['listing_id'] for r in rows[:2]]}
        result=self.send(c,'compare').json()['messages'][-1]['comparison']
        self.assertTrue(all(any('区域' in s for s in item['tradeoffs']) for item in result['items']))
        self.assertFalse(any('预算内' in s for item in result['items'] for s in item['matches']))
        self.assertIn('月预算',result['summary'])

    def test_workflow_compare_then_cheapest_enquiry_is_readonly(self):
        c,rows=self.shown(); selected=[r['listing_id'] for r in rows[:2]]
        self.provider.result={'intent':'workflow','steps':[{'kind':'compare','reference':'selected'},
            {'kind':'prepare_enquiry','reference':'cheapest'}]}
        response=self.send(c,'workflow','比较这两套，再给标价较低的那套写询问',listing_ids=selected)
        self.assertEqual(response.status_code,200,response.text)
        answer=response.json()['messages'][-1]
        self.assertEqual([s['status'] for s in answer['task_steps']],['completed','completed'])
        self.assertEqual(answer['enquiry']['listing_id'],min(rows[:2],key=lambda r:r['weekly_rent'])['listing_id'])
        self.assertTrue(answer['enquiry']['questions'])
        self.assertIn('账单',answer['enquiry']['body'])
        self.assertEqual({r['listing_id'] for r in answer['listings']},set(selected))
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)

    def test_workflow_search_can_feed_previous_rows_and_unresolved_never_invents_ids(self):
        self.provider.result={'intent':'workflow','steps':[{'kind':'search','filters':{'suburb':'Rhodes','max_weekly_rent':1500}},
            {'kind':'compare','reference':'previous'},{'kind':'prepare_enquiry','reference':'cheapest'}]}
        response=self.send(self.conversation(),'flow')
        self.assertEqual(response.status_code,200,response.text)
        answer=response.json()['messages'][-1]
        self.assertTrue(all(s['status']=='completed' for s in answer['task_steps']))
        self.assertEqual(response.json()['last_search_filters']['suburb'],'Rhodes')
        self.provider.result={'intent':'workflow','steps':[{'kind':'prepare_enquiry','reference':'previous'}]}
        answer=self.send(self.conversation(),'unresolved').json()['messages'][-1]
        self.assertEqual(answer['task_steps'][0]['status'],'needs_input')
        self.assertNotIn('enquiry',answer); self.assertFalse(answer['listings'])

    def test_workflow_strict_schema_and_model_boundary_reject_writes_and_unknown_refs(self):
        validator=Draft202012Validator(response_schema())
        valid={'intent':'workflow','steps':[{'kind':'compare','reference':'selected'}]}
        self.assertTrue(validator.is_valid(valid))
        bad=[{'intent':'workflow','steps':[]},{'intent':'workflow','steps':[{'kind':'save'}]},
            {'intent':'workflow','steps':[{'kind':'search','filters':{'max_weekly_rent':True}}]},
            {'intent':'workflow','steps':[{'kind':'explain','listing_ids':['invented']}]},
            {'intent':'workflow','steps':[{'kind':'prepare_enquiry'},{'kind':'prepare_enquiry'}]},
            {'intent':'workflow','steps':[{'kind':'explain','reference':'all'}]}]
        for index,value in enumerate(bad):
            self.provider.result=value
            response=self.send(self.conversation(),'bad'+str(index))
            self.assertEqual(response.status_code,502,(value,response.text))

    def test_unknown_quietness_becomes_useful_verification_checklist(self):
        self.provider.result={'intent':'clarify','clarification_reason':'unknown_fact'}
        response=self.send(self.conversation(),message='哪套安静隔音好？')
        self.assertEqual(response.status_code,200,response.text)
        answer=response.json()['messages'][-1]
        self.assertTrue(any('噪音' in item or '隔音' in item for item in answer['verification_checklist']['items']))
        self.assertNotIn('请先核实这些事实',answer['content'])

    def test_negative_feedback_offers_explicit_suggestions_without_saving_preferences(self):
        self.provider.result={'intent':'other'}
        answer=self.send(self.conversation(),message='这些都不满意').json()['messages'][-1]
        self.assertIn('哪',answer['content'])
        self.assertTrue(any(a['type']=='suggestion' for a in answer['actions']))
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)

    def test_selected_cards_bound_initial_previous_reference_and_cheapest(self):
        c,rows=self.shown(); selected=[row['listing_id'] for row in rows[2:4]]
        self.provider.result={'intent':'workflow','steps':[{'kind':'compare','reference':'previous'},
            {'kind':'prepare_enquiry','reference':'cheapest'}]}
        response=self.send(c,'bound-previous',listing_ids=selected)
        self.assertEqual(response.status_code,200,response.text)
        answer=response.json()['messages'][-1]
        self.assertEqual([item['listing_id'] for item in answer['comparison']['items']],selected)
        self.assertEqual(answer['enquiry']['listing_id'],min(rows[2:4],key=lambda row:row['weekly_rent'])['listing_id'])

    def test_only_valid_current_confirmed_profile_can_supply_comparison_needs(self):
        c,rows=self.shown(); repo=self.client.app.state.repository
        with repo.transaction() as db:
            stored=repo.get(db,'assistant_conversation',c['conversation_id']);stored.pop('last_search_filters',None)
            repo.put(db,'assistant_conversation',c['conversation_id'],stored)
        root='/api/v1/cases/'+self.case['case_id']
        confirmed=self.client.post(root+'/profile-confirmations',json={'draft_revision':self.case['draft']['revision'],
            'fingerprint':self.case['draft']['fingerprint'],'review_token':self.case['agent1']['review_token']})
        self.assertEqual(confirmed.status_code,200,confirmed.text)
        self.provider.result={'intent':'compare','listing_ids':[r['listing_id'] for r in rows[:2]]}
        response=self.send(c,'valid-confirmed');self.assertEqual(response.status_code,200,response.text)
        c=response.json();comparison=c['messages'][-1]['comparison']
        self.assertIn('已确认',comparison['basis']);self.assertTrue(comparison['items'])
        profile=deepcopy(self.case['draft']['profile']);profile['occupants']=2
        self.client.post(root+'/profile-drafts',json={'expected_revision':self.case['draft']['revision'],'profile':profile})
        response=self.send(c,'stale-confirmed');self.assertEqual(response.status_code,200,response.text)
        self.assertIsNone(response.json()['messages'][-1]['comparison']['recommended_listing_id'])

    def test_open_plan_count_is_explicit_in_personal_matches(self):
        from server.app.assistant.comparison import build_comparison
        rows=self.client.get('/api/v1/listings',params={'page_size':100}).json()['items']
        studio=next(row for row in rows if row['advertised_bedrooms']==0)
        result=build_comparison([studio],self.case,{'rental_brief':{'min_bedrooms':1}})
        self.assertTrue(any('开放式' in value for value in result['items'][0]['matches']))

    def test_no_listing_is_recommended_when_every_candidate_violates_explicit_needs(self):
        from server.app.assistant.comparison import build_comparison
        c,rows=self.shown()
        for brief in ({'suburb':'Burwood'},{'min_bathrooms':99},{'budget_amount':1,'budget_period':'week'}):
            result=build_comparison(rows[:2],self.case,{'rental_brief':brief})
            self.assertIsNone(result['recommended_listing_id'],brief)
            self.assertIn('没有完全符合',result['summary'])
            self.assertTrue(all(item['tradeoffs'] for item in result['items']))

    def test_confirmed_independent_bedroom_requirement_rejects_known_open_plan(self):
        from server.app.assistant.comparison import build_comparison
        rows=self.client.get('/api/v1/listings',params={'page_size':100}).json()['items']
        studio=next(row for row in rows if row['advertised_bedrooms']==0)
        case=deepcopy(self.case);profile=deepcopy(case['draft']['profile'])
        profile['hard_requirements']=['private_bedroom'];profile['budget']['maximum']=100000
        profile['housing_preferences']={'min_bedrooms':1}
        case['confirmations']=[{'profile':profile,'fingerprint':case['draft']['fingerprint'],'draft_revision':case['draft']['revision']}]
        case['agent1']['state']='Confirmed'
        result=build_comparison([studio],case,{})
        self.assertIsNone(result['recommended_listing_id'])
        self.assertTrue(any('独立卧室' in value for value in result['items'][0]['tradeoffs']))


class LeaseAssistantIntegrationTests(unittest.TestCase):
    def setUp(self):
        from server.tests.test_assistant_lease_bridge import LeaseBridgeTests
        LeaseBridgeTests.setUp(self)
    def select(self,index):
        from server.tests.test_assistant_lease_bridge import LeaseBridgeTests
        return LeaseBridgeTests.select(self,index)
    def send(self,c,request='chat',message='租客 Zhang San，每周600，帮我准备租约草稿'):
        return self.client.post(self.base+'/assistant/conversations/'+c['conversation_id']+'/messages',json={
            'request_id':request,'expected_revision':c['revision'],'message':message,'allow_external_ai':True})

    def test_send_creates_review_only_proposal_and_apply_route_saves_shared_draft(self):
        self.provider.result={'intent':'draft_contract'}
        self.provider.by_task['lease_draft_extract']={'fields':[
            {'field':'tenant_names','value':['Zhang San'],'quote':'租客 Zhang San'},
            {'field':'rent_amount','value':600,'quote':'每周600'},{'field':'rent_period','value':'week','quote':'每周600'}]}
        response=self.send(self.c)
        self.assertEqual(response.status_code,200,response.text)
        conversation=response.json();proposal=conversation['messages'][-1]['lease_proposal']
        self.assertEqual(proposal['status'],'pending');self.assertEqual(self.leases.list(self.cid)['items'],[])
        self.assertEqual([call['task'] for call in conversation['messages'][-1]['calls']],['assistant_intent','lease_draft_extract'])
        self.assertEqual(self.send(self.c).json(),conversation)
        self.assertEqual(self.provider.inputs[0]['lease_draft']['status'],'ready')
        path=self.base+'/assistant/conversations/'+self.c['conversation_id']+'/lease-proposals/'+proposal['proposal_id']+'/apply'
        body={'request_id':'apply-chat','expected_revision':conversation['revision'],'confirmed':True,'applicability_confirmed':True}
        applied=self.client.post(path,json=body)
        self.assertEqual(applied.status_code,200,applied.text)
        self.assertEqual(applied.json()['draft']['fields']['tenant_names'],'Zhang San')
        self.assertEqual(self.client.post(path,json=body).json(),applied.json())
        read=self.client.get(self.base+'/assistant/conversations/'+self.c['conversation_id']).json()
        self.assertEqual(read['messages'][-2]['lease_proposal']['status'],'applied')
        self.assertEqual(self.leases.read(self.cid,applied.json()['draft']['draft_id'])['version'],1)

    def test_read_hydrates_obsolete_preview_and_routing_context_contains_no_stored_lease_contacts(self):
        self.provider.result={'intent':'draft_contract'}
        conversation=self.send(self.c).json()
        self.assertIn('lease_proposal',conversation['messages'][-1])
        from server.tests.test_assistant_lease_bridge import LeaseBridgeTests
        LeaseBridgeTests.save(self,{'landlord_contact':'private-lease@example.com'})
        read=self.client.get(self.base+'/assistant/conversations/'+self.c['conversation_id']).json()
        self.assertEqual(read['messages'][-1]['lease_proposal']['status'],'obsolete')
        self.provider.result={'intent':'other'}
        response=self.send(read,'next','下一步')
        self.assertEqual(response.status_code,200,response.text)
        context=self.provider.inputs[-1]
        self.assertEqual(context['lease_draft']['status'],'draft')
        self.assertNotIn('private-lease@example.com',str(context['lease_draft']))

    def test_router_receives_safe_pending_field_names_for_unconfirmed_lease_followup(self):
        self.provider.result={'intent':'draft_contract'}
        conversation=self.send(self.c).json()
        self.provider.result={'intent':'other'}
        response=self.send(conversation,'followup','房东 Austin')
        self.assertEqual(response.status_code,200,response.text)
        safe=self.provider.inputs[-1]['lease_draft']
        self.assertIn('pending_proposal',safe)
        self.assertIn('landlord_name',safe['pending_proposal']['missing_fields'])
        self.assertEqual(set(safe['pending_proposal']),{'missing_fields'})
