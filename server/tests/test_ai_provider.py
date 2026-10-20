import json
from pathlib import Path
import unittest
import httpx


class ProviderTests(unittest.TestCase):
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
            return httpx.Response(200, json={'id': 'provider-request-123', 'model': 'actual-model',
                'usage': {'prompt_tokens': 20, 'completion_tokens': 5, 'total_tokens': 25},
                'choices': [{'message': {'content': '{"fields": []}'}}]})
        data, call = self.provider(respond).call({'task': 'contract_extract', 'document': 'synthetic'})
        self.assertEqual(data, {'fields': []})
        self.assertTrue(call['attempted'])
        self.assertEqual(call['status'], 'succeeded')
        self.assertEqual(call['provider_request_id'], 'provider-request-123')
        self.assertEqual(call['usage']['total_tokens'], 25)
        self.assertGreaterEqual(call['duration_ms'], 0)
        self.assertNotIn('private-test-secret', json.dumps(call))

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
