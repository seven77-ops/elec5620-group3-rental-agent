import asyncio
import json
from pathlib import Path
from threading import Event
from time import monotonic, sleep
import unittest
import httpx


class ProviderTests(unittest.TestCase):
    def test_public_summary_deadlines_are_bounded_and_do_not_change_private_default(self):
        from unittest.mock import patch
        from server.app.ai.provider import run_transport
        provider=self.provider(lambda r:httpx.Response(200,json={'choices':[{'message':{'content':'{}'}}]}))
        for context,expected in (({'task':'rag_answer'},30),
             ({'task':'rag_answer','transport_timeout_seconds':18},18),
             ({'task':'rag_grounded_summary','transport_timeout_seconds':15},15),
             ({'task':'rag_grounded_summary','transport_timeout_seconds':900},30),
             ({'task':'contract_extract','transport_timeout_seconds':900},12)):
            with patch('server.app.ai.provider.run_transport',wraps=run_transport) as run:
                provider.call(context);self.assertEqual(run.call_args.args[1],expected)

    def provider(self, handler=None, **changes):
        self.assertTrue(Path('server/app/ai/provider.py').exists(), 'AI provider has not been implemented')
        from server.app.ai.provider import ModelProvider
        env = {'RENTAL_AI_ENABLED': '1', 'RENTAL_AI_URL': 'https://provider.example/chat/completions',
               'RENTAL_AI_MODEL': 'test-model', 'RENTAL_AI_API_KEY': 'private-test-secret'}
        env.update(changes)
        return ModelProvider(env=env, transport=httpx.MockTransport(handler)) if handler else ModelProvider(env=env)

    def test_disabled_configuration_has_no_secret_or_endpoint(self):
        provider = self.provider(RENTAL_AI_ENABLED='0')
        self.assertFalse(provider.public_config()['configured'])
        self.assertNotIn('private-test-secret', json.dumps(provider.public_config()))
        self.assertNotIn('provider.example', json.dumps(provider.public_config()))
        with self.assertRaises(Exception) as error:
            provider.call({'task': 'contract_extract'})
        self.assertEqual(error.exception.code, 'ai_disabled')
        self.assertFalse(error.exception.call['attempted'])

    def test_http_url_rejected_without_call(self):
        calls = []
        provider = self.provider(lambda r: calls.append(r), RENTAL_AI_URL='http://provider.example/chat')
        self.assertFalse(provider.public_config()['configured'])
        with self.assertRaises(Exception) as error:
            provider.call({'task': 'contract_extract'})
        self.assertEqual(error.exception.code, 'ai_not_configured')
        self.assertEqual(calls, [])

    def test_real_http_shape_and_truthful_usage(self):
        def respond(request):
            self.assertEqual(request.headers['Authorization'], 'Bearer private-test-secret')
            body = json.loads(request.content)
            self.assertEqual(body['model'], 'test-model')
            self.assertIn('untrusted', body['messages'][0]['content'])
            return httpx.Response(200, headers={'x-request-id': 'provider-request-123'}, json={'id': 'completion-456', 'model': 'actual-model',
                'usage': {'prompt_tokens': 20, 'completion_tokens': 5, 'total_tokens': 25},
                'choices': [{'message': {'content': '{"fields": []}'}}]})
        data, call = self.provider(respond).call({'task': 'contract_extract', 'document': 'synthetic'})
        self.assertEqual(data, {'fields': []})
        self.assertTrue(call['attempted'])
        self.assertEqual(call['status'], 'succeeded')
        self.assertEqual(call['provider_request_id'], 'provider-request-123')
        self.assertEqual(call['provider_response_id'], 'completion-456')
        self.assertEqual(call['usage']['total_tokens'], 25)
        self.assertGreaterEqual(call['duration_ms'], 0)
        self.assertNotIn('private-test-secret', json.dumps(call))

    def test_assistant_temperature_is_moderate_and_extraction_remains_precise(self):
        sent=[]
        def respond(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200,json={'choices':[{'message':{'content':'{}'}}]})
        provider=self.provider(respond)
        provider.call({'task':'assistant_intent'})
        provider.call({'task':'contract_extract'})
        provider.call({'task':'assistant_commute_reply'})
        self.assertEqual([r['temperature'] for r in sent],[0.6,0,0])
        self.assertEqual(provider.public_config()['assistant_temperature'],0.6)
        provider=self.provider(respond,RENTAL_AI_ASSISTANT_TEMPERATURE='0.8')
        provider.call({'task':'assistant_intent'})
        self.assertEqual(sent[-1]['temperature'],0.8)
        for value in ('nan','infinity','bad','-1','3'):
            self.assertEqual(self.provider(respond,RENTAL_AI_ASSISTANT_TEMPERATURE=value).public_config()['assistant_temperature'],0.6)

    def test_redirect_is_not_followed(self):
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(302, headers={'location': 'https://elsewhere.example/secret'})
        with self.assertRaises(Exception) as error:
            self.provider(respond).call({'task': 'contract_extract'})
        self.assertEqual(error.exception.code, 'ai_http_error')
        self.assertEqual(len(calls), 1)

    def test_timeout_is_sanitized(self):
        def respond(request):
            raise httpx.ReadTimeout('private-test-secret provider.example raw contract', request=request)
        with self.assertRaises(Exception) as error:
            self.provider(respond).call({'task': 'contract_extract'})
        self.assertEqual(error.exception.code, 'ai_timeout')
        self.assertNotIn('private-test-secret', str(error.exception))
        self.assertNotIn('raw contract', str(error.exception))

    def test_total_deadline_stops_trickled_response_and_closes_stream(self):
        # Both interfaces let the regression exercise the old synchronous transport too.
        # Every chunk arrives well within the per-I/O timeout; the full body takes 3s.
        class DripStream(httpx.AsyncByteStream, httpx.SyncByteStream):
            def __init__(self):
                self.closed = Event()

            def __iter__(self):
                for _ in range(30):
                    sleep(.1)
                    yield b' '
                yield b'{"choices":[{"message":{"content":"{\\"fields\\":[]}"}}]}'

            async def __aiter__(self):
                for _ in range(30):
                    await asyncio.sleep(.1)
                    yield b' '
                yield b'{"choices":[{"message":{"content":"{\\"fields\\":[]}"}}]}'

            def close(self):
                self.closed.set()

            async def aclose(self):
                self.closed.set()

        stream = DripStream()
        provider = self.provider(lambda r: httpx.Response(200, stream=stream), RENTAL_AI_TIMEOUT_SECONDS='1')
        start = monotonic()
        with self.assertRaises(Exception) as error:
            provider.call({'task': 'contract_extract'})
        elapsed = monotonic() - start
        self.assertEqual(error.exception.code, 'ai_timeout')
        self.assertTrue(error.exception.call['attempted'])
        self.assertEqual(error.exception.call['status'], 'failed')
        self.assertLess(elapsed, 2)
        self.assertGreaterEqual(error.exception.call['duration_ms'], 900)
        self.assertTrue(stream.closed.wait(.5))
        self.assertNotIn('private-test-secret', str(error.exception))

    def test_response_id_does_not_invent_request_id(self):
        provider = self.provider(lambda r: httpx.Response(200, json={'id': 'completion-only',
            'choices': [{'message': {'content': '{"fields":[]}'}}]}))
        _, call = provider.call({'task': 'contract_extract'})
        self.assertEqual(call.get('provider_response_id'), 'completion-only')
        self.assertNotIn('provider_request_id', call)

    def test_total_deadline_does_not_join_slow_resolver_executor(self):
        from server.app.ai.provider import ProviderError
        resolved, cancelled, closed = Event(), Event(), Event()
        sent = []

        def resolve():
            sleep(2.3)
            resolved.set()

        class ResolverTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                try:
                    # asyncio's real DNS resolver also uses the default executor.
                    await asyncio.to_thread(resolve)
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
                sent.append(request)
                return httpx.Response(200, json={'choices': [{'message': {'content': '{"fields":[]}'}}]})

            async def aclose(self):
                closed.set()

        provider = self.provider(RENTAL_AI_TIMEOUT_SECONDS='1')
        provider.transport = ResolverTransport()
        start = monotonic()
        with self.assertRaises(ProviderError) as error:
            provider.call({'task': 'contract_extract'})
        elapsed = monotonic() - start
        self.assertEqual(error.exception.code, 'ai_timeout')
        self.assertTrue(error.exception.call['attempted'])
        self.assertEqual(error.exception.call['status'], 'failed')
        self.assertTrue(cancelled.wait(.5), 'request coroutine must be cancelled')
        self.assertTrue(closed.wait(.5), 'client transport must close on cancellation')
        self.assertTrue(resolved.wait(3), 'test resolver worker must finish')
        self.assertEqual(sent, [], 'a late DNS result must never resume transmission')
        self.assertLess(elapsed, 1.8, 'caller must not join the resolver executor')
        self.assertLess(error.exception.call['duration_ms'], 1800)

    def test_duplicate_nonfinite_and_oversized_responses_rejected(self):
        for content in ('{"fields":[],"fields":[]}', '{"score":1e999}', '{"score":NaN}'):
            with self.subTest(content=content):
                def respond(request):
                    return httpx.Response(200, json={'choices':[{'message':{'content':content}}]})
                with self.assertRaises(Exception) as error:
                    self.provider(respond).call({'task':'contract_extract'})
                self.assertEqual(error.exception.code, 'ai_invalid_response')
        with self.assertRaises(Exception) as error:
            self.provider(lambda r: httpx.Response(200, content=b'x' * 1_000_001)).call({'task':'contract_extract'})
        self.assertEqual(error.exception.code, 'ai_response_too_large')

    def test_timeout_is_bounded_and_usage_is_never_invented(self):
        provider = self.provider(lambda r: httpx.Response(200, json={'choices':[{'message':{'content':'{"fields":[]}'}}]}),
                                 RENTAL_AI_TIMEOUT_SECONDS='999')
        self.assertEqual(provider.public_config()['timeout_seconds'], 15)
        _, call = provider.call({'task':'contract_extract'})
        self.assertNotIn('usage',call)
        self.assertNotIn('provider_request_id',call)
        self.assertNotIn('provider_response_id',call)

    def test_lease_extraction_has_its_own_bounded_deadline(self):
        from unittest.mock import patch
        from server.app.ai.provider import run_transport
        provider = self.provider(lambda r: httpx.Response(200, json={'choices': [{'message': {'content': '{"fields":[]}'}}]}))
        with patch('server.app.ai.provider.run_transport', wraps=run_transport) as transport:
            provider.call({'task': 'lease_draft_extract'})
            self.assertEqual(transport.call_args.args[1], 45)
            provider.call({'task': 'assistant_intent'})
            self.assertEqual(transport.call_args.args[1], 12)
        self.assertEqual(self.provider(RENTAL_AI_LEASE_TIMEOUT_SECONDS='999').public_config()['lease_timeout_seconds'], 60)
        self.assertEqual(self.provider(RENTAL_AI_LEASE_TIMEOUT_SECONDS='20').public_config()['lease_timeout_seconds'], 20)
        for invalid in ('nan', 'infinity', 'bad'):
            self.assertEqual(self.provider(RENTAL_AI_LEASE_TIMEOUT_SECONDS=invalid).public_config()['lease_timeout_seconds'], 45)


if __name__ == '__main__':
    unittest.main()

class LocalEnvTests(unittest.TestCase):
    def test_whitelist_precedence_and_no_execution(self):
        import tempfile
        self.assertTrue(Path('scripts/local_ai_env.py').exists(), 'Local AI env loader is missing')
        from scripts.local_ai_env import load_ai_env
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env'
            path.write_text('RENTAL_AI_ENABLED=1\nRENTAL_AI_MODEL="model with space"\nRENTAL_AI_API_KEY=local-secret\nVITE_API_KEY=never-copy\nRENTAL_AI_URL="https://example.test/chat"\n')
            result=load_ai_env(path,{'RENTAL_AI_API_KEY':'existing-secret'})
        self.assertEqual(result['RENTAL_AI_API_KEY'],'existing-secret')
        self.assertEqual(result['RENTAL_AI_MODEL'],'model with space')
        self.assertNotIn('VITE_API_KEY',result)
