"""Synthetic-only regressions for private-contract revocation boundaries.

Run with RENTAL_RUNTIME_DIR pointing at a temporary directory so importing the
application's module-level demo app also stays isolated. All model and retrieval
transports below are in-memory doubles.
"""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from server.tests import test_contract_rag as fixtures


QUESTION = 'What does my contract say about cleaning?'
PRIVATE_TEXT = 'The tenant must leave the premises reasonably clean, except for fair wear and tear.'


class MemoryRetrieval:
    model = 'synthetic-contract-vectors'
    dimensions = 64

    def __init__(self, semantic=False, rerank=False):
        self.semantic = semantic
        self.ranking = rerank
        self.embeds = []
        self.reranks = []
        self.on_embed = None

    def status(self):
        return {'embedding_configured': self.semantic, 'rerank_configured': self.ranking}

    def embed(self, texts, *, timeout=None):
        self.embeds.append(deepcopy(texts))
        if self.on_embed:
            self.on_embed()
        return [[1.0] + [0.0] * (self.dimensions - 1) for _ in texts]

    def rerank(self, question, documents):
        self.reranks.append(deepcopy(documents))
        return list(range(len(documents)))


class ContractRagSecurityTests(unittest.TestCase):
    # Reuse fixture construction without inheriting its five ordinary tests.
    status = fixtures.ContractRagTests.status
    enable = fixtures.ContractRagTests.enable
    search = fixtures.ContractRagTests.search

    def setUp(self):
        fixtures.ContractRagTests.setUp(self)
        self.service = next(
            route.endpoint.__self__ for route in self.app.routes
            if getattr(route, 'path', '').endswith('/rag/contracts/{review_id}/revoke')
        )
        self.ctx = self.service.ctx
        self.retrieval = MemoryRetrieval()
        self.ctx.knowledge.provider = self.retrieval
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def body(self, external=True):
        return {'question': QUESTION, 'allow_external_ai': external,
                'context_token': self.status()['context_token']}

    def revoke(self):
        return self.service.revoke(self.case['case_id'], self.rid, {})

    def send(self, conversation, request_id, text=QUESTION):
        return self.client.post(
            self.root + '/assistant/conversations/' + conversation['conversation_id'] + '/messages',
            json={'request_id': request_id, 'expected_revision': conversation['revision'],
                  'message': text, 'allow_external_ai': True},
        )

    def seed_private_history(self):
        self.assertEqual(self.enable(external=True).status_code, 200)
        self.p.result = {'intent': 'contract'}

        def answer_from_supplied_passage():
            context = self.p.inputs[-1]
            if context['task'] != 'rag_answer':
                return
            row = next(row for row in context['evidence']
                       if row['source_type'] == 'user_contract'
                       and any(PRIVATE_TEXT in item['text'] for item in row['passages']))
            passage = next(item for item in row['passages'] if PRIVATE_TEXT in item['text'])
            self.p.by_task['rag_answer'] = {
                'claims': [{'text': PRIVATE_TEXT, 'evidence_id': row['evidence_id'],
                            'quote_id': passage['quote_id']}], 'unknowns': [],
            }

        self.p.on_call = answer_from_supplied_passage
        created = self.client.post(self.root + '/assistant/conversations', json={}).json()
        response = self.send(created, 'private-history')
        self.assertEqual(response.status_code, 200, response.text)
        conversation = response.json()
        self.assertIn(PRIVATE_TEXT, conversation['messages'][-1]['content'])
        self.p.inputs.clear()
        self.p.on_call = None
        self.p.result = {'intent': 'other'}
        return conversation

    def assert_history_redacted(self, contexts):
        intent_calls = [context for context in contexts if context['task'] == 'assistant_intent']
        self.assertTrue(intent_calls, 'The regression must exercise a new external intent call.')
        for context in intent_calls:
            self.assertNotIn(PRIVATE_TEXT, str(context['history']))

    def test_cleanup_failure_still_commits_revocation(self):
        self.assertEqual(self.enable().status_code, 200)
        hit = self.search().json()['evidence'][0]
        with patch('server.app.rag.contracts.shutil.rmtree', side_effect=PermissionError('synthetic failure')):
            self.client.post(self.base + '/revoke', json={})
        self.assertEqual(self.status()['status'], 'revoked')
        self.assertEqual(self.search().status_code, 403)
        self.assertEqual(self.client.get(self.base + '/sources/' + hit['chunk_id']).status_code, 403)

    def test_revocation_before_chat_commit_does_not_persist_private_citations(self):
        self.assertEqual(self.enable().status_code, 200)
        self.p.result = {'intent': 'contract'}
        original = self.service.chat_answer

        def finish_then_revoke(case_id, question):
            answer = original(case_id, question)
            self.assertTrue(answer['knowledge']['citations'])
            self.revoke()
            return answer

        conversation = self.client.post(self.root + '/assistant/conversations', json={}).json()
        with patch.object(self.service, 'chat_answer', side_effect=finish_then_revoke):
            response = self.send(conversation, 'revoke-before-commit')
        self.assertIn(response.status_code, (200, 403, 409), response.text)
        with self.ctx.repo.transaction() as db:
            saved = self.ctx.repo.get(db, 'assistant_conversation', conversation['conversation_id'])
            receipt = self.ctx.repo.get(db, 'assistant_turn_receipt', self.case['case_id'] + ':revoke-before-commit')
        for value in (saved, receipt.get('result', {})):
            for entry in value.get('messages', []):
                self.assertFalse(entry.get('knowledge', {}).get('citations'))
                self.assertNotIn(PRIVATE_TEXT, entry.get('content', ''))

    def test_same_version_source_change_redacts_private_model_history(self):
        conversation = self.seed_private_history()
        with self.ctx.repo.transaction() as db:
            saved = self.ctx.repo.get(db, 'review', self.rid)
            saved['review']['data_limitations'].append('Synthetic changed source binding')
            self.ctx.repo.put(db, 'review', self.rid, saved)
        self.send(conversation, 'changed-history', 'Please continue helping me.')
        self.assert_history_redacted(self.p.inputs)

    def test_revocation_during_routing_redacts_private_model_history(self):
        conversation = self.seed_private_history()
        original = self.ctx.decision_router.prepare

        def prepare_then_revoke(*args, **kwargs):
            result = original(*args, **kwargs)
            self.revoke()
            return result

        with patch.object(self.ctx.decision_router, 'prepare', side_effect=prepare_then_revoke):
            self.send(conversation, 'routing-revoke', 'Please continue helping me.')
        self.assert_history_redacted(self.p.inputs)

    def test_revocation_during_first_intent_call_redacts_retry_history(self):
        conversation = self.seed_private_history()
        count = 0

        def revoke_on_first_call():
            nonlocal count
            if self.p.inputs[-1]['task'] != 'assistant_intent':
                return
            count += 1
            if count == 1:
                self.revoke()
                self.p.result = {'intent': 'invalid-synthetic-intent'}
            else:
                self.p.result = {'intent': 'other'}

        self.p.on_call = revoke_on_first_call
        self.send(conversation, 'retry-revoke', 'Please continue helping me.')
        intent_calls = [context for context in self.p.inputs if context['task'] == 'assistant_intent']
        self.assertEqual(len(intent_calls), 2)
        self.assert_history_redacted(intent_calls[1:])

    def test_revocation_during_public_retrieval_prevents_private_generation(self):
        self.assertEqual(self.enable(external=True).status_code, 200)
        original = self.ctx.knowledge.retrieve

        def retrieve_then_revoke(*args, **kwargs):
            report = original(*args, **kwargs)
            self.revoke()
            return report

        with patch.object(self.ctx.knowledge, 'retrieve', side_effect=retrieve_then_revoke):
            response = self.client.post(self.base + '/answers', json=self.body())
        self.assertIn(response.status_code, (403, 409), response.text)
        self.assertFalse([context for context in self.p.inputs if context['task'] == 'rag_answer'])

    def test_revocation_during_query_embedding_prevents_private_reranking(self):
        self.retrieval.semantic = True
        self.retrieval.ranking = True
        self.assertEqual(self.enable(external=True).status_code, 200)
        self.retrieval.embeds.clear()
        self.retrieval.on_embed = self.revoke
        # Retain the file to model delayed cleanup: permission must be fenced
        # independently of whether the old readable bytes still exist on disk.
        with patch('server.app.rag.contracts.shutil.rmtree', return_value=None):
            response = self.client.post(self.base + '/answers', json=self.body())
        self.assertIn(response.status_code, (403, 409), response.text)
        self.assertTrue(self.retrieval.embeds)
        self.assertFalse(self.retrieval.reranks)
        self.assertFalse([context for context in self.p.inputs if context['task'] == 'rag_answer'])

    def test_read_after_grant_revocation_does_not_recreate_deleted_index(self):
        self.assertEqual(self.enable().status_code, 200)
        original = self.service._query

        def query_then_revoke(*args, **kwargs):
            authorized = original(*args, **kwargs)
            self.revoke()
            return authorized

        with patch.object(self.service, '_query', side_effect=query_then_revoke):
            response = self.client.post(self.base + '/search', json=self.body(external=False))
        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(list((Path(self.tmp.name) / 'rag-private').rglob('*.sqlite3')))

    def test_abandoned_pending_index_request_can_be_retried(self):
        status = self.status()
        body = {'request_id': 'abandoned', 'context_token': status['context_token'],
                'expected_version': self.review['version'], 'confirmed': True, 'allow_external_ai': False}
        key = self.case['case_id'] + ':' + self.rid + ':abandoned'
        with self.ctx.repo.transaction() as db:
            self.ctx.repo.put(db, 'contract_rag_receipt', key,
                              {'input': body, 'status': 'pending', 'grant_id': 'index-abandoned',
                               'started_at': 0, 'created_at': '2000-01-01T00:00:00+00:00'})
        response = self.client.post(self.base + '/index', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'ready')
