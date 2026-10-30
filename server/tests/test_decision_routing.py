"""Classification stays read-only; state, unknowns and shadow runs cannot authorize writes."""
from copy import deepcopy
import json
import tempfile
import threading
import sqlite3
from time import monotonic
import unittest
import httpx
from fastapi.testclient import TestClient

from server.app.main import create_app
from server.app.routing.jev import JevProvider
from server.app.routing.router import DecisionRouter
from server.app.repository import Repository
from server.tests.test_jev_provider import envelope
from server.tests.test_assistant_api import IntentProvider


class DecisionRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.repo=Repository(self.temp.name)

    def router(self, route='knowledge', mode='active', confidence=.95, handler=None):
        provider=JevProvider({'OPENROUTER_API_KEY':'test-only','RENTAL_JEV_MODE':mode},
            transport=httpx.MockTransport(handler or (lambda r:httpx.Response(200,json=envelope(route,confidence)))))
        router=DecisionRouter(provider,self.repo)
        self.addCleanup(router.close,True)
        return router

    def test_minimal_classification_state_does_not_copy_private_snapshots_or_transcripts(self):
        seen=[]
        router=self.router(handler=lambda r:(seen.append(json.loads(r.content)) or httpx.Response(200,json=envelope())))
        conversation={'dialogue_mode':'search','messages':[{'role':'assistant','intent':'search','content':'private contact',
            'listings':[{'address':'private contract address'}]}], 'private_contract':'private contact'}
        decision=router.prepare('How do I request repairs?',conversation,'audit-one')
        self.assertEqual(decision['direct_intent'],{'intent':'knowledge'})
        raw=json.dumps(seen)
        self.assertNotIn('private contact',raw);self.assertNotIn('private contract address',raw)

    def test_explicit_continuation_skips_both_decision_classification_and_route_changes(self):
        seen=[];router=self.router(handler=lambda r:seen.append(r))
        explicit={'intent':'collect_preferences','brief_patch':{'budget_period':'week'}}
        result=router.prepare('Weekly',{},'audit-state',explicit=explicit)
        self.assertEqual(result['direct_intent'],explicit);self.assertEqual(seen,[])

    def test_uncertain_distribution_and_unavailable_provider_use_existing_flow(self):
        self.assertIsNone(self.router(confidence=.2).prepare('help',{},'uncertain')['direct_intent'])
        result=self.router(handler=lambda r:httpx.Response(402,content=b'secret')).prepare('help',{},'error')
        self.assertIsNone(result['direct_intent']);self.assertEqual(result['source'],'ali')
        self.assertNotIn('secret',json.dumps(result))

    def test_close_probabilities_and_pending_tasks_do_not_force_a_route(self):
        body=envelope();probabilities={name:.01 for name in body['answers']['route']['probabilities']}
        probabilities.update(knowledge=.5,housing=.46);body['answers']['route']['probabilities']=probabilities
        result=self.router(handler=lambda r:httpx.Response(200,json=body)).prepare('help',{},'close')
        self.assertEqual(result['reason'],'uncertain')
        seen=[];router=self.router(handler=lambda r:seen.append(r))
        result=router.prepare('A long answer about the budget and room requirements that should stay in intake.',{},'pending',
                              pending={'task':'rental_preferences','fields':['budget_period']})
        self.assertEqual(result['reason'],'pending_task_context');self.assertEqual(seen,[])

    def test_shadow_capacity_is_bounded_and_skips_instead_of_queuing(self):
        release=threading.Event()
        async def blocked(request):
            import asyncio
            while not release.is_set():await asyncio.sleep(.01)
            return httpx.Response(200,json=envelope())
        router=self.router(mode='shadow',handler=blocked)
        try:
            self.assertEqual(router.prepare('one',{},'one')['reason'],'shadow_scheduled')
            self.assertEqual(router.prepare('two',{},'two')['reason'],'shadow_scheduled')
            self.assertEqual(router.prepare('three',{},'three')['reason'],'shadow_busy')
        finally:
            release.set();router.close(True)

    def test_shadow_audit_skips_a_busy_database_without_delaying_the_tenant(self):
        router=self.router(mode='shadow')
        writer=sqlite3.connect(self.repo.database,check_same_thread=False)
        writer.execute('BEGIN IMMEDIATE')
        timer=threading.Timer(.3,writer.rollback);timer.start()
        try:
            started=monotonic()
            result=router.prepare('Synthetic question',{},'busy-db')
            router.observe('busy-db',{'intent':'search'})
            elapsed=monotonic()-started
            self.assertEqual(result['source'],'ali')
            self.assertLess(elapsed,.15,'Optional routing diagnostics must not wait for the web writer')
        finally:
            timer.join();writer.close();router.close(True)

    def test_active_business_route_only_narrows_extraction_and_mixed_requests_clarify(self):
        result=self.router('aftercare').prepare('Prepare a repair email',{},'aftercare')
        self.assertIsNone(result['direct_intent'])
        self.assertIn('living_services',result['allowed_intents'])
        self.assertNotIn('select',result['allowed_intents'])
        mixed=self.router('mixed').prepare('Compare listings then review my lease',{},'mixed')
        self.assertEqual(mixed['direct_intent']['clarification_reason'],'multiple_tasks')

    def test_shadow_does_not_wait_or_change_the_real_route_and_persists_only_metadata(self):
        started=threading.Event();release=threading.Event()
        async def blocked(request):
            started.set()
            import asyncio
            while not release.is_set():await asyncio.sleep(.01)
            return httpx.Response(200,json=envelope())
        router=self.router(mode='shadow',handler=blocked)
        result=router.prepare('Synthetic question',{},'shadow-one')
        self.assertIsNone(result['direct_intent']);self.assertEqual(result['source'],'ali')
        self.assertTrue(started.wait(1));router.observe('shadow-one',{'intent':'search'})
        release.set();router.close(True)
        with self.repo.transaction() as db:record=self.repo.get(db,'routing_audit','shadow-one')
        self.assertEqual(record['observed_intent'],'search');self.assertEqual(record['decision']['route'],'knowledge')
        self.assertNotIn('Synthetic question',json.dumps(record))


class RoutedAssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ai=IntentProvider();self.calls=[];self.route='knowledge';self.status=200
        def transport(request):
            self.calls.append(json.loads(request.content))
            return httpx.Response(self.status,json=envelope(self.route))
        self.jev=JevProvider({'OPENROUTER_API_KEY':'test-only','RENTAL_JEV_MODE':'active'},transport=httpx.MockTransport(transport))
        self.app=create_app(runtime_dir=self.temp.name,ai_provider=self.ai,decision_provider=self.jev)
        self.addCleanup(self.app.state.decision_router.close,True)
        self.client=TestClient(self.app)
        self.case=self.client.post('/api/v1/cases',json={}).json()
        self.base=f"/api/v1/cases/{self.case['case_id']}/assistant/conversations"
        self.conversation=self.client.post(self.base,json={}).json()

    def send(self,message='How do I request repairs?',key='turn-one',consent=True):
        return self.client.post(self.base+'/'+self.conversation['conversation_id']+'/messages',json={
            'request_id':key,'expected_revision':self.conversation['revision'],'message':message,'allow_external_ai':consent})

    def test_knowledge_routes_to_cited_retrieval_without_an_extra_alibaba_intent_call(self):
        result=self.send();self.assertEqual(result.status_code,200,result.text)
        answer=result.json()['messages'][-1]
        self.assertEqual(answer['intent'],'knowledge');self.assertTrue(answer['knowledge']['citations'])
        self.assertNotIn('assistant_intent',[c['task'] for c in self.ai.inputs])
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)
        self.assertEqual(self.send().json(),result.json());self.assertEqual(len(self.calls),1)

    def test_business_route_keeps_validation_and_falls_back_when_extraction_disagrees(self):
        self.route='aftercare';self.ai.result={'intent':'search','filters':{'suburb':'Rhodes'}}
        response=self.send('Show Rhodes listings');self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(len(self.ai.inputs),2)
        self.assertLess(len(self.ai.inputs[0]['response_schema']['oneOf']),len(self.ai.inputs[1]['response_schema']['oneOf']))
        self.assertEqual(response.json()['messages'][-1]['intent'],'search')

    def test_decision_failure_falls_back_and_no_consent_sends_nothing(self):
        self.assertEqual(self.send(consent=False).status_code,422);self.assertEqual(self.calls,[])
        self.status=429
        result=self.send('Show Rhodes listings');self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['messages'][-1]['intent'],'search')

    def test_mixed_business_request_asks_for_order_without_creating_a_write(self):
        self.route='mixed';result=self.send('Compare listings then review my lease')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['messages'][-1]['intent'],'clarify')
        self.assertIn('first',result.json()['messages'][-1]['content']);self.assertEqual(self.ai.inputs,[])
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)

    def test_mixed_task_ordering_is_not_overwritten_by_commute_or_dissatisfaction_copy(self):
        self.route='mixed'
        for index,message in enumerate(('Compare commute options for these listings, then review my lease.',
                                        '这些房源都不喜欢，先换房源再处理合同。')):
            response=self.send(message,key='mixed-copy-'+str(index))
            self.assertEqual(response.status_code,200,response.text)
            answer=response.json()['messages'][-1]
            self.assertIn('handle first',answer['content'])
            self.assertEqual(answer['actions'],[])
            self.conversation=response.json()


if __name__=='__main__':unittest.main()
