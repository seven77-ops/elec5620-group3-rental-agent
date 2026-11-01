"""English public knowledge, independent cloud adapters and safe read-only answers."""
import json, tempfile, unittest
from pathlib import Path
import httpx
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.tests.test_assistant_api import IntentProvider


def document(identifier='repairs',text='Tell your landlord or agent about repairs as soon as possible.'):
    return {'document_id':identifier,'title':'Rental property repairs','source_url':('https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/getting-repairs-done' if identifier=='repairs' else 'https://www.nsw.gov.au/test-only/'+identifier),
        'source_type':'official_guidance','language':'en','jurisdiction':'NSW','checked_at':'2026-10-30',
        'published_at':None,'text':'## Requesting repairs\n\n'+text}


class IndexTests(unittest.TestCase):
    def setUp(self):
        from server.app.rag.index import KnowledgeIndex
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.index=KnowledgeIndex(Path(self.temp.name)/'knowledge.sqlite3')

    def test_english_and_chinese_queries_keep_exact_source_positions(self):
        self.index.publish([document()])
        for query in ('How do I request repairs?', '怎么报修？'):
            hits=self.index.search(query)
            self.assertTrue(hits,query);self.assertEqual(hits[0]['document_id'],'repairs')
            self.assertEqual(hits[0]['section'],'Requesting repairs')
            self.assertEqual(hits[0]['language'],'en')
        self.assertEqual(self.index.search('quantum banana astrophysics'),[])

    def test_atomic_publish_replaces_removed_chunks_and_preserves_vector_identity(self):
        self.index.publish([document()]);old=self.index.search('repairs')[0]
        self.index.save_vectors([old['chunk_id']],[[1.,0.]],'test-model',2)
        self.assertEqual(self.index.vector_search([1.,0.],'test-model',2)[0]['chunk_id'],old['chunk_id'])
        self.assertEqual(self.index.vector_search([1.,0.],'other-model',2),[])
        with self.assertRaises(ValueError):self.index.save_vectors([old['chunk_id']],[[1.]],'test-model',2)
        self.index.publish([document(text='Bond refunds use Rental Bonds Online.')])
        self.assertEqual(self.index.search('soon'),[])
        self.assertEqual(self.index.vector_search([1.,0.],'test-model',2),[])
        version=self.index.status()['index_version']
        with self.assertRaises(ValueError):self.index.publish([document(),document()])
        self.assertEqual(self.index.status()['index_version'],version)

    def test_private_and_untrusted_sources_never_enter_public_index(self):
        for changes in ({'case_id':'another-case'},{'source_url':'http://localhost/private'},{'language':'zh'}):
            with self.assertRaises(ValueError):self.index.publish([{**document(),**changes}])


class ProviderTests(unittest.TestCase):
    def test_explicit_rag_key_overrides_shared_chat_key_and_validates_shapes(self):
        from server.app.rag.provider import RetrievalProvider, RetrievalError
        bare=RetrievalProvider({'RENTAL_AI_API_KEY':'chat-secret'})
        self.assertFalse(bare.status()['embedding_configured'])
        env={'RENTAL_AI_API_KEY':'chat-secret','RENTAL_RAG_API_KEY':'retrieval-secret','RENTAL_RAG_EMBEDDING_URL':'https://model.example/embeddings',
             'RENTAL_RAG_RERANK_URL':'https://model.example/rerank','RENTAL_RAG_DIMENSIONS':'64'}
        seen=[]
        def transport(request):
            seen.append(json.loads(request.content));self.assertEqual(request.headers['Authorization'],'Bearer retrieval-secret')
            if request.url.path=='/embeddings':return httpx.Response(200,json={'data':[{'index':0,'embedding':[1.]*64}]})
            return httpx.Response(200,json={'output':{'results':[{'index':0,'relevance_score':.8}]}})
        p=RetrievalProvider(env,transport=httpx.MockTransport(transport))
        self.assertEqual(len(p.embed(['repair'])[0]),64)
        self.assertEqual(p.rerank('repair',['repair text']),[0])
        self.assertEqual(seen[0]['dimensions'],64)
        self.assertNotIn('secret',json.dumps(p.status()))
        p=RetrievalProvider(env,transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'data':[{'index':0,'embedding':[1.]}]})))
        with self.assertRaises(RetrievalError):p.embed(['repair'])

    def test_shared_chat_key_is_used_only_for_explicitly_configured_retrieval_urls(self):
        from server.app.rag.provider import RetrievalProvider
        urls={'RENTAL_RAG_EMBEDDING_URL':'https://model.example/embeddings',
              'RENTAL_RAG_RERANK_URL':'https://model.example/rerank','RENTAL_RAG_DIMENSIONS':'64'}
        for credentials in ({'RENTAL_AI_API_KEY':'shared-secret'}, {'AGENT3_MODEL_API_KEY':'shared-secret'},
                            {'RENTAL_RAG_API_KEY':'  ','RENTAL_AI_API_KEY':'shared-secret'}):
            seen=[]
            def transport(request):
                seen.append(request.headers['Authorization'])
                if request.url.path=='/embeddings':return httpx.Response(200,json={'data':[{'index':0,'embedding':[1.]*64}]})
                return httpx.Response(200,json={'output':{'results':[{'index':0,'relevance_score':.8}]}})
            provider=RetrievalProvider({**urls,**credentials},transport=httpx.MockTransport(transport))
            self.assertTrue(provider.status()['embedding_configured'])
            provider.embed(['Synthetic repair request']);provider.rerank('repair',['Synthetic repair request'])
            self.assertEqual(seen,['Bearer shared-secret','Bearer shared-secret'])
            self.assertNotIn('shared-secret',json.dumps(provider.status()))
        # A key alone must never invent a destination, or select an inactive legacy key.
        self.assertFalse(RetrievalProvider({'RENTAL_AI_API_KEY':'shared-secret'}).status()['embedding_configured'])
        self.assertFalse(RetrievalProvider({**urls,'RENTAL_AI_MODEL':'current','AGENT3_MODEL_API_KEY':'inactive'}).status()['embedding_configured'])

    def test_http_failures_report_only_safe_status_for_configuration_diagnostics(self):
        from server.app.rag.provider import RetrievalProvider, RetrievalError
        env={'RENTAL_RAG_API_KEY':'secret','RENTAL_RAG_EMBEDDING_URL':'https://model.example/embeddings'}
        p=RetrievalProvider(env,transport=httpx.MockTransport(lambda r:httpx.Response(401,json={'message':'Never expose upstream secret text'})))
        with self.assertRaises(RetrievalError) as error:p.embed(['Synthetic repair'])
        self.assertEqual(error.exception.http_status,401)
        self.assertEqual(str(error.exception),'http_error')

    def test_bulk_embedding_has_a_separate_bounded_deadline_from_online_queries(self):
        from unittest.mock import patch
        from server.app.rag.provider import RetrievalProvider
        from server.app.ai.provider import run_transport
        env={'RENTAL_RAG_API_KEY':'key','RENTAL_RAG_EMBEDDING_URL':'https://model.example/embed','RENTAL_RAG_DIMENSIONS':'64'}
        p=RetrievalProvider(env,transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'data':[{'index':0,'embedding':[1.]*64}]})))
        with patch('server.app.rag.provider.run_transport',wraps=run_transport) as run:
            p.embed(['Synthetic repair'],timeout=30);self.assertEqual(run.call_args.args[1],30)
            p.embed(['Synthetic repair']);self.assertEqual(run.call_args.args[1],6)
            p.embed(['Synthetic repair'],timeout=900);self.assertEqual(run.call_args.args[1],60)

    def test_rerank_has_a_bounded_ten_second_deadline(self):
        from unittest.mock import patch
        from server.app.rag.provider import RetrievalProvider
        from server.app.ai.provider import run_transport
        p=RetrievalProvider({'RENTAL_RAG_API_KEY':'test','RENTAL_RAG_RERANK_URL':'https://model.example/rerank'},
            transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'output':{'results':[{'index':0,'relevance_score':.8}]}})))
        with patch('server.app.rag.provider.run_transport',wraps=run_transport) as run:
            p.rerank('repairs',['Repair guidance']);self.assertEqual(run.call_args.args[1],10)

    def test_invalid_duplicate_rerank_indexes_and_nonfinite_vectors_rejected(self):
        from server.app.rag.provider import RetrievalProvider, RetrievalError
        env={'RENTAL_RAG_API_KEY':'key','RENTAL_RAG_RERANK_URL':'https://model.example/rerank','RENTAL_RAG_EMBEDDING_URL':'https://model.example/embed'}
        for body in ({'output':{'results':[{'index':0,'relevance_score':.8},{'index':0,'relevance_score':.7}]}},
                     {'output':{'results':[{'index':4,'relevance_score':.8}]}}):
            p=RetrievalProvider(env,transport=httpx.MockTransport(lambda r:httpx.Response(200,json=body)))
            with self.assertRaises(RetrievalError):p.rerank('q',['one'])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.p=IntentProvider();self.client=TestClient(create_app(runtime_dir=self.temp.name,ai_provider=self.p))
        self.case=self.client.post('/api/v1/cases',json={}).json();self.root='/api/v1/cases/'+self.case['case_id']

    def test_status_and_local_search_need_no_cloud_and_do_not_change_case(self):
        r=self.client.get(self.root+'/rag/status');self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['knowledge_language'],'en')
        r=self.client.post(self.root+'/rag/search',json={'question':'How do I request repairs?','allow_external_ai':False})
        self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['evidence']);self.assertFalse(self.p.inputs)
        r=self.client.post(self.root+'/rag/answers',json={'question':'How do I request repairs?','allow_external_ai':False})
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['status'],'sources_only')
        self.assertTrue(r.json()['citations']);self.assertFalse(self.p.inputs)
        self.assertEqual(self.client.get(self.root).json(),self.case)
        self.assertEqual(self.client.get('/api/v1/cases/not-found/rag/status').status_code,404)

    def test_answer_checks_quotes_and_ids_and_no_answer_does_not_call_model(self):
        evidence=self.client.post(self.root+'/rag/search',json={'question':'request repairs','allow_external_ai':False}).json()['evidence'][0]
        self.p.by_task['rag_answer']={'claims':[{'text':'Report the repair to your landlord or agent.','evidence_id':evidence['chunk_id'],'quote_id':'p0'}],'unknowns':[]}
        r=self.client.post(self.root+'/rag/answers',json={'question':'request repairs','allow_external_ai':True})
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['status'],'answered')
        self.assertEqual(r.json()['citations'][0]['evidence_id'],evidence['chunk_id'])
        self.p.by_task['rag_answer']['claims']*=2
        repeated=self.client.post(self.root+'/rag/answers',json={'question':'request repairs','allow_external_ai':True}).json()
        self.assertEqual(len(repeated['citations']),1)
        self.assertNotIn('[2]',repeated['answer'])
        self.p.by_task['rag_answer']={'claims':[{'text':'Invented','evidence_id':'other-case-secret','quote':'not in text'}],'unknowns':[]}
        r=self.client.post(self.root+'/rag/answers',json={'question':'request repairs','allow_external_ai':True})
        self.assertEqual(r.json()['status'],'sources_only');self.assertNotIn('Invented',r.text)
        count=len(self.p.inputs)
        r=self.client.post(self.root+'/rag/answers',json={'question':'quantum banana astrophysics','allow_external_ai':True})
        self.assertEqual(r.json()['status'],'insufficient_evidence');self.assertEqual(len(self.p.inputs),count)
        self.assertEqual(self.client.post(self.root+'/rag/search',json={'question':'repairs','case_id':'secret'}).status_code,422)

    def test_public_chat_route_preserves_requirements_and_returns_citations(self):
        self.p.result={'intent':'knowledge'};self.p.fail=False
        base=self.root+'/assistant/conversations';c=self.client.post(base,json={}).json()
        r=self.client.post(base+'/'+c['conversation_id']+'/messages',json={'request_id':'knowledge','expected_revision':0,'message':'How do I request repairs?','allow_external_ai':True})
        self.assertEqual(r.status_code,200,r.text)
        answer=r.json()['messages'][-1];self.assertTrue(answer['knowledge']['citations'])
        self.assertEqual(answer['listings'],[]);self.assertEqual(self.client.get(self.root).json(),self.case)

class CaptureTests(unittest.TestCase):
    def test_blocked_pages_are_rejected_and_navigation_is_not_knowledge(self):
        from scripts.rag_index import parse_source
        from server.app.rag.sources import SOURCES
        source=next(source for source in SOURCES if source[0]=='repairs')
        with self.assertRaises(ValueError):parse_source(source,'URL Source: '+source[2]+'\nMarkdown Content:\n## 403 ERROR\nRequest blocked. '+('x'*400))
        raw='URL Source: '+source[2]+'\nMarkdown Content:\nMenu links\n# Official rental guide\n\n## Repairs\n'+('Real official guidance. '*25)+'\n## You might also be interested in\nFooter navigation'
        doc=parse_source(source,raw)
        self.assertNotIn('Menu links',doc['text']);self.assertNotIn('Footer navigation',doc['text'])

class RetrievalFailureTests(unittest.TestCase):
    def test_embedding_failure_keeps_published_snapshot_and_keyword_search(self):
        from scripts.rag_index import build
        from server.app.rag.index import KnowledgeIndex
        from server.app.rag.provider import RetrievalError
        from server.app.rag.service import KnowledgeService
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            service=KnowledgeService(SimpleNamespace(repo=SimpleNamespace(directory=Path(folder))))
            class FailedCloud:
                model='test';dimensions=2
                def status(self):return {'embedding_configured':True,'rerank_configured':False}
                def embed(self,texts,**kwargs):raise RetrievalError('timeout')
            row=service.index.search('repairs')[0]
            service.index.save_vectors([row['chunk_id']],[[1.,0.]],'test',2)
            service.provider=FailedCloud()
            before=service.index.status()['index_version']
            report=service.retrieve('How do I request repairs?',True)
            self.assertTrue(report['evidence']);self.assertIn('unavailable',report['warnings'][0])
            with self.assertRaises(RetrievalError):build(service.index,[document()],service.provider,True)
            self.assertEqual(service.index.status()['index_version'],before)

    def test_source_version_change_during_external_query_rejects_old_results(self):
        from server.app.rag.service import KnowledgeService
        from server.app.common import ApiError
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            service=KnowledgeService(SimpleNamespace(repo=SimpleNamespace(directory=Path(folder))))
            class ChangedCloud:
                model='test';dimensions=2
                def status(self):return {'embedding_configured':True,'rerank_configured':False}
                def embed(self,texts):
                    service.index.publish([document()]);return [[1.,0.]]
            row=service.index.search('repairs')[0]
            service.index.save_vectors([row['chunk_id']],[[1.,0.]],'test',2)
            service.provider=ChangedCloud()
            with self.assertRaises(ApiError) as error:service.retrieve('repairs',True)
            self.assertEqual(error.exception.code,'knowledge_changed')

    def test_no_semantic_matches_do_not_claim_a_compatible_index_is_missing(self):
        from server.app.rag.service import KnowledgeService
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            service=KnowledgeService(SimpleNamespace(repo=SimpleNamespace(directory=Path(folder))))
            row=service.index.search('repairs')[0]
            service.index.save_vectors([row['chunk_id']],[[1.,0.]],'test',2)
            class EmptyMatchCloud:
                model='test';dimensions=2
                def status(self):return {'embedding_configured':True,'rerank_configured':False}
                def embed(self,texts):return [[-1.,0.]]
            service.provider=EmptyMatchCloud()
            report=service.retrieve('quantum banana astrophysics',True)
            self.assertEqual(report['evidence'],[])
            self.assertEqual(report['retrieval_methods'],['keywords','vectors'])
            self.assertEqual(report['warnings'],[])
