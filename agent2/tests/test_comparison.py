import copy
import unittest

from rental_agent.contracts import validate_contract
from rental_agent.engine import evaluate
from rental_agent.report import compare_reports, render_markdown
from rental_agent.validation import ValidationError
from test_engine import dataset, listing, profile


class ComparisonExplanationTests(unittest.TestCase):
    def compare(self, p, q, data):
        before, after = evaluate(p, data), evaluate(q, data)
        comparison = compare_reports(before, after)
        after['comparison'] = comparison
        return comparison, after

    def test_weight_change_has_recomputable_dimension_contributions(self):
        p, q = profile(), profile()
        q['profile_version'] = 2
        q['weights'] = {'commute': 0.15, 'cost': 0.6, 'housing': 0.15, 'amenities': 0.1}
        comparison, report = self.compare(p, q, dataset(listing()))
        row = comparison['rows'][0]
        self.assertIn('score_contributions', row, '每条比较须包含四维贡献')
        cost = row['score_contributions']['cost']
        self.assertEqual(cost, {'before': 21.6, 'after': 43.2, 'change': 21.6})
        self.assertAlmostEqual(sum(v['change'] for v in row['score_contributions'].values()), row['score_change'], places=3)
        self.assertIn('Cost', '；'.join(row['change_reasons']))
        self.assertIn('30.0%', '；'.join(row['change_reasons']))
        validate_contract('RecommendationReport', report)

    def test_budget_change_explains_exclusion_without_inventing_score(self):
        p, q = profile(), profile()
        q['budget']['maximum'] = 500
        comparison, _ = self.compare(p, q, dataset(listing()))
        row = comparison['rows'][0]
        self.assertIn('change_reasons', row, '资格变化须有具体原因')
        reason = '；'.join(row['change_reasons'])
        self.assertIn('Eligible → Excluded', reason)
        self.assertIn('budget', reason)
        self.assertIn('550', reason)
        self.assertIn('500', reason)
        self.assertIsNone(row['after_score'])
        self.assertIsNone(row['score_change'])

    def test_relaxed_budget_explains_restored_eligibility(self):
        p, q = profile(), profile()
        p['budget']['maximum'] = 500
        comparison, _ = self.compare(p, q, dataset(listing()))
        row = comparison['rows'][0]
        self.assertIn('change_reasons', row)
        self.assertIn('Excluded → Eligible', '；'.join(row['change_reasons']))
        self.assertIn('budget', '；'.join(row['change_reasons']))

    def test_new_destination_explains_pending_route(self):
        p, q = profile(), profile()
        q['destination_id'] = 'new-campus'
        comparison, _ = self.compare(p, q, dataset(listing()))
        row = comparison['rows'][0]
        self.assertIn('change_reasons', row)
        self.assertIn('commute', '；'.join(row['change_reasons']))
        self.assertIn('Destination', '；'.join(row['change_reasons']))
        self.assertIsNone(row['after_score'])

    def test_missing_dimension_is_not_zero_but_zero_weight_is_zero(self):
        p, q = profile(), profile()
        q['weights']['amenities'] = 0
        comparison, _ = self.compare(p, q, dataset(listing(supermarket_distance_m=None)))
        row = comparison['rows'][0]
        self.assertIn('score_contributions', row)
        self.assertEqual(row['score_contributions']['amenities'], {'before': None, 'after': 0.0, 'change': None})
        self.assertIn('Unknown', '；'.join(row['change_reasons']))
        self.assertEqual(row['after_status'], 'eligible')

    def test_peer_only_rank_change_is_explained_as_relative(self):
        p, q = profile(), profile()
        p['weights'] = q['weights'] = {'commute': 1, 'cost': 0, 'housing': 0, 'amenities': 0}
        q['budget']['maximum'] = 500
        comparison, _ = self.compare(p, q, dataset(listing('A'), listing('Z', rent_amount=450)))
        row = next(r for r in comparison['rows'] if r['listing_id'] == 'Z')
        self.assertEqual((row['rank_change'], row['score_change']), (1, 0))
        self.assertIn('change_reasons', row)
        self.assertIn('other candidates', '；'.join(row['change_reasons']))

    def test_unchanged_and_duplicate_rows_have_honest_explanations(self):
        p = profile()
        data = dataset(listing('A'), listing('B', source_listing_id='A'))
        comparison, _ = self.compare(p, p, data)
        for row in comparison['rows']:
            self.assertIn('change_reasons', row)
            self.assertTrue(row['change_reasons'])
        self.assertIn('unchanged', '；'.join(comparison['rows'][0]['change_reasons']))
        self.assertIn('Duplicate', '；'.join(comparison['rows'][1]['change_reasons']))

    def test_different_searches_cannot_be_compared(self):
        p, q = profile(), profile()
        q['search_id'] = 'another-search'
        with self.assertRaisesRegex(ValidationError, 'rental search'):
            self.compare(p, q, dataset(listing()))

    def test_markdown_has_escaped_per_listing_reasons(self):
        p, q = profile(), profile()
        q['budget']['maximum'] = 500
        _, report = self.compare(p, q, dataset(listing()))
        output = render_markdown(report)
        self.assertIn('Reasons for change', output)
        report['comparison']['rows'][0]['change_reasons'] = ['<script>|[link](bad)']
        output = render_markdown(report)
        self.assertNotIn('<script>', output)
        self.assertIn('&#124;', output)

    def test_legacy_comparison_is_readable_but_has_no_fabricated_explanation(self):
        p = profile()
        _, report = self.compare(p, p, dataset(listing()))
        for row in report['comparison']['rows']:
            row.pop('change_reasons', None)
            row.pop('score_contributions', None)
        validate_contract('RecommendationReport', report)
        self.assertIn('The older report has no reasons for change', render_markdown(report))

    def test_explanation_schema_rejects_wrong_type(self):
        p = profile()
        _, report = self.compare(p, p, dataset(listing()))
        report['comparison']['rows'][0]['change_reasons'] = 'not-an-array'
        with self.assertRaisesRegex(ValidationError, 'change_reasons'):
            validate_contract('RecommendationReport', report)

    def test_inputs_and_scores_are_unchanged(self):
        p, q = profile(), profile()
        q['weights']['cost'] = 0.6
        data = dataset(listing())
        before, after = evaluate(p, data), evaluate(q, data)
        originals = copy.deepcopy((before, after))
        compare_reports(before, after)
        self.assertEqual((before, after), originals)


if __name__ == '__main__':
    unittest.main()
