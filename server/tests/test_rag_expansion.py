"""Expanded English source provenance, scoped retrieval and product help integration."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.app.rag.index import KnowledgeIndex
from server.tests.test_rag import document
from server.tests.test_assistant_api import IntentProvider
import json

def captured(identifier):
    path=Path(__file__).resolve().parents[2]/'data/knowledge/en/official-expansion.json'
    return next(d for d in json.loads(path.read_text()) if d['document_id']==identifier)


class ExpansionIndexTests(unittest.TestCase):
    def test_school_advice_and_template_types_preserve_source_identity(self):
        with TemporaryDirectory() as folder:
            index=KnowledgeIndex(Path(folder)/'rag.sqlite3')
            school=captured('student-off-campus');template=captured('standard-lease')
            index.publish([school,template])
            rows=index.search('rent',limit=100,source_types=('official_template',));self.assertTrue(rows)
            self.assertEqual(rows[0]['source_type'],'official_template')
            self.assertEqual(rows[0]['document_url'],template['download_url']+'#page='+str(rows[0]['page']))
            self.assertTrue(index.search('scam',source_types=('student_guidance',)))
            self.assertFalse(index.search('scam',source_types=('official_template',)))
            self.assertEqual({v['source_type']:v['documents'] for v in index.status()['source_breakdown']},
                             {'official_template':1,'student_guidance':1})

    def test_source_type_filters_apply_before_keyword_and_vector_limits(self):
        with TemporaryDirectory() as folder:
            index=KnowledgeIndex(Path(folder)/'rag.sqlite3')
            official=[document('guide-'+str(i),text='Favorite comparison rental repair information.') for i in range(25)]
            school=captured('student-off-campus')
            index.publish(official+[school]);all_rows=index.search('rental',limit=100)
            index.save_vectors([r['chunk_id'] for r in all_rows],[[1.,0.]]*len(all_rows),'test',2)
            for rows in (index.search('rental',limit=1,source_types=('student_guidance',)),
                         index.vector_search([1.,0.],'test',2,limit=1,source_types=('student_guidance',))):
                self.assertEqual([r['document_id'] for r in rows],['student-off-campus'])
            self.assertEqual(index.search('repair',source_types=()),[])

    def test_public_roles_and_derived_urls_cannot_be_forged(self):
        with TemporaryDirectory() as folder:
            index=KnowledgeIndex(Path(folder)/'rag.sqlite3')
            for changes in ({'source_type':'student_guidance'},
                            {'source_type':'official_template','source_url':'https://www.sydney.edu.au/test'},
                            {'document_url':'javascript:alert(1)'},
                            {'download_url':'http://localhost/private.pdf'},
                            {'source_type':'product_guide','jurisdiction':'PRODUCT','source_url':'/api/v1/rag/product-guide'}):
                with self.subTest(changes=changes),self.assertRaises(ValueError):index.publish([{**document(),**changes}])

    def test_registered_pdf_identity_and_content_cannot_be_relabelled(self):
        with TemporaryDirectory() as folder:
            index=KnowledgeIndex(Path(folder)/'rag.sqlite3');template=captured('standard-lease')
            for changes in ({'source_type':'official_guidance'},{'source_url':'https://www.nsw.gov.au/other'},
                            {'document_sha256':'0'*64},{'text':'A private filled agreement must never become official knowledge.'},
                            {'page_count':1},{'download_url':'https://www.nsw.gov.au/different.pdf'}):
                with self.subTest(changes=changes),self.assertRaises(ValueError):index.publish([{**template,**changes}])


class ProductScopeTests(unittest.TestCase):
    def test_inspection_frequency_rubric_accepts_count_nouns_and_requires_period(self):
        from server.app.rag.evaluation import score_answer
        path=Path(__file__).resolve().parents[2]/'data/knowledge/evaluation.expansion.en.json'
        case=next(c for c in json.loads(path.read_text()) if c['id']=='expand-015')
        def score(text):
            answer={'status':'answered','claims':[{'text':text,'evidence_id':'test','quote':text}],
                    'citations':[{'evidence_id':'test','quote':text}]}
            return score_answer(case,answer,{'test':{'text':text}})['automated_checks_passed']
        for noun in ('times','inspections'):
            self.assertTrue(score(f'At least 7 days written notice; no more than 4 {noun} during a 12-month period.'))
        self.assertFalse(score('At least 7 days written notice; no more than 4 inspections.'))

    def test_explanatory_product_questions_are_distinct_from_actions_and_law(self):
        from server.app.rag.scope import is_product_question
        for text in ('How do I save a home to favorites?', 'Do I need to favorite a listing before selecting it?',
                     'How do I generate a lease draft in this app?', 'Does this website send repair emails automatically?',
                     '收藏和选定并跟进有什么区别？','怎么使用我的租房需求？'):
            self.assertTrue(is_product_question(text),text)
        for text in ('Save this house to my favorites.', 'Select the first house.', 'Can you compare my favorite houses?',
                     'How much notice must my landlord give before entry?', 'What is fair wear and tear?',
                     'Is the lease enforceable?', 'Who is responsible for repairs?'):
            self.assertFalse(is_product_question(text),text)

    def test_all_guide_topics_route_without_hijacking_an_explicit_action(self):
        from server.app.rag.scope import is_product_question
        for text in ('How do I upload a contract?','How do I start a new case?',
                     'How do I revoke cloud consent?','How do I edit my rental requirements?','什么是选定并跟进？',
                     'How do I select electricity providers?','How do I record a moving booking?',
                     'How do I prepare inspection questions?','How do I start bond follow-up?',
                     'How do I create a move-out plan?','How do I update repair follow-up records?',
                     'How do I use lifestyle preferences?'):
            self.assertTrue(is_product_question(text),text)
        for text in ('I know how favorites work. Select the first house.',
                     'How do favorites work? Then select the first house.',
                     '我知道怎么收藏了，请选定第一套。','How do I start a new case at NCAT?',
                     'Can you compare my favorites and explain how they differ?'):
            self.assertFalse(is_product_question(text),text)

    def test_product_and_legal_search_do_not_cross_scopes(self):
        from server.app.rag.product_guide import product_document
        with TemporaryDirectory() as folder:
            p=IntentProvider();app=create_app(runtime_dir=folder,ai_provider=p);client=TestClient(app)
            case=client.post('/api/v1/cases',json={}).json();root='/api/v1/cases/'+case['case_id']
            KnowledgeIndex(Path(folder)/'rag.sqlite3').publish([document(),product_document()])
            for question,kind in [('How do I save a home to favorites?','product_guide'),
                                  ('怎么使用我的租房需求？','product_guide'),
                                  ('收藏和选定并跟进有什么区别？','product_guide'),
                                  ('How do I request repairs?','official_guidance')]:
                r=client.post(root+'/rag/search',json={'question':question,'allow_external_ai':False})
                self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['evidence'])
                self.assertEqual({e['source_type'] for e in r.json()['evidence']},{kind})
            self.assertFalse(p.inputs)

    def test_product_help_endpoint_is_readable_and_version_bound(self):
        from server.app.rag.product_guide import product_document
        with TemporaryDirectory() as folder:
            client=TestClient(create_app(runtime_dir=folder,ai_provider=IntentProvider()))
            guide=product_document();r=client.get(guide['source_url']);self.assertEqual(r.status_code,200,r.text)
            self.assertIn('text/html',r.headers['content-type']);self.assertIn('Rental assistant user guide',r.text)
            self.assertEqual(client.get(guide['source_url']+'?version=stale').status_code,409)
            self.assertEqual(client.get(guide['source_url']+'?version='+guide['document_version']).status_code,200)

    def test_native_chat_product_question_is_read_only_and_does_not_demand_a_house(self):
        from server.app.rag.product_guide import product_document
        with TemporaryDirectory() as folder:
            p=IntentProvider();app=create_app(runtime_dir=folder,ai_provider=p);client=TestClient(app)
            case=client.post('/api/v1/cases',json={}).json();root='/api/v1/cases/'+case['case_id']
            KnowledgeIndex(Path(folder)/'rag.sqlite3').publish([product_document(),document()])
            def reply(context):
                if context['task']=='rag_answer':
                    e=context['evidence'][0];p.by_task['rag_answer']={'claims':[{'text':'Favorites and selecting a home are separate options.',
                        'evidence_id':e['evidence_id'],'quote_id':e['passages'][0]['quote_id']}],'unknowns':[]}
            p.on_call=lambda:None
            original=p.call
            def call(context):reply(context);return original(context)
            p.call=call
            c=client.post(root+'/assistant/conversations',json={}).json()
            response=client.post(root+'/assistant/conversations/'+c['conversation_id']+'/messages',json={
                'request_id':'guide','expected_revision':0,'message':'Do I need to favorite a listing before selecting it?','allow_external_ai':True})
            self.assertEqual(response.status_code,200,response.text)
            answer=response.json()['messages'][-1]
            self.assertEqual(answer['intent'],'knowledge');self.assertFalse(answer['listings']);self.assertFalse(answer['actions'])
            self.assertEqual(answer['knowledge']['scope'],'product')
            self.assertTrue(all(c['source_type']=='product_guide' for c in answer['knowledge']['citations']))
            self.assertEqual(client.get(root).json(),case)
