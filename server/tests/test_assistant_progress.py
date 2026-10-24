"""Region discussion must advance when a user chooses a region or answers intake."""
import unittest
from unittest.mock import patch
from server.app.ai.provider import ProviderError
from server.tests import test_assistant_api as harness


class AssistantProgressTests(unittest.TestCase):
    setUp=harness.AssistantTests.setUp
    conversation=harness.AssistantTests.conversation
    send=harness.AssistantTests.send

    def compare(self):
        self.provider.result={'intent':'area_advice','areas':['Burwood','Rhodes'],'brief_patch':{
            'budget_amount':900,'budget_period':'week','budget_scope':'whole_property',
            'min_bedrooms':2,'min_bathrooms':1,'min_car_spaces':0,'lifestyle_priorities':['parks','food']}}
        r=self.send(self.conversation(),'compare','整套每周预算900，两卧。比较Burwood和Rhodes，喜欢公园和餐饮。')
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def choose(self,c):
        # Reproduce the observed model misroute instead of teaching the fixture the desired answer.
        self.provider.result={'intent':'area_advice','areas':['Burwood','Rhodes'],'brief_patch':{'budget_amount':9999,'suburb':'Burwood'}}
        r=self.send(c,'choose','保持我的预算和房型要求，按 Rhodes 区域继续推荐房源，并核对到学校或公司的通勤。')
        self.assertEqual(r.status_code,200,r.text)
        c=r.json()
        self.assertEqual(c['messages'][-1]['intent'],'recommend_areas')
        self.assertNotIn('area_advice',c['messages'][-1])
        self.assertEqual(c['rental_brief']['suburb'],'Rhodes')
        self.assertEqual(c['rental_brief']['budget_amount'],900)
        self.assertEqual(c['rental_brief']['min_bedrooms'],2)
        self.assertIn('学校',c['messages'][-1]['content'])
        return c

    def test_exact_rendered_region_action_advances_even_when_router_misclassifies(self):
        self.choose(self.compare())

    def test_school_abbreviation_answers_pending_destination_without_repeat_cards(self):
        c=self.choose(self.compare())
        self.provider.result={'intent':'area_advice','areas':['Burwood','Rhodes']}
        r=self.send(c,'school','usyd');self.assertEqual(r.status_code,200,r.text)
        c=r.json();answer=c['messages'][-1]
        self.assertEqual(answer['intent'],'recommend_areas')
        self.assertEqual(c['rental_brief']['destination_query'],'usyd')
        self.assertNotIn('area_advice',answer)
        self.assertIn('几点',answer['content']);self.assertIn('多少分钟',answer['content'])
        self.assertEqual(answer['commute_question']['fields'],['arrival_time','commute_max_minutes'])
        self.assertIn('pending_question',self.provider.inputs[-1])
        from server.app.assistant.commute import normalized_query
        self.assertEqual(normalized_query('USYD'),'University of Sydney')

    def test_free_text_pending_answer_uses_bounded_slot_repair_if_misrouted(self):
        c=self.choose(self.compare())
        self.provider.result={'intent':'area_advice','areas':['Burwood','Rhodes']}
        self.provider.by_task['assistant_commute_reply']={'is_reply':True,'brief_patch':{'destination_query':'Westmead Hospital'}}
        r=self.send(c,'hospital','Westmead Hospital')
        self.assertEqual(r.status_code,200,r.text);c=r.json()
        self.assertEqual(c['rental_brief']['destination_query'],'Westmead Hospital')
        self.assertNotIn('area_advice',c['messages'][-1])
        self.assertEqual([i['task'] for i in self.provider.inputs[-2:]],['assistant_intent','assistant_commute_reply'])
        self.assertNotIn('draft_profile',self.provider.inputs[-1])

    def test_explicit_area_question_or_other_agent_does_not_get_forced_to_commute(self):
        c=self.choose(self.compare())
        self.provider.result={'intent':'area_advice','areas':['Burwood','Rhodes']}
        self.provider.by_task['assistant_commute_reply']={'is_reply':False,'brief_patch':{}}
        r=self.send(c,'back-to-areas','先不看通勤，再比较Burwood和Rhodes的公园')
        self.assertEqual(r.status_code,200,r.text)
        self.assertIn('area_advice',r.json()['messages'][-1])
        self.provider.result={'intent':'draft_contract'}
        self.provider.by_task['lease_draft_extract']={'fields':[]}
        r=self.send(r.json(),'contract','先帮我准备租约草稿')
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['messages'][-1]['intent'],'draft_contract')

    def test_alias_in_new_chat_is_not_implicitly_a_commute_request(self):
        self.provider.result={'intent':'area_advice','areas':['Rhodes']}
        r=self.send(self.conversation(),'not-pending','usyd')
        self.assertEqual(r.status_code,200,r.text)
        self.assertNotIn('destination_query',r.json().get('rental_brief',{}))

    def test_fully_collected_intake_is_not_still_asking_for_a_destination(self):
        from server.app.assistant.progress import pending_question
        c={'dialogue_mode':'recommend_areas','rental_brief':{'budget_amount':900,'budget_period':'week',
           'budget_scope':'whole_property','min_bedrooms':2,'destination_query':'usyd','arrival_time':'09:00',
           'commute_max_minutes':40,'commute_mode':'public_transport'},'commute_destination_options':[]}
        self.assertIsNone(pending_question(c))

    def test_existing_looped_conversation_can_resume_without_new_question_metadata(self):
        c=self.choose(self.compare());repo=self.client.app.state.repository
        with repo.transaction() as db:
            saved=repo.get(db,'assistant_conversation',c['conversation_id'])
            saved['messages'][-1]=saved['messages'][1].copy()
            repo.put(db,'assistant_conversation',c['conversation_id'],saved)
        self.provider.result={'intent':'area_advice','areas':['Burwood','Rhodes']}
        r=self.send(c,'legacy-resume','usyd')
        self.assertEqual(r.status_code,200,r.text)
        answer=r.json()['messages'][-1]
        self.assertNotIn('area_advice',answer);self.assertIn('几点',answer['content'])

    def test_failed_optional_repair_never_overrides_explicit_area_question(self):
        c=self.choose(self.compare())
        self.provider.result={'intent':'area_advice','areas':['Burwood','Rhodes']}
        self.provider.by_task['assistant_commute_reply']={'malformed':True}
        r=self.send(c,'bad-repair','先不看通勤，再比较Burwood和Rhodes的公园')
        self.assertEqual(r.status_code,200,r.text);self.assertIn('area_advice',r.json()['messages'][-1])
        original=self.provider.call
        def fail_repair(context):
            if context['task']=='assistant_commute_reply':
                raise ProviderError('ai_timeout',{'task':'assistant_commute_reply','status':'failed','attempted':True})
            return original(context)
        with patch.object(self.provider,'call',side_effect=fail_repair):
            r=self.send(r.json(),'failed-repair','先不看通勤，再比较Burwood和Rhodes的公园')
        self.assertEqual(r.status_code,200,r.text);self.assertIn('area_advice',r.json()['messages'][-1])
