"""Soft preferences reorder hard matches without creating housing facts."""
from copy import deepcopy
from datetime import date
import json
import unittest

from server.app.assistant.soft_preferences import (
    explicit_priorities, merge_explicit_priorities, rank_answer, rank_listings,
)
from server.app.areas.evidence import AreaKnowledge
from server.app.real_data.catalog import RealCatalog


TODAY = date(2026, 10, 30)


class Catalog:
    fingerprint = 'catalog-fixture'
    suburbs = ['Burwood', 'Rhodes', 'Carlton']


def listing(identifier, suburb, features=()):
    return {'listing_id': identifier, 'suburb': suburb, 'features': list(features),
            'weekly_rent': 700, 'bedrooms': 2, 'bathrooms': 1, 'car_spaces': 0,
            'source_url': 'https://www.domain.com.au/example-' + identifier,
            'captured_at': '2026-10-24T00:00:00+00:00',
            'usyd_commute': {'status': 'ok', 'duration_minutes': 25}}


class SoftPreferenceTests(unittest.TestCase):
    def rank(self, rows, topics, knowledge=None, today=TODAY):
        return rank_listings(rows, topics, Catalog(), knowledge=knowledge, today=today)

    def test_reorders_all_hard_matches_with_traceable_evidence_and_stable_ties(self):
        rows = [listing('c', 'Carlton'), listing('r', 'Rhodes'), listing('b', 'Burwood')]
        before = deepcopy(rows)
        ranked, report = self.rank(rows, ['shopping'])
        self.assertEqual([r['listing_id'] for r in ranked], ['r', 'b', 'c'])
        self.assertEqual(rows, before)
        self.assertEqual({r['listing_id'] for r in ranked}, {r['listing_id'] for r in rows})
        self.assertEqual(report['catalog_fingerprint'], Catalog.fingerprint)
        self.assertEqual(report['area_evidence_fingerprint'], AreaKnowledge().fingerprint)
        self.assertEqual(report['coverage']['matching_listings'], 3)
        self.assertEqual(report['coverage']['matching_suburbs_with_records'], 2)
        self.assertEqual(report['coverage']['matching_listings_with_supported_preferences'], 2)
        self.assertEqual(self.rank(rows, ['shopping'])[1], report)
        json.dumps(report)
        b = report['items'][0]
        self.assertEqual(b['matched_topics'], ['shopping'])
        self.assertEqual(b['score'], 1)
        self.assertTrue(b['area_context']['evidence'])
        for evidence in b['area_context']['evidence']:
            self.assertTrue(evidence['source']['url'].startswith('https://'))
            self.assertEqual(evidence['freshness'], 'current_reference')
            self.assertIn('shopping', evidence['supports_topics'])
        self.assertIn('suburb', b['reasons'][0].lower())

    def test_missing_coverage_is_unknown_not_absence_or_borrowed_neighbor_facts(self):
        _, report = self.rank([listing('c', 'Carlton')], ['parks', 'library'])
        item = report['items'][0]
        self.assertEqual(item['unknown_topics'], ['parks', 'library'])
        self.assertEqual(item['score'], 0)
        self.assertEqual(item['area_context']['evidence'], [])
        self.assertIn('not evidence that facilities are absent', ' '.join(item['notes']))

    def test_quiet_safety_and_unrecognized_topics_never_score_even_from_features(self):
        rows = [listing('r', 'Rhodes', ['Quiet', 'Secure Parking', 'Security Access'])]
        _, report = self.rank(rows, ['quiet', 'safety', 'best_suburb'])
        item = report['items'][0]
        self.assertEqual(item['score'], 0)
        self.assertEqual(item['unknown_topics'], ['quiet', 'safety'])
        self.assertEqual(report['unsupported_priorities'], ['best_suburb'])
        self.assertIn('not established', ' '.join(item['notes']))

    def test_stale_opinion_and_wider_or_neighbor_scope_do_not_score(self):
        knowledge = AreaKnowledge()
        sample = deepcopy(next(e for e in knowledge.records if e['kind'] == 'official'))
        sample.update(suburb='Carlton', topics=['parks'])
        for field, value in [('kind', 'resident_opinion'), ('kind', 'media'),
                             ('geographic_scope', 'lga'), ('geographic_scope', 'nearby_facility')]:
            with self.subTest(field=field, value=value):
                record = deepcopy(sample); record[field] = value
                knowledge.records = [record]
                self.assertEqual(self.rank([listing('c', 'Carlton')], ['parks'], knowledge)[1]['items'][0]['score'], 0)
        knowledge.records = [sample]
        self.assertEqual(self.rank([listing('c', 'Carlton')], ['parks'], knowledge, date(2030, 1, 1))[1]['items'][0]['score'], 0)

    def test_advertisement_claims_are_separate_allowlisted_and_never_walking_or_grocery_proof(self):
        rows = [listing('c', 'Carlton', ['Close to shops', 'Close to Parklands',
                'Not close to shops', 'No parks nearby', 'Unfurnished', 'Carlton shops #### For rent'])]
        _, report = self.rank(rows, ['shopping', 'parks'])
        item = report['items'][0]
        self.assertEqual(item['score'], 2)
        self.assertEqual([e['feature'] for e in item['advertisement_evidence']], ['Close to shops', 'Close to Parklands'])
        self.assertFalse(item['area_context']['evidence'])
        self.assertTrue(all(e['source']['url'] == rows[0]['source_url'] for e in item['advertisement_evidence']))
        self.assertTrue(all(e['status'] == 'advertised_unconfirmed' for e in item['advertisement_evidence']))
        self.assertIn('walking distance', ' '.join(report['limitations']))
        denied = listing('d', 'Carlton', ['Not close to shops', 'No parks nearby', 'Unverified feature'])
        self.assertEqual(self.rank([denied], ['shopping', 'parks'])[1]['items'][0]['score'], 0)

    def test_each_topic_scores_only_once_and_missing_ad_source_cannot_score(self):
        row = listing('b', 'Burwood', ['Close to shops', 'Close to Shops'])
        _, report = self.rank([row], ['shopping', 'shopping'])
        self.assertEqual(report['items'][0]['score'], 1)
        row = listing('c', 'Carlton', ['Close to shops']); row.pop('source_url')
        self.assertEqual(self.rank([row], ['shopping'])[1]['items'][0]['score'], 0)

    def test_explicit_english_and_chinese_topics_preserve_hard_brief_and_ignore_negation(self):
        self.assertEqual(explicit_priorities('Prefer parks, groceries and a library. Quiet and safe please.'),
                         ['parks', 'shopping', 'library', 'quiet', 'safety'])
        self.assertEqual(explicit_priorities('希望附近有公园、餐饮、超市和图书馆，安静安全'),
                         ['parks', 'food', 'shopping', 'library', 'quiet', 'safety'])
        self.assertEqual(explicit_priorities("I don't care about parks or shopping; no preference for a library."), [])
        self.assertEqual(explicit_priorities('不需要公园和超市，不在意安静'), [])
        brief = {'budget_amount': 800, 'commute_max_minutes': 30, 'min_bedrooms': 2, 'lifestyle_priorities': ['food']}
        before = deepcopy(brief)
        merged = merge_explicit_priorities(brief, 'Prefer a library and parks')
        self.assertEqual(merged['lifestyle_priorities'], ['food', 'parks', 'library'])
        self.assertEqual({k:v for k,v in merged.items() if k != 'lifestyle_priorities'},
                         {k:v for k,v in before.items() if k != 'lifestyle_priorities'})
        self.assertEqual(brief, before)
        self.assertEqual(explicit_priorities('Apartment at 2 Park Road, Library Lane'), [])

    def test_real_catalog_numeric_and_commute_hard_matches_remain_identical(self):
        catalog = RealCatalog()
        for filters in [{'max_weekly_rent': 800, 'min_bedrooms': 2, 'min_bathrooms': 1},
                        {'max_weekly_rent': 1000, 'usyd_max_minutes': 45, 'usyd_mode': 'public_transport'}]:
            rows = catalog.matching(filters)
            self.assertGreater(len(rows), 0, 'Hard-filter preservation must exercise actual listings')
            ranked, report = rank_listings(rows, ['shopping', 'parks'], catalog, today=TODAY)
            self.assertEqual({r['listing_id'] for r in rows}, {r['listing_id'] for r in ranked})
            self.assertEqual(len(rows), len(ranked))
            self.assertTrue(all(r['weekly_rent'] <= filters['max_weekly_rent'] for r in ranked))
            original = {r['listing_id']:r for r in rows}
            self.assertTrue(all(r == original[r['listing_id']] for r in ranked))
            self.assertEqual(len(report['items']), len(rows))

    def test_explicit_removal_replaces_old_topics_without_changing_hard_fields(self):
        brief = {'budget_amount': 800, 'commute_max_minutes': 30, 'min_bedrooms': 2,
                 'lifestyle_priorities': ['shopping', 'library']}
        before = deepcopy(brief)
        for message in ['Shopping no longer matters; prioritize parks', '买菜无所谓，优先公园',
                        'I no longer care about shopping; prioritize parks',
                        "Shopping doesn't matter; prioritize parks"]:
            with self.subTest(message=message):
                merged = merge_explicit_priorities(brief, message)
                self.assertEqual(merged['lifestyle_priorities'], ['library', 'parks'])
                self.assertEqual({k:v for k,v in merged.items() if k != 'lifestyle_priorities'},
                                 {k:v for k,v in brief.items() if k != 'lifestyle_priorities'})
        self.assertEqual(brief, before)
        self.assertEqual(merge_explicit_priorities(brief, "I don't care about shopping or libraries")['lifestyle_priorities'], [])
        self.assertEqual(merge_explicit_priorities(brief, '图书馆不重要，不需要超市')['lifestyle_priorities'], [])

    def test_clear_all_lifestyle_preferences_and_following_new_topic_are_explicit(self):
        brief = {'budget_amount': 800, 'lifestyle_priorities': ['shopping', 'quiet', 'parks']}
        for message in ['No lifestyle preferences', '生活偏好不限', 'Clear all lifestyle priorities']:
            with self.subTest(message=message):
                merged = merge_explicit_priorities(brief, message)
                self.assertEqual(merged, {'budget_amount': 800, 'lifestyle_priorities': []})
                self.assertNotIn('soft_preferences', rank_answer({'intent': 'search', 'listings': []}, merged, Catalog()))
        self.assertEqual(merge_explicit_priorities(brief, 'No lifestyle preferences, but prioritize a library')['lifestyle_priorities'], ['library'])
        self.assertEqual(merge_explicit_priorities(brief, '生活偏好不限；但优先图书馆')['lifestyle_priorities'], ['library'])
        self.assertEqual(merge_explicit_priorities(brief, 'Keep my budget under 800')['lifestyle_priorities'], brief['lifestyle_priorities'])

    def test_latest_explicit_topic_edit_wins_without_interpreting_negative_facts_as_preferences(self):
        brief = {'lifestyle_priorities': ['shopping', 'library']}
        self.assertEqual(merge_explicit_priorities(brief, 'Drop shopping; prefer shopping after all')['lifestyle_priorities'], ['library', 'shopping'])
        self.assertEqual(merge_explicit_priorities(brief, 'Prefer parks; parks are not a priority')['lifestyle_priorities'], ['shopping', 'library'])
        self.assertEqual(merge_explicit_priorities(brief, '不要修改生活偏好')['lifestyle_priorities'], ['shopping', 'library'])
        self.assertEqual(merge_explicit_priorities(brief, 'There are no shops near this house')['lifestyle_priorities'], ['shopping', 'library'])
        self.assertEqual(merge_explicit_priorities(brief, '附近没有超市')['lifestyle_priorities'], ['shopping', 'library'])

    def test_answer_hook_only_ranks_result_sets_not_comparisons_or_unrequested_topics(self):
        rows = [listing('c', 'Carlton'), listing('b', 'Burwood')]
        answer = {'intent': 'search', 'listings': rows, 'content': '2 hard matches', '_search_filters': {'max_weekly_rent': 800}}
        ranked = rank_answer(answer, {'lifestyle_priorities': ['shopping']}, Catalog(), today=TODAY)
        self.assertEqual([r['listing_id'] for r in ranked['listings']], ['b', 'c'])
        self.assertEqual(ranked['_search_filters'], answer['_search_filters'])
        self.assertEqual(answer['listings'], rows)
        self.assertNotIn('soft_preferences', rank_answer(answer, {}, Catalog(), today=TODAY))
        comparison = {**answer, 'intent': 'compare'}
        self.assertEqual(rank_answer(comparison, {'lifestyle_priorities': ['shopping']}, Catalog(), today=TODAY), comparison)


if __name__ == '__main__':
    unittest.main()
