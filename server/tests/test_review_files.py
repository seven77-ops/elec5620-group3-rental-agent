from server.tests.test_operator_inbox import OperatorInboxTests
from urllib.parse import quote

PDF=b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n'

class ReviewFilesTests(OperatorInboxTests):
    def seed(self):
        cid=self.client.post('/api/v1/cases',json={}).json()['case_id']
        state=self.command(cid,0,'create',{'tenancy':dict(self.config['tenancy_template'],address='Fictional review address',confirmed=True,baseline_evidence_refs=[]),'evidence':[]})
        return cid,state

    def upload(self,cid):
        response=self.client.post(f'/api/v1/cases/{cid}/living-services/attachments?purpose=moveout',content=PDF,headers={'Content-Type':'application/pdf','X-Filename':quote('清洁收据.pdf'),'X-Request-Id':'receipt'})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def report(self,ids):
        return {'category':'cleaning','title':'Disputed cleaning charge','description':'Fictional agent deduction. 原文保留。','requested_outcome':'Please review the receipt.','amount_cents':18000,'evidence_refs':[],'attachment_ids':ids,'tenant_confirmed':True}

    def test_direct_review_and_case_scoped_files_survive_restart(self):
        cid,state=self.seed();item=self.upload(cid)
        state=self.command(cid,state['version'],'report_issue',self.report([item['attachment_id']]))
        response=self.client.get('/api/v1/operator/reviews')
        self.assertEqual(response.status_code,200,response.text)
        review=response.json()['items'][0]
        self.assertEqual(review['attachments'],[item])
        tenant=self.client.get('/api/v1/aftercare/cases/'+state['case_id']).json()
        self.assertEqual(tenant['reviews'][0]['attachments'],[item])
        self.assertEqual(self.client.get(item['download_url']).content,PDF)
        decision={'review_id':review['review_id'],'decision':'release','note':'Reviewed receipt; ask the agent for an itemised explanation.','gate_resolved':True}
        state=self.command(cid,state['version'],'operator_decision',decision)
        self.assertEqual(state['case']['reviews'][0]['status'],'released')
        from fastapi.testclient import TestClient
        restarted=TestClient(self.create_app(runtime_dir=self.temp.name))
        saved=restarted.get('/api/v1/operator/reviews').json()['items'][0]
        self.assertEqual(saved['attachments'],[item])
        self.assertEqual(saved['decisions'][0]['note'],decision['note'])

    def test_cross_case_file_is_rejected_and_reply_can_attach_own_file(self):
        cid,state=self.seed();other,_=self.seed();foreign=self.upload(other)
        body={'case_id':cid,'request_id':'foreign','expected_version':state['version'],'operation':'report_issue','payload':self.report([foreign['attachment_id']])}
        self.assertEqual(self.client.post('/api/v1/aftercare/commands',json=body).status_code,404)
        state=self.command(cid,state['version'],'report_issue',self.report([]))
        item=self.upload(cid)
        reply={'case_id':cid,'request_id':'reply-files','expected_version':state['version'],'operation':'reply_review','payload':{'review_id':state['case']['reviews'][0]['review_id'],'text':'Fictional receipt supplied','evidence_refs':[],'attachment_ids':[item['attachment_id']],'tenant_confirmed':True}}
        result=self.client.post('/api/v1/aftercare/commands',json=reply)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.post('/api/v1/aftercare/commands',json=reply).json(),result.json())
        review=self.client.get('/api/v1/operator/reviews').json()['items'][0]
        self.assertEqual(review['attachments'],[item])
        self.assertEqual(len(review['updates']),1)
