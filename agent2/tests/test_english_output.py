"""English authored output retains source facts, IDs and deterministic scoring."""
from copy import deepcopy
import re
import unittest
from rental_agent.engine import evaluate
from rental_agent.report import render_markdown
from rental_agent.ai_explanation import explain_recommendations
from test_engine import profile, listing, dataset


class EnglishOutputTests(unittest.TestCase):
    def test_reports_use_english_without_mutating_bilingual_source_facts(self):
        data=dataset(listing(),listing('pending',bills_included=None),listing('excluded',rent_amount=999))
        original=deepcopy(data)
        report=evaluate(profile(),data)
        self.assertEqual(data,original)
        self.assertEqual(report['recommendations'][0]['score'],88.6)
        self.assertIn('Comparable weekly cost',report['recommendations'][0]['reasons'][0])
        self.assertIsNone(re.search(r'[\u3400-\u9fff]',render_markdown(report)))
        self.assertEqual(data['listings'][0]['address'],'虚构地址，仅用于测试')

    def test_explanation_gateway_requests_english(self):
        report=evaluate(profile(),dataset(listing()))
        def gateway(context):
            self.assertIn('English prose',context['instructions'])
            self.assertNotIn('Chinese prose',context['instructions'])
            row=context['recommendations'][0]
            return {'items':[{'listing_id':row['listing_id'],'text':'The saved score reflects the supplied requirements.','evidence_refs':[row['evidence_refs'][0]]}]}
        self.assertEqual(explain_recommendations(report,gateway)['items'][0]['listing_id'],'A')
