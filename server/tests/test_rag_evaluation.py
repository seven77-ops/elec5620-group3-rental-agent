"""Evaluation measures passage recall and mechanical checks, never legal correctness."""
import importlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from server.app.rag.index import KnowledgeIndex
from server.tests.test_rag import document

ROOT = Path(__file__).resolve().parents[2]


class EvaluationTests(unittest.TestCase):
    def api(self):
        try:
            return importlib.import_module('server.app.rag.evaluation')
        except ModuleNotFoundError:
            self.fail('The passage-level RAG evaluation subsystem is not implemented')

    def fixture(self):
        return {'id':'repair-1','question':'How to request repairs?', 'language':'en',
                'category':'procedure','answerability':'supported',
                'targets':[{'document_id':'repairs','section':'Requesting repairs','text_contains':['as soon as possible']}],
                'required_claim_patterns':['landlord|agent'],'forbidden_claim_patterns':['stop paying rent'],
                'expected_conditions':['Contact the landlord or agent first.'],
                'manual_review':['Check whether the paraphrase preserves the condition.']}

    def index(self, folder):
        index=KnowledgeIndex(Path(folder)/'index.sqlite3');index.publish([document()]);return index

    def test_fixture_requires_a_real_passage_not_only_a_document_title(self):
        api=self.api()
        with tempfile.TemporaryDirectory() as folder:
            index=self.index(folder);case=self.fixture()
            api.validate_cases([case],index)
            case['targets'][0]['text_contains']=['invented reimbursement promise']
            with self.assertRaisesRegex(ValueError,'target'):api.validate_cases([case],index)

    def test_retrieval_score_does_not_count_irrelevant_section_in_right_document(self):
        api=self.api();case=self.fixture()
        wrong={**document(),'chunk_id':'wrong','section':'Wrong section','text':'as soon as possible'}
        right={**wrong,'chunk_id':'right','section':'Requesting repairs'}
        score=api.score_retrieval(case,[wrong,right])
        self.assertEqual(score['recall_at_1'],0);self.assertEqual(score['recall_at_3'],1)
        self.assertEqual(score['reciprocal_rank'],.5)

    def test_no_answer_retrieval_is_not_scored_as_recall_success(self):
        api=self.api();case={**self.fixture(),'answerability':'unsupported','targets':[]}
        score=api.score_retrieval(case,[{'text':'unrelated'}])
        self.assertIsNone(score['recall_at_6']);self.assertTrue(score['retrieved_on_unsupported'])

    def test_citation_exactness_and_claim_condition_checks_are_separate(self):
        api=self.api()
        with tempfile.TemporaryDirectory() as folder:
            index=self.index(folder);row=index.search('repairs')[0]
            answer={'status':'answered','claims':[{'text':'Stop paying rent.','evidence_id':row['chunk_id'],'quote':row['text']}],
                    'citations':[{'evidence_id':row['chunk_id'],'quote':row['text']}], 'unknowns':[]}
            score=api.score_answer(self.fixture(),answer,{row['chunk_id']:row})
            self.assertTrue(score['exact_citations']);self.assertFalse(score['condition_heuristics_passed'])
            self.assertEqual(score['support_judgment'],'pending_human_review')
            answer['citations'][0]['quote']='Fabricated quotation'
            self.assertFalse(api.score_answer(self.fixture(),answer,{row['chunk_id']:row})['exact_citations'])

    def test_claim_without_its_own_matching_citation_is_invalid(self):
        api=self.api()
        with tempfile.TemporaryDirectory() as folder:
            index=self.index(folder);row=index.search('repairs')[0]
            answer={'status':'answered','claims':[{'text':'Call your landlord','evidence_id':row['chunk_id'],'quote':'made up'}],
                    'citations':[{'evidence_id':row['chunk_id'],'quote':row['text']}]}
            self.assertFalse(api.score_answer(self.fixture(),answer,{row['chunk_id']:row})['exact_citations'])

    def test_unsupported_question_requires_empty_claims_and_records_unknowns(self):
        api=self.api();case={**self.fixture(),'answerability':'private_unavailable','targets':[]}
        result=api.score_answer(case,{'status':'sources_only','claims':[], 'citations':[], 'unknowns':[]},{})
        self.assertTrue(result['abstained']);self.assertEqual(result['support_judgment'],'pending_human_review')
        result=api.score_answer(case,{'status':'answered','claims':[{'text':'Your lease allows pets'}], 'citations':[]},{})
        self.assertFalse(result['abstained']);self.assertFalse(result['automated_checks_passed'])

    def test_offline_modes_are_explicitly_skipped_and_never_call_cloud(self):
        api=self.api()
        class NoCloud:
            def status(self):return {'embedding_configured':True,'rerank_configured':True}
            def embed(self,*args,**kwargs):raise AssertionError('offline cloud call')
        with tempfile.TemporaryDirectory() as folder:
            index=self.index(folder)
            report=api.evaluate(index,[self.fixture()],provider=NoCloud(),as_of=date(2026,10,30))
            self.assertEqual(report['modes']['keyword']['summary']['evaluated'],1)
            self.assertEqual(report['modes']['hybrid']['status'],'skipped')
            self.assertEqual(report['modes']['hybrid_rerank']['status'],'skipped')
            self.assertEqual(report['human_review_completed'],False)

    def test_external_modes_share_query_vectors_and_do_not_write_index(self):
        api=self.api()
        class Cloud:
            model='test';dimensions=2;rerank_model='test-rerank'
            calls=0
            def status(self):return {'embedding_configured':True,'rerank_configured':True,'embedding_model':self.model,'dimensions':2,'rerank_model':self.rerank_model}
            def embed(self,texts,**kwargs):self.calls+=1;return [[1.,0.] for _ in texts]
            def rerank(self,q,docs):return list(reversed(range(len(docs))))
        with tempfile.TemporaryDirectory() as folder:
            index=self.index(folder);row=index.search('repairs')[0]
            index.save_vectors([row['chunk_id']],[[1.,0.]],'test',2);before=index.path.read_bytes();cloud=Cloud()
            report=api.evaluate(index,[self.fixture()],provider=cloud,external=True,as_of=date(2026,10,30))
            self.assertEqual(cloud.calls,1);self.assertEqual(index.path.read_bytes(),before)
            self.assertEqual(report['modes']['hybrid_rerank']['status'],'completed')
            self.assertEqual(report['external_calls']['embedding_requests'],1)

    def test_expired_sources_are_filtered_in_every_mode(self):
        api=self.api()
        with tempfile.TemporaryDirectory() as folder:
            report=api.evaluate(self.index(folder),[self.fixture()],as_of=date(2027,3,1))
            self.assertEqual(report['modes']['keyword']['cases'][0]['retrieved'],[])
            self.assertGreater(report['index']['stale_chunks'],0)

    def test_failed_external_embedding_is_degraded_not_a_hybrid_pass(self):
        api=self.api()
        from server.app.rag.provider import RetrievalError
        class Cloud:
            model='test';dimensions=2
            def status(self):return {'embedding_configured':True,'rerank_configured':True}
            def embed(self,*args,**kwargs):raise RetrievalError('timeout')
            def rerank(self,q,docs):return list(range(len(docs)))
        with tempfile.TemporaryDirectory() as folder:
            index=self.index(folder);row=index.search('repairs')[0];index.save_vectors([row['chunk_id']],[[1.,0.]],'test',2)
            report=api.evaluate(index,[self.fixture()],provider=Cloud(),external=True,as_of=date(2026,10,30))
            self.assertEqual(report['modes']['hybrid']['status'],'degraded')
            self.assertFalse(report['modes']['hybrid']['cases'][0]['semantic_used'])
            self.assertIn('embedding:timeout',report['modes']['hybrid']['cases'][0]['degradation'])

    def test_review_sheet_preserves_question_conditions_and_empty_human_verdict(self):
        api=self.api()
        with tempfile.TemporaryDirectory() as folder:
            report=api.evaluate(self.index(folder),[self.fixture()],as_of=date(2026,10,30))
            path=api.write_report(report,Path(folder)/'report.json')
            rows=json.loads(path.with_suffix('.review.json').read_text())
            self.assertEqual(rows[0]['question'],self.fixture()['question'])
            self.assertIsNone(rows[0]['human_supported']);self.assertTrue(rows[0]['expected_conditions'])

    def test_eighty_cases_have_reviewable_annotations_and_resolve_to_current_corpus(self):
        api=self.api()
        cases=json.loads((ROOT/'data/knowledge/evaluation.en.json').read_text())
        self.assertEqual(len(cases),80);self.assertEqual(len({c['id'] for c in cases}),80)
        self.assertGreaterEqual(sum(c['language']=='en' for c in cases),65)
        self.assertGreaterEqual(sum(c['answerability']!='supported' for c in cases),8)
        with tempfile.TemporaryDirectory() as folder:
            index=KnowledgeIndex(Path(folder)/'index.sqlite3');index.publish(json.loads((ROOT/'data/knowledge/en/documents.json').read_text()))
            api.validate_cases(cases,index)


    def test_generation_uses_precomputed_retrieval_and_production_quote_validation(self):
        api=self.api()
        class Chat:
            calls=0
            def public_config(self):return {'configured':True,'model':'synthetic-model'}
            def call(self,context):
                self.calls+=1
                row=context['evidence'][0]
                return {'claims':[{'text':'Contact your landlord about repairs.','evidence_id':row['evidence_id'], 'quote_id':row['passages'][0]['quote_id']}], 'unknowns':[]}, {'model':'synthetic-model','status':'success'}
        with tempfile.TemporaryDirectory() as folder:
            index=self.index(folder);chat=Chat()
            report=api.evaluate(index,[self.fixture()],external=True,generate=True,ai_provider=chat,
                                generation_modes=('keyword',),as_of=date(2026,10,30))
            result=report['modes']['keyword']['cases'][0]
            self.assertEqual(chat.calls,1);self.assertTrue(result['answer_checks']['automated_checks_passed'])
            self.assertEqual(result['answer']['claims'][0]['quote'],index.search('repairs')[0]['text'])
            self.assertEqual(report['external_calls']['generation_attempts'],1)
            self.assertEqual(report['modes']['keyword']['summary']['human_support_pass_rate'],None)

    def test_generation_rejected_quote_is_not_counted_as_an_answer_pass(self):
        api=self.api()
        class Chat:
            def public_config(self):return {'configured':True,'model':'synthetic-model'}
            def call(self,context):
                return {'claims':[{'text':'Guaranteed success','evidence_id':'other-private-tenant', 'quote_id':'p0'}], 'unknowns':[]}, {}
        with tempfile.TemporaryDirectory() as folder:
            report=api.evaluate(self.index(folder),[self.fixture()],external=True,generate=True,ai_provider=Chat(),
                                generation_modes=('keyword',),as_of=date(2026,10,30))
            result=report['modes']['keyword']['cases'][0]
            self.assertEqual(result['answer']['status'],'sources_only')
            self.assertFalse(result['answer_checks']['automated_checks_passed'])

    def test_rerank_failure_retains_fused_results_and_records_degradation(self):
        api=self.api()
        from server.app.rag.provider import RetrievalError
        class Cloud:
            model='test';dimensions=2
            def status(self):return {'embedding_configured':True,'rerank_configured':True}
            def embed(self,texts,**kwargs):return [[1.,0.] for _ in texts]
            def rerank(self,*args):raise RetrievalError('timeout')
        with tempfile.TemporaryDirectory() as folder:
            index=self.index(folder);row=index.search('repairs')[0];index.save_vectors([row['chunk_id']],[[1.,0.]],'test',2)
            report=api.evaluate(index,[self.fixture()],provider=Cloud(),external=True,as_of=date(2026,10,30))
            self.assertEqual(report['modes']['hybrid_rerank']['status'],'degraded')
            result=report['modes']['hybrid_rerank']['cases'][0]
            self.assertEqual(result['retrieved'],report['modes']['hybrid']['cases'][0]['retrieved'])
            self.assertFalse(result['rerank_used']);self.assertEqual(result['degradation'],['rerank:timeout'])


    def test_cloud_failure_is_not_mislabeled_as_successful_no_answer_behavior(self):
        api=self.api()
        from server.app.ai.provider import ProviderError
        class Chat:
            def public_config(self):return {'configured':True,'model':'synthetic-model'}
            def call(self,context):raise ProviderError('ai_timeout',{'status':'failed'})
        with tempfile.TemporaryDirectory() as folder:
            case={**self.fixture(),'answerability':'private_unavailable','targets':[]}
            report=api.evaluate(self.index(folder),[case],external=True,generate=True,ai_provider=Chat(),
                                generation_modes=('keyword',),as_of=date(2026,10,30))
            result=report['modes']['keyword']['cases'][0]
            self.assertTrue(result['answer_checks']['abstained'])
            self.assertFalse(result['answer_checks']['automated_checks_passed'])
            self.assertEqual(result['generation_observation']['error_code'],'ai_timeout')

    def test_valid_empty_model_claims_preserve_unknowns_for_abstention_review(self):
        api=self.api()
        class Chat:
            def public_config(self):return {'configured':True,'model':'synthetic-model'}
            def call(self,context):return {'claims':[], 'unknowns':['The private lease is not supplied.']}, {}
        with tempfile.TemporaryDirectory() as folder:
            case={**self.fixture(),'answerability':'private_unavailable','targets':[]}
            report=api.evaluate(self.index(folder),[case],external=True,generate=True,ai_provider=Chat(),
                                generation_modes=('keyword',),as_of=date(2026,10,30))
            result=report['modes']['keyword']['cases'][0]
            self.assertTrue(result['generation_observation']['valid_model_abstention'])
            self.assertEqual(result['generation_observation']['raw_response']['unknowns'],['The private lease is not supplied.'])
            self.assertEqual(result['answer']['unknowns'],['The private lease is not supplied.'])
            self.assertEqual(report['modes']['keyword']['summary']['generation_outcomes'],{'model_abstained':1})
            self.assertTrue(result['answer_checks']['automated_checks_passed'])

    def test_preserved_english_is_reported_without_passing_chinese_requirements(self):
        case={**self.fixture(),'language':'zh','required_claim_patterns':['Weekdays']}
        quote='Allow two business days for the payment.'
        answer={'status':'answered','language':'zh','answer_language':'en','source_preserving':True,
                'generation_outcome':'answered','claims':[{'text':quote,'evidence_id':'one','quote':quote}],
                'citations':[{'evidence_id':'one','quote':quote}]}
        checks=self.api().score_answer(case,answer,{'one':{'text':quote}})
        self.assertTrue(checks['requested_language_not_delivered'])
        self.assertFalse(checks['automated_checks_passed'])
        self.assertEqual(checks['generation_outcome'],'answered')


class EvaluationCliTests(unittest.TestCase):
    def test_generate_requires_explicit_external_flag(self):
        import subprocess
        result=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/rag_evaluate.py'),'--generate'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('--generate requires --external',result.stderr)

    def test_cli_writes_offline_report_without_touching_live_index(self):
        import subprocess
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'result.json'
            result=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/rag_evaluate.py'),'--limit','2','--output',str(output),'--as-of','2026-10-30'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads(output.read_text());self.assertEqual(report['case_count'],2)
            self.assertEqual(report['modes']['hybrid']['status'],'skipped')
