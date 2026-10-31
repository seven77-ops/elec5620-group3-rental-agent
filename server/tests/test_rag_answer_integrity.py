"""Source-bound answer contract: citation pairs, abstention and presentation."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from jsonschema import Draft202012Validator
from server.app.rag.service import KnowledgeService,passages


def row(identifier='source-a',text='Contact the landlord or agent first.'):
    return {'chunk_id':identifier,'document_id':identifier,'title':'Synthetic repairs guide','section':'Repair requests',
            'text':text,'source_url':'https://www.nsw.gov.au/test-only','checked_at':'2026-10-30','content_hash':'synthetic',
            'source_type':'official_guidance','language':'en'}


class AnswerIntegrityTests(unittest.TestCase):
    def compose(self,raw,evidence=None,language='en',question='Who should I contact first?'):
        self.inputs=[]
        def call(context):
            self.inputs.append(deepcopy(context));return deepcopy(raw),{'task':'rag_answer','status':'succeeded','model':'synthetic'}
        service=KnowledgeService.__new__(KnowledgeService)
        service.ctx=SimpleNamespace(ai_provider=SimpleNamespace(call=call))
        return service.compose(question,{'index_version':'synthetic','retrieval_methods':['keywords'],'warnings':[]},
                               evidence or [row()],True,language)

    def test_prompt_schema_allows_only_quote_pairs_from_this_request(self):
        evidence=[row(),row('source-b','Another sufficiently long source paragraph.\n\n'+('Background facts. '*220)+'\n\nA final sufficiently long source paragraph.')]
        self.compose({'claims':[],'unknowns':['Not enough evidence.']},evidence)
        schema=self.inputs[0]['response_schema'];validator=Draft202012Validator(schema)
        for item in self.inputs[0]['evidence']:
            for quote in item['passages']:
                valid={'claims':[{'text':'A brief supported claim.','evidence_id':item['evidence_id'],'quote_id':quote['quote_id']}],'unknowns':[]}
                self.assertFalse(list(validator.iter_errors(valid)))
        # p1 exists for B, but not A: independently valid identifiers are insufficient.
        for identifier,quote_id in [('source-a','p1'),('other-private-source','p0'),('source-a','p99')]:
            invalid={'claims':[{'text':'A claim.','evidence_id':identifier,'quote_id':quote_id}],'unknowns':[]}
            self.assertTrue(list(validator.iter_errors(invalid)),(identifier,quote_id))

    def test_intentional_abstention_preserves_missing_facts_without_outage_warning(self):
        answer=self.compose({'claims':[],'unknowns':['The private contract was not supplied.']})
        self.assertEqual(answer['status'],'insufficient_evidence')
        self.assertEqual(answer['unknowns'],['The private contract was not supplied.'])
        self.assertEqual(answer['generation_outcome'],'model_abstained')
        self.assertFalse(answer['warnings']);self.assertFalse(answer['claims'])
        self.assertTrue(answer['citations']);self.assertEqual(len(self.inputs),1)

    def test_source_preservation_deduplicates_identical_passages(self):
        text='If repairs are needed, contact the landlord or agent first.'
        answer=self.compose({'claims':[
            {'text':'Contact the landlord.','evidence_id':'source-a','quote_id':'p0'},
            {'text':'Contact the agent.','evidence_id':'source-a','quote_id':'p0'}],'unknowns':[]},[row(text=text)])
        self.assertEqual(answer['status'],'answered');self.assertEqual(len(answer['claims']),1)
        self.assertEqual(len(answer['citations']),1);self.assertNotIn('[2]',answer['answer'])
        self.assertEqual(answer['claims'][0]['quote'],text)

    def test_invalid_claim_is_never_silently_dropped_or_retried(self):
        answer=self.compose({'claims':[
            {'text':'Contact your landlord first.','evidence_id':'source-a','quote_id':'p0'},
            {'text':'Guaranteed invented outcome.','evidence_id':'other-case','quote_id':'p0'}],'unknowns':[]})
        self.assertEqual(answer['status'],'sources_only');self.assertFalse(answer['claims'])
        self.assertEqual(answer['generation_outcome'],'invalid_citation')
        self.assertNotIn('Guaranteed invented',answer['answer']);self.assertEqual(len(self.inputs),1)

    def test_legacy_language_request_returns_english_with_preserved_source(self):
        quote='If repairs are needed, contact the landlord or agent first.'
        answer=self.compose({'claims':[{'text':'先联系房东或中介。','evidence_id':'source-a','quote_id':'p0'}],'unknowns':[]},
                            [row(text=quote)],language='zh',question='维修先找谁？')
        self.assertEqual(answer['status'],'answered');self.assertEqual(answer['language'],'en')
        self.assertEqual(answer['answer_language'],'en');self.assertTrue(answer['source_preserving'])
        self.assertTrue(all(not any('\u4e00' <= ch <= '\u9fff' for ch in warning) for warning in answer['warnings']))
        self.assertEqual(answer['claims'][0]['quote'],quote)

    def test_untranslated_initial_claim_cannot_be_labelled_as_an_english_answer(self):
        answer=self.compose({'claims':[{'text':'先联系房东或中介。','evidence_id':'source-a','quote_id':'p0'}],'unknowns':[]},
                            [row(text='Contact the landlord or agent first.')],question='Who should I contact first?')
        self.assertNotIn('先联系房东',answer['answer'])
        self.assertFalse(answer['claims'])
        self.assertEqual(answer['status'],'sources_only')

    def test_untranslated_unknowns_are_not_published(self):
        answer=self.compose({'claims':[],'unknowns':['请提供租约。']})
        self.assertFalse(answer['unknowns'])
        self.assertEqual(answer['status'],'sources_only')

    def test_no_complete_passage_is_not_sent_as_empty_citation_options(self):
        answer=self.compose({'claims':[],'unknowns':[]},[row(text='When requesting a repair, the tenant should')])
        self.assertEqual(answer['status'],'sources_only');self.assertEqual(answer['generation_outcome'],'no_complete_passages')
        self.assertFalse(self.inputs)
