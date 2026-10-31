"""Public presentation must summarize in the requested language without dropping grounding."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from server.app.rag.service import KnowledgeService
from server.tests.test_rag_answer_integrity import row


class PublicSummaryTests(unittest.TestCase):
    def answer(self, candidate=None, *, external=True, base=None, source=None, checked=True, revised=None, original_supported=True):
        source=source or row(text='If repairs are needed, contact the landlord or agent first. Allow 14 days for a response.')
        first={'claims':[{'text':'When repairs are needed, contact the landlord or agent first and allow 14 days for a response.','evidence_id':'source-a','quote_id':'p0'}],'unknowns':[]}
        reviewed={'claims':[{'text':'When repairs are needed, contact the landlord or agent first and allow 14 days for a response.','evidence_id':'source-a','quote_ids':['p0'],
                             'grounded':True,'conditions_preserved':True}],'unknowns':[]}
        self.inputs=[]
        def call(context):
            self.inputs.append(deepcopy(context))
            if context['task']=='rag_summary_check':return {'supported':[checked]*len(context['checks']),'original_supported':[original_supported]*len(context['checks']),
                'texts':[revised or c['claim'] for c in context['checks']]},{'task':context['task']}
            return deepcopy((candidate or reviewed) if context['task']=='rag_grounded_summary' else (base or first)), {'task':context['task']}
        service=KnowledgeService.__new__(KnowledgeService)
        service.ctx=SimpleNamespace(ai_provider=SimpleNamespace(call=call))
        service.index=SimpleNamespace(status=lambda:{'index_version':'test'})
        service.retrieve=lambda *args:{'evidence':[source],'index_version':'test','warnings':[],'scope':'public'}
        return service.answer('需要维修时先找谁？',external,'zh')

    def test_legacy_language_request_gets_english_summary_with_exact_evidence(self):
        answer=self.answer()
        self.assertEqual(answer['status'],'answered')
        self.assertIn('contact the landlord',answer['answer']);self.assertNotIn('If repairs',answer['answer'])
        self.assertIn('If repairs',answer['citations'][0]['quote'])
        self.assertEqual(answer['answer_language'],'en')
        self.assertEqual(answer['summary_method'],'source_reviewed_summary')
        self.assertEqual([v['task'] for v in self.inputs],['rag_answer','rag_grounded_summary','rag_summary_check'])

    def test_wrong_language_model_summary_cannot_be_published_as_english(self):
        candidate={'claims':[{'text':'先联系房东或中介。','evidence_id':'source-a','quote_ids':['p0'],
                             'grounded':True,'conditions_preserved':True}],'unknowns':[]}
        answer=self.answer(candidate)
        self.assertNotIn('先联系房东',answer['answer'])
        self.assertNotEqual(answer.get('summary_method'),'source_reviewed_summary')
        self.assertTrue(answer['citations'])

    def test_bad_review_cannot_bypass_numbers_citations_conditions_or_certainty(self):
        for change in ({'text':'Allow 30 days for a response.'}, {'evidence_id':'private-other-case'}, {'conditions_preserved':False},
                       {'grounded':False}, {'text':'Compensation is guaranteed.'}, {'text':'A refund can be requested when the bond status is HELD.'}):
            with self.subTest(change=change):
                claim={'text':'When repairs are needed, contact the landlord or agent first and allow 14 days for a response.','evidence_id':'source-a','quote_ids':['p0'],
                       'grounded':True,'conditions_preserved':True,**change}
                answer=self.answer({'claims':[claim],'unknowns':[]})
                self.assertNotEqual(answer.get('summary_method'),'source_reviewed_summary')
                self.assertNotIn('30 days',answer['answer']);self.assertNotIn('Compensation',answer['answer'])

    def test_invalid_first_draft_is_not_forwarded_as_accepted_text(self):
        answer=self.answer(base={'claims':[{'text':'Invented bad draft 999 days','evidence_id':'other-case','quote_id':'p0'}],'unknowns':[]})
        self.assertEqual(answer['status'],'answered')
        self.assertNotIn('Invented bad draft',str(self.inputs))

    def test_local_private_and_intentional_abstention_do_not_trigger_public_summary(self):
        self.answer(external=False);self.assertFalse(self.inputs)
        self.answer(source={**row(),'source_type':'user_contract'});self.assertEqual(len(self.inputs),1)
        answer=self.answer(base={'claims':[],'unknowns':['Need a private rent ledger.']})
        self.assertEqual(answer['generation_outcome'],'model_abstained');self.assertEqual(len(self.inputs),1)

    def test_provider_outage_does_not_trigger_a_second_cloud_call(self):
        from server.app.ai.provider import ProviderError
        from server.app.rag.public_summary import review_public_summary
        for scope in ('public','contract'):
            calls=[]
            def fail(context):calls.append(context);raise ProviderError('ai_timeout',{})
            service=KnowledgeService.__new__(KnowledgeService)
            service.ctx=SimpleNamespace(ai_provider=SimpleNamespace(call=fail))
            service.index=SimpleNamespace(status=lambda:{'index_version':'test'})
            service.retrieve=lambda *args:{'evidence':[row()],'index_version':'test','warnings':[],'scope':scope}
            result=service.answer('How do I request repairs?',True,'en')
            self.assertEqual(result['generation_outcome'],'provider_error');self.assertEqual(len(calls),1)
        # Even a failed draft cannot send private text through this public presenter.
        result={'scope':'contract','generation_outcome':'invalid_citation','claims':[]}
        self.assertIs(review_public_summary(None,'question','en',[row()],result),result)

    def test_review_rejection_is_atomic_and_keeps_original_evidence(self):
        good={'text':'When repairs are needed, contact the landlord or agent first.','evidence_id':'source-a','quote_ids':['p0'],'grounded':True,'conditions_preserved':True}
        answer=self.answer({'claims':[good,{**good,'evidence_id':'invented'}],'unknowns':[]})
        self.assertNotEqual(answer.get('summary_method'),'source_reviewed_summary')
        self.assertIn('If repairs',answer['citations'][0]['quote'])
        self.assertEqual(answer['status'],'sources_only');self.assertFalse(answer['claims'])
        self.assertNotIn('If repairs',answer['answer'])

    def test_independent_check_rejects_cross_source_facts(self):
        answer=self.answer(checked=False)
        self.assertNotEqual(answer.get('summary_method'),'source_reviewed_summary')
        check=self.inputs[-1]
        self.assertEqual(check['task'],'rag_summary_check')
        self.assertNotIn('evidence',check);self.assertNotIn('accepted_draft',check)
        self.assertEqual(set(check['checks'][0]),{'claim','quote','source_context'})

    def test_each_synthesis_request_is_isolated_to_its_own_source(self):
        from server.app.rag.public_summary import review_public_summary
        inputs=[]
        def call(context):
            inputs.append(deepcopy(context))
            if context['task']=='rag_summary_check':return {'supported':[True,True],'original_supported':[True,True],'texts':[c['claim'] for c in context['checks']]},{}
            self.assertEqual(len(context['evidence']),1)
            source=context['evidence'][0]
            claim={'text':'When repairs are needed, contact the landlord or agent first.','evidence_id':source['evidence_id'],
                   'quote_ids':['p0'],'grounded':True,'conditions_preserved':True}
            return {'claims':[claim],'unknowns':[]},{}
        result={'scope':'public','source_preserving':True,'claims':[{'evidence_id':'source-a'},{'evidence_id':'source-b'}],
                'warnings':[],'citations':[],'generation_outcome':'answered'}
        answer=review_public_summary(SimpleNamespace(call=call),'维修先找谁？','zh',
            [row(),row('source-b')],result,timeout=25)
        self.assertEqual(answer['summary_method'],'source_reviewed_summary')
        self.assertEqual(len(answer['claims']),2)
        self.assertEqual(len(inputs),3)
        self.assertNotIn('accepted_draft',str(inputs))

    def test_reviewed_revision_is_checked_again_not_confused_with_failed_original(self):
        answer=self.answer(original_supported=False,revised='When repairs are needed, contact the landlord or agent first.')
        self.assertEqual(answer['summary_method'],'source_reviewed_summary')
        answer=self.answer(original_supported=False,revised='需要维修时，应等待99天。')
        self.assertEqual(answer['status'],'sources_only');self.assertNotIn('99天',answer['answer'])


if __name__=='__main__':unittest.main()
