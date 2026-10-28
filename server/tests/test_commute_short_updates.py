"""Explicit short commute edits must override a router that repeats old slots."""
from copy import deepcopy
import unittest

from server.tests import test_assistant_api as harness


class CommuteShortUpdateTests(unittest.TestCase):
    setUp = harness.AssistantTests.setUp
    conversation = harness.AssistantTests.conversation
    send = harness.AssistantTests.send

    def seeded(self):
        c = self.conversation()
        self.before = {'budget_amount': 900, 'budget_period': 'week',
                       'budget_scope': 'whole_property', 'suburb': None,
                       'min_bedrooms': 2, 'min_bathrooms': 1, 'min_car_spaces': 0,
                       'occupants': 2, 'rental_mode': 'whole_property',
                       'commute_mode': 'walk', 'commute_max_minutes': 10}
        c.update(rental_brief=deepcopy(self.before), dialogue_mode='recommend_areas')
        with self.client.app.state.repository.transaction() as db:
            self.client.app.state.repository.put(db, 'assistant_conversation', c['conversation_id'], c)
        # Deliberately reproduce bad extraction, not a fixture trained to pass.
        self.provider.result = {'intent': 'recommend_areas', 'brief_patch': {
            'commute_mode': 'walk', 'commute_max_minutes': 10, 'budget_amount': 9999}}
        return c

    def test_public_transport_twenty_minutes_updates_both_slots_and_actual_results(self):
        c = self.seeded()
        response = self.send(c, 'short-edit', '公共交通20分钟', allow_external_data=True)
        self.assertEqual(response.status_code, 200, response.text)
        updated = response.json()
        brief = updated['rental_brief']
        self.assertEqual(brief['commute_mode'], 'public_transport')
        self.assertEqual(brief['commute_max_minutes'], 20)
        for key, value in self.before.items():
            if key not in ('commute_mode', 'commute_max_minutes'):
                self.assertEqual(brief[key], value, key)
        answer = updated['messages'][-1]
        self.assertIn('公共交通', answer['content'])
        self.assertIn('20分钟', answer['content'])
        from server.app.real_data.catalog import RealCatalog
        matching = RealCatalog().matching({'max_weekly_rent': 900,
            'min_bedrooms': 2, 'min_bathrooms': 1, 'min_car_spaces': 0,
            'usyd_mode': 'public_transport', 'usyd_max_minutes': 20})
        self.assertTrue(matching)
        self.assertEqual({r['listing_id'] for r in answer['listings']},
                         {r['listing_id'] for r in matching})
        context = self.client.get(self.base + '/conversations/' + c['conversation_id'] + '/recommendation-context').json()
        self.assertEqual(context['criteria']['commute_mode'], 'public_transport')
        self.assertEqual(context['total'], len(matching))
        self.assertEqual(self.client.get('/api/v1/cases/' + self.case['case_id']).json(), self.case)
        self.assertEqual(self.send(c, 'short-edit', '公共交通20分钟', allow_external_data=True).json(), updated)

    def test_mode_only_then_duration_only_keep_the_other_slot_after_reload(self):
        c = self.seeded()
        self.provider.result = {'intent': 'other'}
        c = self.send(c, 'mode', '改成公共交通', allow_external_data=True).json()
        self.assertEqual(c['rental_brief']['commute_mode'], 'public_transport')
        self.assertEqual(c['rental_brief']['commute_max_minutes'], 10)
        c = self.client.get(self.base + '/conversations/' + c['conversation_id']).json()
        c = self.send(c, 'duration', '最多二十分钟', allow_external_data=True).json()
        self.assertEqual(c['rental_brief']['commute_mode'], 'public_transport')
        self.assertEqual(c['rental_brief']['commute_max_minutes'], 20)

    def test_guard_accepts_unambiguous_short_edits_only_in_active_housing_context(self):
        from server.app.assistant.progress import explicit_transition
        c = self.seeded()
        samples = {
            '公共交通20分钟': {'commute_mode': 'public_transport', 'commute_max_minutes': 20},
            '公共交通二十分钟以内': {'commute_mode': 'public_transport', 'commute_max_minutes': 20},
            '改成步行10分钟': {'commute_mode': 'walk', 'commute_max_minutes': 10},
            '火车30分钟': {'commute_mode': 'train', 'commute_max_minutes': 30},
            '公交车二十五分钟': {'commute_mode': 'bus', 'commute_max_minutes': 25},
            '我想步行十分钟到达的房子·': {'commute_mode': 'walk', 'commute_max_minutes': 10},
        }
        for text, expected in samples.items():
            with self.subTest(text=text):
                result = explicit_transition(c, text)
                self.assertEqual(result, {'intent': 'recommend_areas', 'brief_patch': expected})
        for text in ('不要公共交通20分钟', '步行10分钟或者公共交通20分钟',
                     '先别改成公共交通20分钟', '公共交通20分钟是什么意思？',
                     '中介说公共交通20分钟', '公共交通20分钟到公司',
                     '帮我写公共交通20分钟的报修邮件', '公共交通0分钟', '公共交通241分钟'):
            with self.subTest(text=text):
                self.assertIsNone(explicit_transition(c, text))
        self.assertIsNone(explicit_transition({'messages': []}, '公共交通20分钟'))


if __name__ == '__main__':
    unittest.main()
