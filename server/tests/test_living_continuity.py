"""Repair conversation continuity without implicit writes or duplicate issues."""
import tempfile
import unittest
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.tests.test_assistant_api import IntentProvider


class LivingContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.provider=IntentProvider()
        self.app=create_app(runtime_dir=self.temp.name,ai_provider=self.provider)
        self.client=TestClient(self.app)
        self.case=self.client.post('/api/v1/cases',json={}).json()
        self.root='/api/v1/cases/'+self.case['case_id']; self.living=self.root+'/living-services'
        self.chat=self.client.post(self.root+'/assistant/conversations',json={}).json()
        self.path=self.root+'/assistant/conversations/'+self.chat['conversation_id']

    def send(self,intent,text):
        self.provider.result=intent
        r=self.client.post(self.path+'/messages',json={'request_id':'turn-'+str(self.chat['revision']),
            'expected_revision':self.chat['revision'],'message':text,'allow_external_ai':True})
        self.assertEqual(r.status_code,200,r.text);self.chat=r.json()
        return self.chat['messages'][-1]

    def report(self):
        return self.send({'intent':'living_services','topic':'repairs','service_action':'report_repair',
            'repair':{'title':'厨房漏水','description':'厨房水槽下面一直漏水','location':'厨房','priority':'normal'}},
            '厨房漏水，厨房水槽下面一直漏水，帮我准备邮件')

    def apply(self,answer,identifier):
        action=next(a for a in answer['actions'] if a['type']=='apply_living_services')
        r=self.client.post(self.living+'/proposals/'+action['proposal_id']+'/apply',json={
            'request_id':identifier,'expected_version':action['expected_version'],'confirmed':True})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def follow(self,patch,text,repair_id=None):
        return self.send({'intent':'living_services','topic':'repairs','service_action':'update_repair',
            'repair_update':patch,**({'repair_id':repair_id} if repair_id else {})},text)

    def test_polite_pending_draft_replaces_proposal_without_saving_an_issue(self):
        old=self.report(); old_id=old['actions'][0]['proposal_id']
        answer=self.follow({'email_tone':'polite'},'把这封邮件写得客气一点')
        self.assertEqual(self.client.get(self.living).json()['repairs'],[])
        record=self.apply(answer,'polite-confirm')
        self.assertEqual(len(record['repairs']),1)
        self.assertEqual(record['repairs'][0]['email_tone'],'polite')
        self.assertIn('厨房水槽下面一直漏水',record['repairs'][0]['email']['body'])
        denied=self.client.post(self.living+'/proposals/'+old_id+'/apply',json={
            'request_id':'old-confirm','expected_version':0,'confirmed':True})
        self.assertEqual(denied.status_code,409)
        restored=self.client.get(self.path).json()
        self.assertTrue(restored['messages'][1]['actions'][0]['superseded'])

    def test_saved_email_rewrite_preserves_issue_identity_and_local_recipient(self):
        profile=self.client.get(self.living).json()['profile']
        profile.update(address='Private Address',agent_email='agent@example.com')
        self.client.post(self.living+'/profile',json={'request_id':'profile','expected_version':0,'confirmed':True,'values':profile})
        saved=self.apply(self.report(),'repair-confirm'); repair=saved['repairs'][0]
        answer=self.follow({'email_tone':'polite'},'写得客气一点')
        self.assertEqual(self.client.get(self.living).json()['version'],saved['version'])
        updated=self.apply(answer,'rewrite-confirm')
        self.assertEqual(len(updated['repairs']),1)
        entry=updated['repairs'][0]
        self.assertEqual(entry['repair_id'],repair['repair_id'])
        self.assertEqual(entry['description'],repair['description'])
        self.assertEqual(entry['email']['to'],'agent@example.com')
        self.assertEqual(entry['email']['delivery_status'],'prepared_not_sent')
        self.assertIn('Private Address',entry['email']['body'])
        context=self.provider.inputs[-1]['living_services']
        self.assertEqual(context['focused_repair_id'],repair['repair_id'])
        self.assertNotIn('Private Address',str(context));self.assertNotIn('agent@example.com',str(context))

    def test_reply_then_resolution_update_same_issue_after_reload(self):
        saved=self.apply(self.report(),'save');rid=saved['repairs'][0]['repair_id']
        self.chat=self.client.get(self.path).json()
        text='中介回复说明天上午来修'
        answer=self.follow({'status':'contacted'},text)
        self.assertEqual(self.client.get(self.living).json()['repairs'][0]['status'],'prepared')
        updated=self.apply(answer,'reply-confirm')
        self.assertEqual(updated['repairs'][0]['status'],'contacted')
        self.assertEqual(updated['repairs'][0]['updates'][-1]['note'],text)
        self.chat=self.client.get(self.path).json()
        answer=self.follow({'status':'resolved'},'已经修好了，标记解决')
        final=self.apply(answer,'resolved-confirm')
        self.assertEqual(len(final['repairs']),1);self.assertEqual(final['repairs'][0]['repair_id'],rid)
        self.assertEqual(final['repairs'][0]['status'],'resolved')

    def test_ambiguous_or_foreign_reference_does_not_update_an_arbitrary_issue(self):
        for n in range(2):
            r=self.client.post(self.living+'/repairs',json={'request_id':'repair-'+str(n),'expected_version':n,
                'confirmed':True,'values':{'title':['厨房漏水','门锁损坏'][n],'description':'用户描述'+str(n),'location':'','priority':'normal'}})
            self.assertEqual(r.status_code,200,r.text)
        for rid in (None,'repair-other-case'):
            answer=self.follow({'status':'resolved'},'已经处理好了',rid)
            self.assertFalse(any(a['type']=='apply_living_services' for a in answer['actions']))
            self.assertIn('哪一条',answer['content'])
        self.assertEqual(self.client.get(self.living).json()['version'],2)

    def test_stale_repair_proposal_conflicts_and_manual_note_is_user_recorded(self):
        saved=self.apply(self.report(),'save');rid=saved['repairs'][0]['repair_id']
        answer=self.follow({'status':'resolved'},'已经修好了')
        action=next(a for a in answer['actions'] if a['type']=='apply_living_services')
        manual=self.client.post(self.living+'/repairs/'+rid,json={'request_id':'manual','expected_version':1,
            'confirmed':True,'values':{'status':'contacted','note':'已致电中介，等待安排'}})
        self.assertEqual(manual.status_code,200,manual.text)
        denied=self.client.post(self.living+'/proposals/'+action['proposal_id']+'/apply',json={
            'request_id':'stale','expected_version':1,'confirmed':True})
        self.assertEqual(denied.status_code,409)
        self.assertEqual(self.client.get(self.living).json()['repairs'][0]['status'],'contacted')

    def test_older_profile_payload_preserves_existing_lease_dates(self):
        profile=self.client.get(self.living).json()['profile']
        profile.update(lease_start_date='2026-11-01',lease_end_date='2027-11-01')
        saved=self.client.post(self.living+'/profile',json={'request_id':'with-dates','expected_version':0,'confirmed':True,'values':profile})
        self.assertEqual(saved.status_code,200,saved.text)
        del profile['lease_start_date'];del profile['lease_end_date']
        profile['agent_name']='Updated Agent'
        r=self.client.post(self.living+'/profile',json={'request_id':'older-edit','expected_version':1,'confirmed':True,'values':profile})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['profile']['lease_start_date'],'2026-11-01')
        self.assertEqual(r.json()['profile']['lease_end_date'],'2027-11-01')
        clear={**r.json()['profile'],'lease_start_date':None,'lease_end_date':None}
        r=self.client.post(self.living+'/profile',json={'request_id':'clear-dates','expected_version':2,'confirmed':True,'values':clear})
        self.assertEqual(r.status_code,200,r.text)
        self.assertIsNone(r.json()['profile']['lease_start_date'])
        self.assertIsNone(r.json()['profile']['lease_end_date'])

    def test_older_profile_payloads_and_date_validation_remain_compatible(self):
        profile=self.client.get(self.living).json()['profile']
        self.assertIsNone(profile['lease_start_date']);self.assertIsNone(profile['lease_end_date'])
        del profile['lease_start_date'];del profile['lease_end_date']
        r=self.client.post(self.living+'/profile',json={'request_id':'old-client','expected_version':0,'confirmed':True,'values':profile})
        self.assertEqual(r.status_code,200,r.text)
        bad={**r.json()['profile'],'lease_start_date':'2027-10-01','lease_end_date':'2026-10-01'}
        r=self.client.post(self.living+'/profile',json={'request_id':'bad-dates','expected_version':1,'confirmed':True,'values':bad})
        self.assertEqual(r.status_code,422,r.text)

if __name__=='__main__':unittest.main()
