"""Chat delivers the exact email that explicit confirmation saves, without mail delivery."""
import tempfile
import unittest
from copy import deepcopy
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.app.ai.provider import ProviderError
from server.tests.test_assistant_api import IntentProvider

MESSAGE='厨房水槽从昨晚开始漏水，帮我准备一封礼貌的英文报修邮件，只准备草稿，不要发送。'
FACT='厨房水槽从昨晚开始漏水'

class DraftProvider(IntentProvider):
    def __init__(self):
        super().__init__();self.polish_fail=False
        self.result={'intent':'living_services','topic':'repairs','service_action':'report_repair',
                     'repair':{'title':'Property repair','description':FACT,'location':'Kitchen','priority':'normal'}}
    def call(self,context):
        if context['task']=='repair_email_polish':
            self.inputs.append(deepcopy(context))
            if self.polish_fail:raise ProviderError('ai_timeout',{'task':context['task'],'status':'failed'})
            return {'subject':'Repair request: leaking kitchen sink','body':'Dear Property Manager,\n\nThe kitchen sink has been leaking since last night. Could you please arrange an inspection and repair?\n\nThank you.'},{'task':context['task'],'status':'succeeded'}
        return super().call(context)

class ChatRepairDraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.provider=DraftProvider();self.app=create_app(runtime_dir=self.tmp.name,ai_provider=self.provider)
        self.client=TestClient(self.app)
        self.case=self.client.post('/api/v1/cases',json={}).json();self.root='/api/v1/cases/'+self.case['case_id']
        self.chat=self.client.post(self.root+'/assistant/conversations',json={}).json()
        self.path=self.root+'/assistant/conversations/'+self.chat['conversation_id']
    def send(self,message=MESSAGE):
        body={'request_id':'turn-'+str(self.chat['revision']),'expected_revision':self.chat['revision'],'message':message,'allow_external_ai':True}
        r=self.client.post(self.path+'/messages',json=body)
        if r.status_code==200:self.chat=r.json()
        return r,body
    def apply(self,answer,key='save'):
        action=next(a for a in answer['actions'] if a['type']=='apply_living_services')
        return self.client.post(self.root+'/living-services/proposals/'+action['proposal_id']+'/apply',json={
            'request_id':key,'expected_version':action['expected_version'],'confirmed':True})
    def test_english_polite_preview_exists_without_recipient_and_exact_text_is_saved_once(self):
        response,body=self.send();self.assertEqual(response.status_code,200,response.text)
        answer=response.json()['messages'][-1];draft=answer.get('repair_email')
        self.assertIsNotNone(draft,'Email body must be delivered inside the chat before saving')
        self.assertEqual(draft['language'],'en');self.assertEqual(draft['tone'],'polite');self.assertEqual(draft['to'],'')
        self.assertIn('since last night',draft['body']);self.assertNotIn('Description',draft['body'])
        polish=next(c for c in self.provider.inputs if c['task']=='repair_email_polish')
        self.assertEqual(polish['language'],'en');self.assertEqual(polish['tone'],'polite')
        self.assertEqual(self.client.get(self.root+'/living-services').json()['repairs'],[])
        self.assertEqual(self.client.post(self.path+'/messages',json=body).json(),response.json())
        self.assertEqual(sum(c['task']=='repair_email_polish' for c in self.provider.inputs),1)
        saved=self.apply(answer);self.assertEqual(saved.status_code,200,saved.text)
        entry=saved.json()['repairs'][0]
        self.assertEqual(entry['email']['subject'],draft['subject']);self.assertEqual(entry['email']['body'],draft['body'])
        self.assertEqual(entry['email']['delivery_status'],'prepared_not_sent')
        self.assertEqual(self.apply(answer).json(),saved.json())
    def test_pending_and_saved_rewrites_update_one_issue_and_keep_preview_on_reload(self):
        first,_=self.send();self.assertEqual(first.status_code,200,first.text)
        first_answer=first.json()['messages'][-1]
        self.provider.result={'intent':'living_services','topic':'repairs','service_action':'update_repair','repair_update':{'email_tone':'concise'}}
        second,_=self.send('这封英文邮件简洁一点')
        self.assertEqual(second.status_code,200,second.text);answer=second.json()['messages'][-1]
        self.assertIsNotNone(answer.get('repair_email'))
        self.assertEqual(answer['repair_email']['tone'],'concise')
        self.assertEqual(self.apply(first_answer,'old').status_code,409)
        saved=self.apply(answer);self.assertEqual(saved.status_code,200,saved.text)
        rid=saved.json()['repairs'][0]['repair_id']
        third,_=self.send('这封邮件再礼貌一点');self.assertEqual(third.status_code,200,third.text)
        answer=third.json()['messages'][-1];self.assertIsNotNone(answer.get('repair_email'))
        final=self.apply(answer,'rewrite');self.assertEqual(final.status_code,200,final.text)
        self.assertEqual(len(final.json()['repairs']),1);self.assertEqual(final.json()['repairs'][0]['repair_id'],rid)
        self.assertEqual(final.json()['repairs'][0]['email']['body'],answer['repair_email']['body'])
        restored=self.client.get(self.path).json()['messages'][-1]
        self.assertEqual(restored['repair_email'],answer['repair_email'])
    def test_pending_rewrite_stays_english_despite_legacy_language_and_tone_changes(self):
        first,_=self.send();self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.apply(first.json()['messages'][-1]).status_code,200)
        self.provider.result={'intent':'living_services','topic':'repairs','service_action':'update_repair','repair_update':{'email_language':'zh'}}
        translated,_=self.send('把这封邮件改成中文');self.assertEqual(translated.status_code,200,translated.text)
        self.provider.result['repair_update']={'email_tone':'concise'}
        concise,_=self.send('简洁一点，保留原来的问题事实');self.assertEqual(concise.status_code,200,concise.text)
        self.assertEqual(concise.json()['messages'][-1]['repair_email']['language'],'en')
        self.assertEqual(next(c for c in reversed(self.provider.inputs) if c['task']=='repair_email_polish')['language'],'en')

    def test_rewrite_preserves_original_property_when_living_profile_moves(self):
        profile=self.client.get(self.root+'/living-services').json()['profile'];profile['address']='Old Property'
        self.client.post(self.root+'/living-services/profile',json={'request_id':'old-property','expected_version':0,'confirmed':True,'values':profile})
        first,_=self.send();self.assertEqual(first.status_code,200,first.text)
        saved=self.apply(first.json()['messages'][-1]);self.assertEqual(saved.status_code,200,saved.text)
        profile['address']='New Property'
        self.client.post(self.root+'/living-services/profile',json={'request_id':'new-property','expected_version':2,'confirmed':True,'values':profile})
        self.provider.result={'intent':'living_services','topic':'repairs','service_action':'update_repair','repair_update':{'email_tone':'concise'}}
        result,_=self.send('简洁一点，保留原来的问题事实');self.assertEqual(result.status_code,200,result.text)
        body=result.json()['messages'][-1]['repair_email']['body']
        self.assertIn('Old Property',body);self.assertNotIn('New Property',body)
        for context in self.provider.inputs:
            self.assertNotIn('Old Property',str(context));self.assertNotIn('New Property',str(context))

    def test_generation_failure_does_not_save_a_wrong_language_template(self):
        self.provider.polish_fail=True
        response,_=self.send()
        self.assertEqual(response.status_code,503,response.text)
        self.assertEqual(self.client.get(self.root+'/living-services').json()['repairs'],[])
        self.assertEqual(self.client.get(self.path).json()['revision'],0)
    def test_stored_contacts_stay_local_and_stale_preview_cannot_overwrite_changes(self):
        profile=self.client.get(self.root+'/living-services').json()['profile']
        profile.update(address='Private Address',agent_name='Private Manager',agent_email='private@example.com')
        self.client.post(self.root+'/living-services/profile',json={'request_id':'p','expected_version':0,'confirmed':True,'values':profile})
        response,_=self.send();self.assertEqual(response.status_code,200,response.text)
        answer=response.json()['messages'][-1]
        for context in self.provider.inputs:
            raw=str(context);self.assertNotIn('private@example.com',raw);self.assertNotIn('Private Address',raw);self.assertNotIn('Private Manager',raw)
        self.assertEqual(answer['repair_email']['to'],'private@example.com')
        self.client.post(self.root+'/living-services/profile',json={'request_id':'p2','expected_version':1,'confirmed':True,'values':profile})
        self.assertEqual(self.apply(answer).status_code,409)

if __name__=='__main__':unittest.main()
