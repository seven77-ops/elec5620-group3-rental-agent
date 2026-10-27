"""Short answers must complete the pending rental question, even if routing misses them."""
import unittest
from server.tests import test_assistant_api as harness

class PreferenceProgressTests(unittest.TestCase):
    setUp=harness.AssistantTests.setUp
    conversation=harness.AssistantTests.conversation
    send=harness.AssistantTests.send

    def start(self):
        self.provider.result={'intent':'collect_preferences','brief_patch':{'suburb':'Burwood','budget_amount':1200,'budget_period':'week','budget_scope':'unknown'}}
        r=self.send(self.conversation(),'start','我想住Burwood预算1200每周')
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def test_whole_property_reply_advances_instead_of_repeating_scope(self):
        c=self.start()
        self.provider.result={'intent':'collect_preferences','brief_patch':{}}
        r=self.send(c,'scope','整套');self.assertEqual(r.status_code,200,r.text);c=r.json()
        self.assertEqual(c['rental_brief']['budget_scope'],'whole_property')
        self.assertEqual(c['rental_brief']['budget_amount'],1200)
        self.assertEqual(c['rental_brief']['suburb'],'Burwood')
        self.assertIn('卧室',c['messages'][-1]['content'])
        self.assertNotIn('是整套、每个房间',c['messages'][-1]['content'])
        self.assertEqual(self.provider.inputs[-1]['pending_question']['fields'],['budget_scope'])

    def test_scope_reply_is_not_inferred_in_a_new_conversation(self):
        self.provider.result={'intent':'collect_preferences','brief_patch':{}}
        c=self.send(self.conversation(),'not-pending','整套').json()
        self.assertNotIn('budget_scope',c['rental_brief'])

    def test_commute_intake_also_accepts_the_same_short_budget_scope(self):
        self.provider.result={'intent':'recommend_areas','brief_patch':{'budget_amount':1200,'budget_period':'week','suburb':'Burwood'}}
        c=self.send(self.conversation(),'commute','按通勤找房，Burwood每周1200').json()
        self.provider.result={'intent':'recommend_areas','brief_patch':{}}
        r=self.send(c,'scope','整套')
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['rental_brief']['budget_scope'],'whole_property')
        self.assertIn('卧室',r.json()['messages'][-1]['content'])

    def test_free_text_pending_reply_has_a_bounded_recovery(self):
        c=self.start();self.provider.result={'intent':'collect_preferences','brief_patch':{}}
        self.provider.by_task['assistant_preferences_reply']={'is_reply':True,'brief_patch':{'budget_scope':'per_person'}}
        r=self.send(c,'scope','这是我自己一个人每周能承担的金额')
        self.assertEqual(r.status_code,200,r.text);c=r.json()
        self.assertEqual(c['rental_brief']['budget_scope'],'per_person')
        self.assertNotIn('draft_profile',self.provider.inputs[-1])
        self.assertEqual(self.provider.inputs[-1]['task'],'assistant_preferences_reply')

    def test_new_topic_is_not_overridden_by_intake_recovery(self):
        c=self.start();self.provider.result={'intent':'draft_contract'}
        self.provider.by_task['lease_draft_extract']={'fields':[]}
        c=self.send(c,'contract','先帮我准备合同').json()
        self.assertEqual(c['messages'][-1]['intent'],'draft_contract')

    def test_invalid_recovery_keeps_original_question_without_inventing_answers(self):
        c=self.start();self.provider.result={'intent':'collect_preferences','brief_patch':{}}
        self.provider.by_task['assistant_preferences_reply']={'is_reply':True,'brief_patch':{'budget_scope':'made-up'}}
        r=self.send(c,'bad','我暂时不清楚')
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['rental_brief']['budget_scope'],'unknown')

    def test_cycle_only_reply_never_converts_existing_month_budget(self):
        for copy_amount in (False,True):
            with self.subTest(copy_amount=copy_amount):
                self.provider.result={'intent':'collect_preferences','brief_patch':{'suburb':'Burwood','budget_amount':4800,'budget_period':'month','budget_scope':'whole_property'}}
                c=self.send(self.conversation(),'monthly-'+str(copy_amount),'整套月预算4800，想住Burwood').json()
                self.provider.result={'intent':'collect_preferences','brief_patch':{'budget_period':'week',**({'budget_amount':4800} if copy_amount else {})}}
                r=self.send(c,'cycle-'+str(copy_amount),'每周')
                self.assertEqual(r.status_code,200,r.text)
                self.assertEqual(r.json()['rental_brief']['budget_period'],'month')
                self.assertEqual(r.json()['rental_brief']['budget_amount'],4800)
                self.assertIn('每周最高',r.json()['messages'][-1]['content'])

    def test_unknown_cycle_can_be_filled_and_explicit_new_week_amount_is_allowed(self):
        self.provider.result={'intent':'collect_preferences','brief_patch':{'suburb':'Burwood','budget_amount':1200,'budget_scope':'whole_property'}}
        c=self.send(self.conversation(),'unknown','Burwood整套预算1200').json()
        self.provider.result={'intent':'collect_preferences','brief_patch':{}}
        c=self.send(c,'week','每周').json()
        self.assertEqual(c['rental_brief']['budget_period'],'week')
        self.provider.result={'intent':'collect_preferences','brief_patch':{'budget_amount':4800,'budget_period':'month'}}
        c=self.send(c,'monthly','改成月预算4800').json()
        self.provider.result={'intent':'collect_preferences','brief_patch':{'budget_amount':1200,'budget_period':'week'}}
        c=self.send(c,'explicit-week','按每周1200算').json()
        self.assertEqual(c['rental_brief']['budget_period'],'week')
        self.assertEqual(c['rental_brief']['budget_amount'],1200)

    def test_month_to_week_guard_covers_search_and_checks_actual_chinese_amount(self):
        cases=[
            ('那就按周来吧',{'intent':'search','filters':{'max_weekly_rent':4800}},'month',4800),
            ('每周一千二百元',{'intent':'collect_preferences','brief_patch':{'budget_period':'week','budget_amount':4800}},'month',4800),
            ('每周一千二百元',{'intent':'collect_preferences','brief_patch':{'budget_period':'week','budget_amount':1200}},'week',1200),
            ('按每周1,200澳元',{'intent':'search','filters':{'max_weekly_rent':1200}},'week',1200),
        ]
        for i,(text,intent,period,amount) in enumerate(cases):
            with self.subTest(text=text,intent=intent):
                self.provider.result={'intent':'collect_preferences','brief_patch':{'suburb':'Burwood','budget_amount':4800,'budget_period':'month','budget_scope':'whole_property'}}
                c=self.send(self.conversation(),f'month-edge-{i}','Burwood整套月预算4800').json()
                self.provider.result=intent
                r=self.send(c,f'week-edge-{i}',text)
                self.assertEqual(r.status_code,200,r.text)
                self.assertEqual(r.json()['rental_brief']['budget_period'],period)
                self.assertEqual(r.json()['rental_brief']['budget_amount'],amount)
