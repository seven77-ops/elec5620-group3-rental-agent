"""Shared chat and page records, with explicit reviewed proposals and real directories."""
import tempfile
import unittest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.tests.test_assistant_api import IntentProvider


class LivingChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.provider = IntentProvider()
        self.client = TestClient(create_app(runtime_dir=self.temp.name, ai_provider=self.provider))
        self.case = self.client.post('/api/v1/cases', json={}).json()
        self.root = '/api/v1/cases/' + self.case['case_id']
        self.chat = self.client.post(self.root + '/assistant/conversations', json={}).json()
        self.path = self.root + '/assistant/conversations/' + self.chat['conversation_id']

    def send(self, intent, message):
        self.provider.result = intent
        r = self.client.post(self.path + '/messages', json={
            'request_id': 'turn-' + str(self.chat['revision']), 'expected_revision': self.chat['revision'],
            'message': message, 'allow_external_ai': True})
        self.assertEqual(r.status_code, 200, r.text)
        self.chat = r.json()
        return self.chat['messages'][-1]

    def test_chat_utility_choice_needs_confirmation_and_page_reads_the_same_profile(self):
        answer = self.send({'intent':'living_services','topic':'utilities','service_action':'update_profile',
                            'profile_patch':{'utilities':{'electricity':'agl','internet':'tpg'}}},
                           '我的电是 AGL，网络用 TPG，帮我记下来')
        self.assertEqual(self.client.get(self.root + '/living-services').json()['version'], 0)
        action = next(a for a in answer['actions'] if a['type']=='apply_living_services')
        self.assertIn('AGL', '\n'.join(action['summary']))
        body = {'request_id':'apply', 'expected_version':action['expected_version'], 'confirmed':True}
        endpoint = self.root + '/living-services/proposals/' + action['proposal_id'] + '/apply'
        saved = self.client.post(endpoint,json=body)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(self.client.post(endpoint,json=body).json(),saved.json())
        profile = self.client.get(self.root + '/living-services').json()['profile']
        self.assertEqual(profile['utilities']['electricity'],'agl')
        self.assertEqual(profile['utilities']['internet'],'tpg')
        follow = self.send({'intent':'living_services','topic':'utilities','service_action':'view'},'我现在用哪家电力和网络？')
        self.assertIn('AGL',follow['content']); self.assertIn('TPG',follow['content'])
        self.assertEqual(self.client.get(self.root).json(),self.case)

    def test_chat_repair_keeps_user_facts_and_drafts_email_only_after_confirmation(self):
        before = self.client.get(self.root + '/living-services').json()
        values = {**before['profile'],'address':'1 Example Street','agent_email':'agent@example.com'}
        self.assertEqual(self.client.post(self.root + '/living-services/profile',json={
            'request_id':'profile','expected_version':0,'confirmed':True,'values':values}).status_code,200)
        answer = self.send({'intent':'living_services','topic':'repairs','service_action':'report_repair',
                            'repair':{'title':'厨房漏水','description':'厨房水槽下面一直漏水','location':'Kitchen','priority':'normal'}},
                           '厨房水槽下面一直漏水，帮我写封报修邮件')
        self.assertEqual(self.client.get(self.root + '/living-services').json()['repairs'],[])
        action = next(a for a in answer['actions'] if a['type']=='apply_living_services')
        r = self.client.post(self.root + '/living-services/proposals/' + action['proposal_id'] + '/apply',json={
            'request_id':'repair-confirm','expected_version':action['expected_version'],'confirmed':True})
        self.assertEqual(r.status_code,200,r.text)
        repair = r.json()['repairs'][0]
        self.assertEqual(repair['description'],'厨房水槽下面一直漏水')
        self.assertIn('Water is continuously leaking beneath the kitchen sink.',repair['email']['body'])
        self.assertEqual(repair['email']['to'],'agent@example.com')
        self.assertEqual(repair['email']['delivery_status'],'prepared_not_sent')

    def test_recommendations_use_real_catalogue_and_do_not_select_suppliers(self):
        for topic, category in [('moving','removalist'),('cleaning','cleaner')]:
            answer = self.send({'intent':'living_services','topic':topic,'service_action':'recommend'},
                               '帮我找悉尼搬家公司' if topic=='moving' else '找退租清洁公司')
            self.assertGreaterEqual(len(answer['providers']),3)
            for provider in answer['providers']:
                self.assertIn(category,provider['categories'])
                self.assertTrue(provider['source_url'].startswith('https://'))
                self.assertIn('2026-',provider['checked_on'])
        self.assertEqual(self.client.get(self.root + '/living-services').json()['version'],0)

    def test_invented_utility_selection_is_not_proposed(self):
        answer = self.send({'intent':'living_services','topic':'utilities','service_action':'update_profile',
                            'profile_patch':{'utilities':{'electricity':'agl'}}},'我还没选电力公司')
        self.assertFalse(any(a['type']=='apply_living_services' for a in answer['actions']))
        self.assertEqual(self.client.get(self.root + '/living-services').json()['version'],0)

    def test_concurrent_living_change_rejects_model_result_and_contacts_stay_local(self):
        values=self.client.get(self.root+'/living-services').json()['profile']
        values.update(address='Private Example Address',agent_email='private@example.com',agent_phone='0400123456')
        def concurrent_update():
            result=self.client.post(self.root+'/living-services/profile',json={
                'request_id':'concurrent','expected_version':0,'confirmed':True,'values':values})
            self.assertEqual(result.status_code,200,result.text)
        self.provider.on_call=concurrent_update
        self.provider.result={'intent':'living_services','topic':'utilities','service_action':'update_profile',
                              'profile_patch':{'utilities':{'electricity':'agl'}}}
        r=self.client.post(self.path+'/messages',json={'request_id':'stale','expected_revision':0,
            'message':'我的电力用AGL，请记录','allow_external_ai':True})
        self.assertEqual(r.status_code,409,r.text)
        self.assertEqual(self.client.get(self.path).json()['revision'],0)
        current=self.client.get(self.root+'/living-services').json()
        self.assertIsNone(current['profile']['utilities']['electricity'])
        context=self.provider.inputs[0]['living_services']['profile']
        self.assertNotIn('agent_email',context); self.assertNotIn('agent_phone',context)
        self.assertNotIn('address',context)

    def test_real_aftercare_defaults_and_clock_have_no_demo_facts_or_checkpoints(self):
        config=self.client.get('/api/v1/demo-config').json()
        tenancy=config['tenancy_template']
        self.assertEqual(tenancy['address'],''); self.assertIsNone(tenancy['rooms'])
        self.assertEqual(config['capabilities']['aftercare_evidence_template'],[])
        tenancy={**tenancy,'address':'User Confirmed Test Address','confirmed':True}
        before=datetime.now().astimezone()
        r=self.client.post('/api/v1/aftercare/commands',json={
            'case_id':self.case['case_id'],'request_id':'real-tenancy','expected_version':0,
            'operation':'create','payload':{'tenancy':tenancy,'evidence':[]}})
        self.assertEqual(r.status_code,200,r.text)
        cid=self.client.get(self.root).json()['aftercare_case_id']
        saved=self.client.get('/api/v1/aftercare/cases/'+cid).json()
        timestamp=datetime.fromisoformat(saved['updated_at'])
        self.assertLess(abs(timestamp-before),timedelta(seconds=10))
        self.assertEqual(saved['evidence'],[])


if __name__ == '__main__': unittest.main()
