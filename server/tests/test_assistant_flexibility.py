"""Question-specific replies across different areas, budgets and ambiguous names."""
import unittest
from server.tests import test_assistant_api as harness


class AssistantFlexibilityTests(unittest.TestCase):
    setUp=harness.AssistantTests.setUp
    conversation=harness.AssistantTests.conversation
    send=harness.AssistantTests.send

    def test_area_answer_changes_with_region_evidence_and_budget(self):
        c=self.conversation()
        self.provider.result={'intent':'area_advice','areas':['Chatswood','Eastwood'],'brief_patch':{
            'budget_amount':1100,'budget_period':'week','budget_scope':'whole_property','min_bedrooms':2,
            'lifestyle_priorities':['library']}}
        r=self.send(c,'libraries','比较Chatswood和Eastwood，预算1100两卧，喜欢图书馆');self.assertEqual(r.status_code,200,r.text)
        c=r.json();first=c['messages'][-1]['content']
        for term in ('Chatswood','Eastwood','Libraries','1100'):self.assertIn(term,first)
        self.provider.result={'intent':'area_advice','areas':['Parramatta','Strathfield'],'focus':'housing','brief_patch':{'budget_amount':700}}
        r=self.send(c,'cheaper','改为Parramatta和Strathfield，预算700，按房型和价格比较')
        self.assertEqual(r.status_code,200,r.text);second=r.json()['messages'][-1]['content']
        self.assertNotEqual(first,second);self.assertIn('700',second);self.assertIn('Parramatta',second)
        self.assertNotIn('Chatswood',second)

    def test_quietness_question_gets_uncertainty_answer_not_general_intro(self):
        self.provider.result={'intent':'area_advice','areas':['Redfern','Marrickville'],'brief_patch':{'lifestyle_priorities':['quiet']}}
        r=self.send(self.conversation(),'quiet','Redfern和Marrickville哪个更安静？')
        self.assertEqual(r.status_code,200,r.text);text=r.json()['messages'][-1]['content']
        self.assertIn('cannot determine',text);self.assertIn('Quietness',text)
        self.assertIn('Redfern',text);self.assertNotIn('Rhodes',text)

    def test_incomplete_suburb_is_clarified_without_losing_budget_and_rooms(self):
        self.provider.result={'intent':'collect_preferences','brief_patch':{
            'suburb':'Rosebery','budget_amount':900,'budget_period':'week','budget_scope':'whole_property','min_bedrooms':2}}
        r=self.send(self.conversation(),'rose','我想看Rose区的房子，整套每周900，两卧。')
        self.assertEqual(r.status_code,200,r.text);c=r.json()
        self.assertNotIn('suburb',c['rental_brief']);self.assertEqual(c['rental_brief']['budget_amount'],900)
        self.assertEqual(c['rental_brief']['min_bedrooms'],2)
        self.assertIn('full English name',c['messages'][-1]['content']);self.assertIn('Rose',c['messages'][-1]['content'])

    def test_known_pending_school_reply_is_accepted_despite_malformed_router_fields(self):
        self.provider.result={'intent':'recommend_areas','brief_patch':{
            'budget_amount':750,'budget_period':'week','budget_scope':'whole_property','min_bedrooms':1,'suburb':'Camperdown'}}
        c=self.send(self.conversation(),'intake','Camperdown，整套每周750，一卧，按通勤推荐').json()
        self.provider.result={'intent':'recommend_areas','areas':['Kensington'],'brief_patch':{'destination_query':'UNSW Kensington'}}
        r=self.send(c,'unsw','UNSW Kensington')
        self.assertEqual(r.status_code,200,r.text);c=r.json()
        self.assertEqual(c['rental_brief']['suburb'],'Camperdown')
        self.assertEqual(c['messages'][-1]['intent'],'outside_scope')
        self.assertIn('University of Sydney',c['messages'][-1]['content'])

    def test_natural_area_choice_recovers_a_misrouted_area_introduction(self):
        self.provider.result={'intent':'area_advice','areas':['Burwood','Ashfield'],'brief_patch':{
            'budget_amount':850,'budget_period':'week','budget_scope':'whole_property','min_bedrooms':1}}
        c=self.send(self.conversation(),'intro','Burwood和Ashfield对比，850整套一卧').json()
        self.provider.result={'intent':'area_advice','areas':['Ashfield']}
        self.provider.by_task['assistant_area_followup']={'continue_housing':True,'brief_patch':{'suburb':'Ashfield'}}
        r=self.send(c,'choose','那先看Ashfield吧，帮我找房，也看看上学方不方便。')
        self.assertEqual(r.status_code,200,r.text);c=r.json();answer=c['messages'][-1]
        self.assertEqual(answer['intent'],'recommend_areas');self.assertNotIn('area_advice',answer)
        self.assertEqual(c['rental_brief']['suburb'],'Ashfield');self.assertEqual(c['rental_brief']['budget_amount'],850)
        self.assertIn('USYD main campus',answer['content'])

    def test_area_followup_recovery_does_not_steal_another_comparison(self):
        self.provider.result={'intent':'area_advice','areas':['Burwood','Ashfield']}
        c=self.send(self.conversation(),'intro','Burwood和Ashfield对比').json()
        self.provider.result={'intent':'area_advice','areas':['Chatswood','Eastwood'],'brief_patch':{'lifestyle_priorities':['library']}}
        self.provider.by_task['assistant_area_followup']={'continue_housing':False,'brief_patch':{}}
        c=self.send(c,'new','换成Chatswood和Eastwood，比较图书馆').json()
        self.assertEqual(c['messages'][-1]['intent'],'area_advice')
        self.assertEqual([a['suburb'] for a in c['messages'][-1]['area_advice']['areas']],['Chatswood','Eastwood'])

    def test_search_cannot_expand_an_incomplete_region_name(self):
        self.provider.result={'intent':'search','filters':{'suburb':'Rosebery','max_weekly_rent':900,'min_bedrooms':2}}
        r=self.send(self.conversation(),'rose-search','我想看Rose区的房子，整套每周900，两卧。')
        self.assertEqual(r.status_code,200,r.text);c=r.json();answer=c['messages'][-1]
        self.assertEqual(answer['intent'],'collect_preferences');self.assertEqual(answer['listings'],[])
        self.assertNotIn('suburb',c['rental_brief']);self.assertEqual(c['rental_brief']['budget_amount'],900)
        self.assertEqual(c['rental_brief']['min_bedrooms'],2);self.assertIn('full English name',answer['content'])

    def test_evidence_tie_names_supported_areas_without_including_missing_area(self):
        self.provider.result={'intent':'area_advice','areas':['Burwood','Marrickville','Carlton'],
                              'brief_patch':{'lifestyle_priorities':['food','library']}}
        c=self.send(self.conversation(),'tie','比较Burwood、Marrickville和Carlton，喜欢餐饮图书馆').json()
        answer=c['messages'][-1]['content']
        self.assertNotIn('these areas all have relevant facilities evidence',answer)
        self.assertIn('Burwood, Marrickville',answer)

    def test_invalid_intent_gets_one_schema_repair_attempt(self):
        self.provider.result={'intent':'area_advice','areas':['Carlton','Rosebery'],'focus':'price'}
        def correct_on_retry():
            if len(self.provider.inputs)==2:
                self.provider.result={'intent':'area_advice','areas':['Carlton','Rosebery'],'focus':'housing',
                    'brief_patch':{'budget_amount':800,'budget_period':'week','budget_scope':'whole_property','min_bedrooms':2}}
        self.provider.on_call=correct_on_retry
        r=self.send(self.conversation(),'schema','先不判断安全，按便宜和卧室数量比较Carlton和Rosebery，800两卧')
        self.assertEqual(r.status_code,200,r.text)
        self.assertIn('800',r.json()['messages'][-1]['content'])
        self.assertEqual(len(self.provider.inputs),2)
        self.assertIn('validation_feedback',self.provider.inputs[-1])

    def test_natural_choice_keeps_new_requirements_from_primary_extraction(self):
        self.provider.result={'intent':'area_advice','areas':['Burwood','Ashfield'],'brief_patch':{
            'budget_amount':850,'budget_period':'week','budget_scope':'whole_property','min_bedrooms':1}}
        c=self.send(self.conversation(),'intro','比较Burwood和Ashfield，整套850一卧').json()
        self.provider.result={'intent':'area_advice','areas':['Ashfield'],'brief_patch':{'budget_amount':900,'min_bedrooms':2}}
        self.provider.by_task['assistant_area_followup']={'continue_housing':True,'brief_patch':{'suburb':'Ashfield'}}
        r=self.send(c,'choose','先看Ashfield吧，预算改900，两卧，继续按通勤找房')
        self.assertEqual(r.status_code,200,r.text);brief=r.json()['rental_brief']
        self.assertEqual(brief['budget_amount'],900);self.assertEqual(brief['min_bedrooms'],2)
        self.assertEqual(brief['suburb'],'Ashfield')
