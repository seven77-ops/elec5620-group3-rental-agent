"""English output policy with external providers stubbed throughout."""
import unittest
from types import SimpleNamespace

from server.app.ai.provider import TASKS
from server.app.assistant.repair_drafts import email_options
from server.app.assistant.progress import explicit_transition, region_continuation
from server.app.assistant.commute_edits import explicit_edit
from server.app.assistant.preferences_progress import explicit
from server.app.living.repairs import styled_email
from server.app.rag.service import KnowledgeService
from server.tests.test_repair_email_ai import RepairEmailAITests


class EnglishOutputPolicyTests(unittest.TestCase):
    def test_repair_language_stays_english_for_chinese_request_and_legacy_values(self):
        self.assertEqual(email_options('请改成中文，礼貌一点', {'email_language': 'zh'}, {'email_language': 'zh'}), ('en', 'polite'))

    def test_no_evidence_answer_normalizes_legacy_language(self):
        service = object.__new__(KnowledgeService)
        answer = service.compose('押金怎么退？', {}, [], False, 'zh')
        self.assertEqual(answer['language'], 'en')
        self.assertEqual(answer['answer_language'], 'en')
        self.assertIn('source', answer['answer'])

    def test_generative_model_tasks_enforce_english(self):
        for task in ('rag_answer', 'rag_grounded_summary', 'rag_summary_check', 'repair_email_polish'):
            with self.subTest(task=task):
                self.assertIn('Always write', TASKS[task])
                self.assertIn('English', TASKS[task])
                self.assertNotIn('Chinese only if', TASKS[task])
                self.assertNotIn('zh means Chinese', TASKS[task])


class EnglishActionRoutingTests(unittest.TestCase):
    def test_legacy_chinese_refresh_action_retains_exact_boundary(self):
        text = '保持全部已确认的预算、房型和通勤条件，换一批推荐，优先展示之前没看过的房源。'
        self.assertEqual(explicit_transition({'messages':[], 'dialogue_mode':'recommend_areas'}, text), {'intent':'recommend_areas','refresh_recommendations':True})
        self.assertIsNone(explicit_transition({'messages':[], 'dialogue_mode':'recommend_areas'}, '不要'+text))

    def test_legacy_repair_boilerplate_updates_to_english_without_changing_facts(self):
        facts = '地址：123 Example St\n情况描述：厨房漏水\n原始记录保持不变'
        legacy = '您好，Alex：\n\n请协助安排以下维修：\n'+facts+'\n\n请告知后续处理安排，谢谢。'
        result = styled_email(legacy, 'polite')
        self.assertIn(facts, result)
        self.assertIn('Could you please review the issue below and help arrange a repair?', result)
        self.assertTrue(result.endswith('Please let me know the arrangements or any additional details you need. Thank you for your help.'))
        self.assertNotIn('请协助安排以下维修：', result)

    def test_english_area_action_keeps_offered_suburb_boundary(self):
        conversation = {'messages':[{'area_advice':{'areas':[{'suburb':'Rhodes'}]}}]}
        self.assertEqual(region_continuation(conversation, 'Keep my budget and housing needs, recommend listings in Rhodes and check the commute to the University of Sydney main campus.'), 'Rhodes')
        self.assertIsNone(region_continuation(conversation, 'Keep my budget and housing needs, recommend listings in Burwood and check the commute to the University of Sydney main campus.'))

    def test_english_refresh_action_routes_without_losing_filters(self):
        result = explicit_transition({'messages':[], 'dialogue_mode':'recommend_areas'}, 'Keep all confirmed budget, housing and commute criteria. Show another set of recommendations, prioritising listings I have not seen before.')
        self.assertEqual(result, {'intent':'recommend_areas','refresh_recommendations':True})

    def test_english_short_commute_edit_retains_existing_scope(self):
        conversation = {'dialogue_mode':'recommend_areas','rental_brief':{'commute_mode':'train','commute_max_minutes':40}}
        self.assertEqual(explicit_edit(conversation, 'bus 45 minutes'), {'intent':'recommend_areas','brief_patch':{'commute_mode':'bus','commute_max_minutes':45}})
        self.assertIsNone(explicit_edit(conversation, 'do not change to bus 45 minutes'))

    def test_english_occupants_and_unrestricted_answers(self):
        conversation = {'dialogue_mode':'collect_preferences','rental_brief':{}}
        self.assertEqual(explicit(conversation, '2 people', {'task':'rental_preferences','fields':['occupants']}), {'intent':'collect_preferences','brief_patch':{'occupants':2}})
        self.assertEqual(explicit(conversation, 'unrestricted', {'task':'rental_preferences','fields':['min_car_spaces']}), {'intent':'collect_preferences','brief_patch':{'min_car_spaces':0}})


class LegacyEmailLanguageTests(RepairEmailAITests):
    def test_legacy_language_normalized_before_provider(self):
        self.ai.polish(self.cid, {**self.body, 'language': 'zh'})
        self.assertEqual(self.provider.calls[0]['language'], 'en')
