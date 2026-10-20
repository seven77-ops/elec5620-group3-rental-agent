import copy
from pathlib import Path
import unittest

from rental_agent.engine import evaluate
from test_engine import dataset, listing, profile


MODULE = Path(__file__).resolve().parents[1] / 'rental_agent' / 'ai_explanation.py'


def saved_report():
    return evaluate(profile(), dataset(
        *[listing(str(index)) for index in range(7)],
        listing('pending', private_bedroom=None),
        listing('excluded', private_bedroom=False),
    ))


def valid_response(report):
    return {'items': [
        {'listing_id': row['listing_id'], 'text': '通勤与费用符合已保存条件，仍须核对原始证据。',
         'evidence_refs': [row['evidence_refs']['rent_amount']['source_ref']]}
        for row in report['recommendations']
    ]}


class AiExplanationTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.exists(), 'Grounded AI explanation module is not implemented')
        from rental_agent.ai_explanation import explain_recommendations
        self.explain = explain_recommendations
        self.report = saved_report()
        self.response = valid_response(self.report)

    def test_saved_top5_only_and_compact_original_context(self):
        inputs = []
        result = self.explain(self.report, lambda context: inputs.append(context) or self.response)
        self.assertEqual(result, self.response)
        self.assertEqual(len(inputs), 1)
        context = inputs[0]
        self.assertEqual(context['task'], 'recommendation_explain')
        self.assertIsInstance(context['instructions'], str)
        self.assertEqual(context['profile'], {key: self.report['profile'][key]
                         for key in ('budget', 'commute', 'soft_preferences', 'weights')})
        self.assertNotIn('eligible', context)
        expected = []
        for row in self.report['recommendations']:
            expected.append({
                **{key: row[key] for key in ('listing_id', 'rank', 'score', 'score_breakdown', 'reasons', 'tradeoffs')},
                'evidence_refs': list(dict.fromkeys(e['source_ref'] for e in row['evidence_refs'].values())),
            })
        self.assertEqual(context['recommendations'], expected)
        self.assertEqual([row['listing_id'] for row in expected], ['0', '1', '2', '3', '4'])

    def test_saved_order_restored_without_changing_ranks_or_scores(self):
        self.response['items'].reverse()
        result = self.explain(self.report, lambda _: self.response)
        self.assertEqual([row['listing_id'] for row in result['items']], ['0', '1', '2', '3', '4'])
        self.assertTrue(all(set(item) == {'listing_id', 'text', 'evidence_refs'} for item in result['items']))

    def test_unknown_pending_excluded_and_non_top5_ids_rejected(self):
        for identifier in ('forged', 'pending', 'excluded', '6', True, {}, None):
            with self.subTest(identifier=identifier):
                response = copy.deepcopy(self.response)
                response['items'][0]['listing_id'] = identifier
                with self.assertRaises(ValueError):
                    self.explain(self.report, lambda _: response)

    def test_duplicate_or_missing_recommendation_rejected(self):
        for items in (self.response['items'][:-1], self.response['items'] + [self.response['items'][0]],
                      [self.response['items'][0]] * 5):
            with self.subTest(items=items), self.assertRaises(ValueError):
                self.explain(self.report, lambda _: {'items': items})

    def test_unknown_cross_listing_or_field_name_refs_rejected(self):
        for refs in (['forged'], ['rent_amount'], ['fixture:pending#rent_amount'],
                     ['fixture:1#rent_amount'], [self.response['items'][0]['evidence_refs'][0], 'forged']):
            with self.subTest(refs=refs):
                response = copy.deepcopy(self.response)
                response['items'][0]['evidence_refs'] = refs
                with self.assertRaises(ValueError):
                    self.explain(self.report, lambda _: response)

    def test_citations_must_be_nonempty_unique_string_list(self):
        ref = self.response['items'][0]['evidence_refs'][0]
        for refs in (None, [], ref, {}, [ref, ref], [True], [{}], [None], ['']):
            with self.subTest(refs=refs):
                response = copy.deepcopy(self.response)
                response['items'][0]['evidence_refs'] = refs
                with self.assertRaises(ValueError):
                    self.explain(self.report, lambda _: response)

    def test_text_must_be_nonempty_and_bounded(self):
        for text in (None, True, 1, {}, [], '', ' \n\t ', 'x' * 1001, ' ' * 1001 + 'x'):
            with self.subTest(text_type=type(text), size=len(text) if isinstance(text, str) else None):
                response = copy.deepcopy(self.response)
                response['items'][0]['text'] = text
                with self.assertRaises(ValueError):
                    self.explain(self.report, lambda _: response)

    def test_text_at_limit_and_trimming(self):
        self.response['items'][0]['text'] = 'x' * 1000
        self.response['items'][1]['text'] = '  仅解释已保存评分。  '
        result = self.explain(self.report, lambda _: self.response)
        self.assertEqual(result['items'][0]['text'], 'x' * 1000)
        self.assertEqual(result['items'][1]['text'], '仅解释已保存评分。')

    def test_malformed_response_shape_rejected(self):
        for response in (None, [], {}, {'items': None}, {'items': {}}, {'items': 'bad'},
                         {'items': [None] * 5}, {'items': [{}] * 5}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                self.explain(self.report, lambda _: response)

    def test_unexpected_result_fields_cannot_change_saved_decisions(self):
        for key, value in (('score', 100), ('rank', 1), ('status', 'eligible'), ('permission', True)):
            with self.subTest(key=key):
                response = copy.deepcopy(self.response)
                response['items'][0][key] = value
                with self.assertRaises(ValueError):
                    self.explain(self.report, lambda _: response)
        with self.assertRaises(ValueError):
            self.explain(self.report, lambda _: {**self.response, 'recommendations': []})

    def test_empty_report_and_no_eligible_rows_skip_gateway(self):
        inputs = []
        for report in ({}, {'recommendations': []}, evaluate(profile(), dataset()),
                       evaluate(profile(), dataset(listing(private_bedroom=None)))):
            with self.subTest(report=report):
                self.assertEqual(self.explain(report, lambda context: inputs.append(context)), {'items': []})
        self.assertEqual(inputs, [])

    def test_report_and_gateway_response_immutable(self):
        before = copy.deepcopy(self.report)
        original_response = copy.deepcopy(self.response)
        result = self.explain(self.report, lambda _: self.response)
        result['items'][0]['text'] = 'changed'
        result['items'][0]['evidence_refs'].clear()
        self.assertEqual(self.report, before)
        self.assertEqual(self.response, original_response)

    def test_gateway_context_mutation_cannot_mutate_report(self):
        before = copy.deepcopy(self.report)
        def gateway(context):
            row = context['recommendations'][0]
            row['score_breakdown']['cost'] = 100
            row['reasons'].append('forged reason')
            row['tradeoffs'].clear()
            row['evidence_refs'].append('forged')
            context['profile']['budget']['maximum'] = 1
            context['profile']['soft_preferences'].clear()
            return self.response
        self.explain(self.report, gateway)
        self.assertEqual(self.report, before)

    def test_gateway_context_mutation_cannot_authorize_forged_id_or_reference(self):
        for key, value in (('listing_id', 'forged'), ('evidence_refs', ['forged'])):
            with self.subTest(key=key):
                def gateway(context):
                    context['recommendations'][0][key] = value
                    response = copy.deepcopy(self.response)
                    response['items'][0][key] = value
                    return response
                with self.assertRaises(ValueError):
                    self.explain(self.report, gateway)

    def test_gateway_failure_propagates_without_mutation(self):
        before = copy.deepcopy(self.report)
        failure = RuntimeError('local test transport failure')
        def gateway(_):
            raise failure
        with self.assertRaises(RuntimeError) as caught:
            self.explain(self.report, gateway)
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.report, before)

    def test_duplicate_original_refs_are_compacted_without_rewriting(self):
        row = self.report['recommendations'][0]
        row['evidence_refs']['another_field'] = copy.deepcopy(row['evidence_refs']['rent_amount'])
        inputs = []
        self.explain(self.report, lambda context: inputs.append(context) or self.response)
        refs = inputs[0]['recommendations'][0]['evidence_refs']
        self.assertEqual(len(refs), len(set(refs)))
        self.assertIn('fixture:0#rent_amount', refs)

    def test_saved_recommendation_without_original_evidence_ref_fails_before_call(self):
        inputs = []
        for refs in ({}, [], {'rent_amount': {}}, {'rent_amount': {'source_ref': ''}},
                     {'rent_amount': {'source_ref': True}}, {'rent_amount': 'forged'}):
            with self.subTest(refs=refs):
                report = copy.deepcopy(self.report)
                report['recommendations'][0]['evidence_refs'] = refs
                with self.assertRaises(ValueError):
                    self.explain(report, lambda context: inputs.append(context))
        self.assertEqual(inputs, [])

    def test_malformed_or_ineligible_recommendation_input_skips_gateway_and_fails(self):
        inputs = []
        reports = [None, [], {'recommendations': None}, {'recommendations': {}},
                   {'recommendations': [None]}, {'recommendations': [self.report['pending_confirmation'][0]]},
                   {'recommendations': [self.report['recommendations'][0]] * 2},
                   {'recommendations': self.report['eligible']}]
        for report in reports:
            with self.subTest(report=report), self.assertRaises(ValueError):
                self.explain(report, lambda context: inputs.append(context))
        self.assertEqual(inputs, [])


if __name__ == '__main__':
    unittest.main()
