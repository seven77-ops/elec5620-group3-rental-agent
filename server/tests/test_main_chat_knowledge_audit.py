"""Read-only main-chat public knowledge audit; every remote boundary is mocked."""
from copy import deepcopy
import tempfile
import json
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
# The production module constructs its default app on import. Keep that app in
# an isolated directory too, even when this audit is invoked on its own.
_IMPORT_RUNTIME=tempfile.TemporaryDirectory(prefix='main-chat-knowledge-import-')
with patch.dict('os.environ',{'RENTAL_RUNTIME_DIR':_IMPORT_RUNTIME.name}):
    from server.app.main import create_app
from server.app.routing.jev import JevProvider
from server.tests import test_assistant_api as chat
from server.tests import test_contract_rag as contracts
from server.tests.test_decision_routing import envelope
from server.tests.test_rag import document

QUESTION='How do I request repairs?'
UNKNOWN='Your rent ledger and payment dates are not supplied.'


class LocalRetrieval:
    model='audit-local-only'
    dimensions=64
    def status(self):return {'embedding_configured':False,'rerank_configured':False}
    def embed(self,*args,**kwargs):raise AssertionError('The audit must not call external embeddings')
    def rerank(self,*args,**kwargs):raise AssertionError('The audit must not call external reranking')


def configure(test,app,provider):
    test.provider=provider;test.route='knowledge';test.classifications=[];test.abstain=False
    test.ctx=next(r.endpoint.__self__.ctx for r in app.routes if getattr(r,'path','').endswith('/rag/status'))
    test.ctx.knowledge.provider=LocalRetrieval()
    test.ctx.knowledge.index.publish([document()])
    def classify(request):
        test.classifications.append(json.loads(request.content))
        return httpx.Response(200,json=envelope(test.route))
    test.jev=JevProvider({'OPENROUTER_API_KEY':'synthetic-audit-only','RENTAL_JEV_MODE':'active'},transport=httpx.MockTransport(classify))
    app.state.decision_router.provider=test.jev
    test.addCleanup(app.state.decision_router.close,True)
    def grounded_reply():
        context=provider.inputs[-1];task=context['task']
        if task=='rag_answer':
            if test.abstain:
                provider.by_task[task]={'claims':[],'unknowns':[UNKNOWN]};return
            row=context['evidence'][0];quote=row['passages'][0]
            provider.by_task[task]={'claims':[{'text':quote['text'],'evidence_id':row['evidence_id'],'quote_id':quote['quote_id']}],'unknowns':[]}
        elif task=='rag_grounded_summary':
            row=context['evidence'][0];quote=row['passages'][0]
            provider.by_task[task]={'claims':[{'text':quote['text'],'evidence_id':row['evidence_id'],'quote_ids':[quote['quote_id']],
                'grounded':True,'conditions_preserved':True}],'unknowns':[]}
        elif task=='rag_summary_check':
            provider.by_task[task]={'texts':[r['claim'] for r in context['checks']],
                'supported':[True]*len(context['checks']),'original_supported':[True]*len(context['checks'])}
    provider.on_call=grounded_reply


class MainChatPublicKnowledgeAudit(unittest.TestCase):
    setUpBase=chat.AssistantTests.setUp
    conversation=chat.AssistantTests.conversation
    send=chat.AssistantTests.send

    def setUp(self):
        self.setUpBase();self.app=self.client.app
        configure(self,self.app,self.provider)

    def test_active_jev_knowledge_uses_real_answer_pipeline_and_citations_survive_restart(self):
        c=self.conversation();self.provider.result={'intent':'knowledge'}
        with patch.object(self.ctx.knowledge,'answer',wraps=self.ctx.knowledge.answer) as answer:
            r=self.send(c,'public-answer',QUESTION)
        self.assertEqual(r.status_code,200,r.text[:500]);value=r.json();message=value['messages'][-1]
        answer.assert_called_once_with(QUESTION,True,'en')
        self.assertEqual(message['intent'],'knowledge');self.assertEqual(message['knowledge']['scope'],'public')
        self.assertEqual(message['knowledge']['status'],'answered');self.assertTrue(message['knowledge']['citations'])
        self.assertEqual(message['content'],message['knowledge']['answer'])
        self.assertEqual(message['listings'],[]);self.assertEqual(message['actions'],[])
        self.assertNotIn('assistant_intent',[entry['task'] for entry in self.provider.inputs])
        self.assertEqual(message['routing']['source'],'jev');self.assertEqual(len(self.classifications),1)
        path=self.base+'/conversations/'+c['conversation_id']
        self.assertEqual(self.client.get(path).json(),value)
        reopened=create_app(runtime_dir=self.temp.name,ai_provider=self.provider,decision_provider=self.jev)
        self.addCleanup(reopened.state.decision_router.close,True)
        self.assertEqual(TestClient(reopened).get(path).json(),value)
        self.assertEqual(self.send(c,'public-answer',QUESTION).json(),value)
        self.assertEqual(len(self.classifications),1)
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)

    def test_mid_intake_knowledge_preserves_working_housing_context_and_saved_profile(self):
        root='/api/v1/cases/'+self.case['case_id']
        profile={**self.case['draft']['profile'],'budget':{'currency':'AUD','period':'week','scope':'whole_property','maximum':900},
                 'housing_preferences':{'suburb':'Rhodes','min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':0},'occupants':1}
        drafted=self.client.post(root+'/profile-drafts',json={'expected_revision':self.case['draft']['revision'],'profile':profile})
        self.assertEqual(drafted.status_code,200,drafted.text[:500]);value=drafted.json()
        confirmed=self.client.post(root+'/profile-confirmations',json={'draft_revision':value['draft']['revision'],
            'fingerprint':value['draft']['fingerprint'],'review_token':value['agent1']['review_token']})
        self.assertEqual(confirmed.status_code,200,confirmed.text[:500]);self.case=confirmed.json()
        self.assertEqual(self.case['confirmations'][-1]['profile']['budget']['maximum'],900)
        self.route='housing';self.provider.result={'intent':'search','filters':{'suburb':'Rhodes','max_weekly_rent':900,'min_bedrooms':2}}
        r=self.send(self.conversation(),'preview','Preview Rhodes homes up to AUD 900 per week.');self.assertEqual(r.status_code,200)
        self.provider.result={'intent':'collect_preferences','brief_patch':{'suburb':'Rhodes','budget_amount':900,'budget_period':'week','budget_scope':'unknown'}}
        r=self.send(r.json(),'intake','Help me record my rental requirements.');self.assertEqual(r.status_code,200)
        c=r.json();state={k:deepcopy(c[k]) for k in ('rental_brief','last_search_filters','dialogue_mode')}
        self.assertEqual(state['dialogue_mode'],'collect_preferences');self.assertTrue(state['last_search_filters'])
        self.route='knowledge';self.provider.result={'intent':'knowledge'}
        r=self.send(c,'question-during-intake',QUESTION);self.assertEqual(r.status_code,200,r.text[:500])
        updated=r.json();message=updated['messages'][-1]
        self.assertTrue(message['knowledge']['citations']);self.assertEqual(message['intent'],'knowledge')
        self.assertEqual({k:updated[k] for k in state},state)
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)
        self.assertEqual(self.client.get(self.base+'/conversations/'+c['conversation_id']).json(),updated)
        for context in self.provider.inputs:
            if context['task'].startswith('rag_'):
                self.assertNotIn('rental_brief',context);self.assertNotIn('draft_profile',context);self.assertNotIn('last_search_filters',context)

    def test_missing_personal_facts_remain_unknown_in_chat_and_after_reload(self):
        self.abstain=True;self.provider.result={'intent':'knowledge'};c=self.conversation()
        r=self.send(c,'unknown-personal-debt','What is my exact rent debt for these repairs?')
        self.assertEqual(r.status_code,200,r.text[:500]);message=r.json()['messages'][-1]
        self.assertEqual(message['knowledge']['status'],'insufficient_evidence')
        self.assertEqual(message['knowledge']['unknowns'],[UNKNOWN]);self.assertEqual(message['knowledge']['claims'],[])
        restored=self.client.get(self.base+'/conversations/'+c['conversation_id']).json()
        self.assertEqual(restored['messages'][-1]['knowledge']['unknowns'],[UNKNOWN])
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)

    def test_chat_consent_guard_precedes_jev_retrieval_and_model_calls(self):
        c=self.conversation()
        with patch.object(self.ctx.knowledge,'answer',wraps=self.ctx.knowledge.answer) as answer:
            r=self.send(c,'no-consent',QUESTION,allow_external_ai=False)
        self.assertEqual(r.status_code,422);answer.assert_not_called()
        self.assertEqual(self.classifications,[]);self.assertEqual(self.provider.inputs,[])
        self.assertEqual(self.client.get(self.base+'/conversations/'+c['conversation_id']).json(),c)
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)


class MainChatPrivateScopeAudit(unittest.TestCase):
    status=contracts.ContractRagTests.status
    enable=contracts.ContractRagTests.enable

    def setUp(self):
        contracts.ContractRagTests.setUp(self)
        configure(self,self.app,self.p)
        self.route='contract';self.p.result={'intent':'contract'}

    def send(self,c,key,question):
        return self.client.post(self.root+'/assistant/conversations/'+c['conversation_id']+'/messages',json={
            'request_id':key,'expected_revision':c['revision'],'message':question,'allow_external_ai':True})

    def conversation(self):
        return self.client.post(self.root+'/assistant/conversations',json={}).json()

    def test_upload_processing_consent_does_not_implicitly_enable_private_chat_search(self):
        before=self.client.get(self.root).json();self.assertEqual(self.status()['status'],'not_enabled')
        with patch.object(self.ctx.knowledge,'answer',wraps=self.ctx.knowledge.answer) as public:
            r=self.send(self.conversation(),'private-without-search','What does my uploaded contract say about cleaning?')
        self.assertEqual(r.status_code,200,r.text[:500]);message=r.json()['messages'][-1]
        self.assertEqual(message['intent'],'contract');self.assertNotIn('knowledge',message)
        self.assertIn('separately enable contract search',message['content']);public.assert_not_called()
        self.assertEqual(self.status()['status'],'not_enabled')
        self.assertNotIn('rag_answer',[c['task'] for c in self.p.inputs])
        self.assertEqual(self.client.get(self.root).json(),before)

    def test_private_search_stays_case_scoped_and_public_followup_cannot_borrow_clauses(self):
        enabled=self.enable(external=False);self.assertEqual(enabled.status_code,200,enabled.text[:500])
        before=self.client.get(self.root).json()
        r=self.send(self.conversation(),'private-authorized','What does my uploaded contract say about cleaning?')
        self.assertEqual(r.status_code,200,r.text[:500]);c=r.json();knowledge=c['messages'][-1]['knowledge']
        self.assertEqual(knowledge['scope'],'contract');self.assertEqual(knowledge['private_binding']['case_id'],self.case['case_id'])
        self.assertTrue(any(item['source_type']=='user_contract' for item in knowledge['citations']))
        self.assertNotIn('rag_answer',[entry['task'] for entry in self.p.inputs])
        self.route='knowledge';self.p.result={'intent':'knowledge'}
        r=self.send(c,'public-after-contract',QUESTION);self.assertEqual(r.status_code,200,r.text[:500])
        public=r.json()['messages'][-1]['knowledge']
        self.assertEqual(public['scope'],'public');self.assertNotIn('private_binding',public)
        self.assertTrue(public['citations']);self.assertTrue(all(c['source_type']!='user_contract' for c in public['citations']))
        for context in self.p.inputs:
            if context['task'].startswith('rag_'):
                self.assertTrue(all(row['source_type']!='user_contract' for row in context.get('evidence',[])))
        self.assertEqual(self.client.get(self.root).json(),before)
