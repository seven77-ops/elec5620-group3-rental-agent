"""Separate Decisions protocol, strict distributions and bounded secret-free failures."""
import asyncio
import json
import unittest
import httpx

from server.app.routing.jev import JevProvider, JevError, ROUTES


def envelope(route='knowledge', confidence=.95):
    probabilities={name:(.95 if name==route else .01) for name in ROUTES}
    return {'model':'typesafe/jev-1.14-20261001','answers':{'route':{
        'type':'choice','choice':route,'confidence':confidence,'probabilities':probabilities}},
        'usage':{'cost':.00001,'input_tokens':30,'output_tokens':4}}


class JevProviderTests(unittest.TestCase):
    def provider(self, handler, **env):
        return JevProvider({'OPENROUTER_API_KEY':'jev-private-key','RENTAL_JEV_MODE':'active',**env},
                           transport=httpx.MockTransport(handler))

    def test_decisions_use_a_separate_key_and_do_not_parse_chat_envelopes(self):
        seen=[]
        def send(request):
            seen.append(json.loads(request.content))
            self.assertEqual(str(request.url),'https://openrouter.ai/api/alpha/decisions')
            self.assertEqual(request.headers['Authorization'],'Bearer jev-private-key')
            return httpx.Response(200,json=envelope())
        client=self.provider(send,RENTAL_AI_API_KEY='ali-private-key')
        result=client.classify({'message':'How do I request repairs?'})
        self.assertEqual(result['route'],'knowledge')
        self.assertEqual(seen[0]['model'],'typesafe/jev-1.14')
        self.assertEqual(seen[0]['questions']['route']['type'],'choice')
        self.assertEqual(result['usage']['cost'],.00001)
        self.assertNotIn('private-key',json.dumps(client.public_config()))
        self.assertNotIn('private-key',json.dumps(result))
        with self.assertRaises(JevError):
            self.provider(lambda r:httpx.Response(200,json={'choices':[{'message':{'content':'knowledge'}}]})).classify({})

    def test_missing_key_never_reuses_the_alibaba_key(self):
        client=JevProvider({'RENTAL_AI_API_KEY':'ali-secret','RENTAL_JEV_MODE':'active'})
        self.assertFalse(client.public_config()['configured'])
        with self.assertRaises(JevError) as error:client.classify({})
        self.assertEqual(error.exception.code,'jev_not_configured')

    def test_invalid_or_nonfinite_choices_and_distributions_are_rejected(self):
        bad=[]
        for field,value in [('choice','delete_all'),('confidence',True),('confidence',float('nan')),
                            ('probabilities',{'knowledge':1}),('type','noul')]:
            body=envelope();body['answers']['route'][field]=value;bad.append(body)
        body=envelope();body['answers']['route']['probabilities']['housing']=-.01;bad.append(body)
        body=envelope();body['answers']['route']['choice']='housing';bad.append(body)
        for body in bad:
            with self.subTest(body=repr(body)),self.assertRaises(JevError):
                self.provider(lambda r:httpx.Response(200,content=json.dumps(body).encode())).classify({})

    def test_http_error_body_is_not_exposed_and_redirects_are_not_followed(self):
        for status in (302,401,402,429,500):
            seen=[]
            def send(request):
                seen.append(request)
                return httpx.Response(status,headers={'Location':'https://other.example'},content=b'upstream secret')
            with self.assertRaises(JevError) as error:self.provider(send).classify({})
            self.assertEqual(len(seen),1)
            self.assertNotIn('secret',str(error.exception))

    def test_total_deadline_and_response_size_are_bounded(self):
        async def delayed(request):
            await asyncio.sleep(.2)
            return httpx.Response(200,json=envelope())
        with self.assertRaises(JevError) as error:
            self.provider(delayed,RENTAL_JEV_TIMEOUT_SECONDS='0.05').classify({})
        self.assertEqual(error.exception.code,'jev_timeout')
        with self.assertRaises(JevError):
            self.provider(lambda r:httpx.Response(200,content=b' '*70000)).classify({})

    def test_configuration_defaults_to_off_and_invalid_modes_fail_closed(self):
        self.assertEqual(JevProvider({}).public_config()['mode'],'off')
        self.assertEqual(JevProvider({'RENTAL_JEV_MODE':'unexpected'}).public_config()['mode'],'off')


if __name__=='__main__':unittest.main()
