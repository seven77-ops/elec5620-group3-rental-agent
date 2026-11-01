"""Tenant reports and protected human decisions share one durable review record."""
from copy import deepcopy
from fastapi.testclient import TestClient
from server.tests.test_operator_inbox import OperatorInboxTests

class MoveoutIssueTests(OperatorInboxTests):
    def create_case(self):
        cid=self.client.post('/api/v1/cases',json={}).json()['case_id']
        tenancy=dict(self.config['tenancy_template'],address='1 Fictional Report Road',confirmed=True,baseline_evidence_refs=[])
        created=self.command(cid,0,'create',{'tenancy':tenancy,'evidence':[]})
        return cid,created

    def payload(self,category='bond'):
        return {'category':category,'title':'Fictional move-out issue','description':'中介提议扣款。 Original text must be preserved.',
                'requested_outcome':'Please check the records and explain the next steps.',
                'amount_cents':18000,'evidence_refs':[],'tenant_confirmed':True}

    def test_four_categories_without_bond_and_restart_preserve_original_report(self):
        cid,created=self.create_case()
        state=created
        for category in ('bond','cleaning','repairs','other'):
            state=self.command(cid,state['version'],'report_issue',self.payload(category))
        self.assertIsNone(state['case']['bond'])
        items=[item for item in self.inbox() if item['case_id']==cid]
        self.assertEqual(len(items),4)
        self.assertEqual({i['report']['category'] for i in items},{'bond','cleaning','repairs','other'})
        self.assertTrue(all(i['report']['description']==self.payload()['description'] for i in items))
        restarted=TestClient(self.create_app(runtime_dir=self.temp.name,operator_key='inbox-test'))
        self.assertEqual(self.inbox(restarted),self.inbox())

    def test_retry_once_rejects_stale_version_and_cross_case_evidence(self):
        cid,created=self.create_case()
        body={'case_id':cid,'request_id':'once','expected_version':created['version'],'operation':'report_issue','payload':self.payload()}
        first=self.client.post('/api/v1/aftercare/commands',json=body)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.client.post('/api/v1/aftercare/commands',json=body).json(),first.json())
        stale={**body,'request_id':'stale'}
        self.assertEqual(self.client.post('/api/v1/aftercare/commands',json=stale).status_code,409)
        wrong={**body,'request_id':'foreign','expected_version':first.json()['version'],
               'payload':{**self.payload(),'evidence_refs':['another-case-evidence']}}
        self.assertEqual(self.client.post('/api/v1/aftercare/commands',json=wrong).status_code,409)
        self.assertEqual(len(self.inbox()),1)

    def test_return_reply_and_operator_completion_preserve_report(self):
        cid,created=self.create_case()
        state=self.command(cid,created['version'],'report_issue',self.payload('cleaning'))
        review=state['case']['reviews'][0]
        decision={'review_id':review['review_id'],'decision':'return','note':'Please add the cleaning receipt.','gate_resolved':False}
        unauthorized={'case_id':cid,'request_id':'unauthorized','expected_version':state['version'],'operation':'operator_decision','payload':decision}
        state=self.command(cid,state['version'],'operator_decision',decision,self.headers)
        state=self.command(cid,state['version'],'reply_review',{'review_id':review['review_id'],'text':'The fictional receipt is unavailable.','evidence_refs':[],'tenant_confirmed':True})
        self.assertEqual(state['case']['reviews'][0]['report'],review['report'])
        self.assertEqual(self.inbox()[0]['updates'][0]['text'],'The fictional receipt is unavailable.')
        state=self.command(cid,state['version'],'operator_decision',{**decision,'decision':'release','note':'Reviewed the provided facts.','gate_resolved':True},self.headers)
        self.assertEqual(state['case']['reviews'][0]['status'],'released')
        body={'case_id':cid,'request_id':'late-reply','expected_version':state['version'],'operation':'reply_review','payload':{'review_id':review['review_id'],'text':'Late change','evidence_refs':[],'tenant_confirmed':True}}
        self.assertEqual(self.client.post('/api/v1/aftercare/commands',json=body).status_code,409)

    def test_bond_closure_keeps_independent_report_open_and_allows_later_report(self):
        cid,state=self.dispute('2 Fictional Report Road')
        state=self.command(cid,state['version'],'report_issue',self.payload('repairs'))
        state=self.command(cid,state['version'],'confirm_outcome',{'outcome':'Fictional refund received','evidence_refs':[],'tenant_confirmed':True})
        report=next(r for r in state['case']['reviews'] if r.get('report'))
        self.assertEqual(report['status'],'open')
        bond=deepcopy(state['case']['bond'])
        state=self.command(cid,state['version'],'add_evidence',{'evidence':{
            'evidence_id':'new-exit-receipt','kind':'receipt','source_ref':'user-entered:exit-receipt',
            'source_version':1,'recorded_at':state['case']['updated_at'],'summary':'New fictional receipt after bond closure'}})
        state=self.command(cid,state['version'],'reply_review',{'review_id':report['review_id'],'text':'More fictional details','evidence_refs':['new-exit-receipt'],'tenant_confirmed':True})
        state=self.command(cid,state['version'],'operator_decision',{'review_id':report['review_id'],'decision':'release','note':'Fictional review finished','gate_resolved':True},self.headers)
        state=self.command(cid,state['version'],'report_issue',self.payload('cleaning'))
        self.assertEqual(state['case']['bond'],bond)

    def test_registered_references_are_linked_and_invalid_reports_do_not_create_reviews(self):
        cid,state=self.create_case()
        for identifier in ('linked-receipt','unrelated-photo'):
            state=self.command(cid,state['version'],'add_evidence',{'evidence':{
                'evidence_id':identifier,'kind':'receipt','source_ref':'user-entered:'+identifier,
                'source_version':1,'recorded_at':state['case']['updated_at'],'summary':'Fictional reference '+identifier}})
        report={**self.payload(),'amount_cents':None,'evidence_refs':['linked-receipt']}
        for change in ({'category':'invalid'},{'tenant_confirmed':False},{'description':'   '},{'amount_cents':0}):
            response=self.client.post('/api/v1/aftercare/commands',json={
                'case_id':cid,'request_id':'bad-'+next(iter(change)),'expected_version':state['version'],
                'operation':'report_issue','payload':{**report,**change}})
            self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.inbox(),[])
        state=self.command(cid,state['version'],'report_issue',report)
        self.assertEqual(self.inbox()[0]['report'],report)
        self.assertEqual([e['evidence_id'] for e in self.inbox()[0]['evidence']],['linked-receipt'])
