import tempfile,unittest
from fastapi.testclient import TestClient

class IssueReportTests(unittest.TestCase):
    def setUp(self):
        from server.tests.legacy_app import create_app
        self.create_app=create_app;self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.client=TestClient(create_app(runtime_dir=self.temp.name))
        self.cid=self.client.post('/api/v1/cases',json={}).json()['case_id']

    def report(self,**changes):
        return {'request_id':'report-once','category':'furniture','description':'Fictional broken chair. 原始内容保留。','attachment_ids':[],**changes}

    def test_direct_report_without_tenancy_auto_date_retry_history_and_advice(self):
        path=f'/api/v1/cases/{self.cid}/issue-reports'
        created=self.client.post(path,json=self.report());self.assertEqual(created.status_code,200,created.text)
        report=created.json();self.assertEqual(report['report']['description'],self.report()['description'])
        self.assertTrue(report['created_at']);self.assertEqual(report['status'],'open')
        self.assertEqual(self.client.post(path,json=self.report()).json(),report)
        case=self.client.get(f'/api/v1/cases/{self.cid}').json();self.assertIsNone(case['aftercare_case_id'])
        self.assertEqual(len(self.client.get('/api/v1/issue-reports').json()['items']),1)
        review=self.client.get('/api/v1/operator/reviews').json()['items'][0]
        self.assertEqual(review['review_id'],report['review_id'])
        body={'request_id':'advice-once','expected_version':1,'note':'Ask the agent to check the chair and provide dated photos.'}
        path=f"/api/v1/issue-reports/{report['review_id']}/advice"
        result=self.client.post(path,json=body);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.post(path,json=body).json(),result.json())
        self.assertEqual(result.json()['status'],'released')
        self.assertEqual(result.json()['report'],report['report'])
        restarted=TestClient(self.create_app(runtime_dir=self.temp.name))
        self.assertEqual(restarted.get('/api/v1/issue-reports').json()['items'][0]['decisions'][0]['note'],body['note'])

    def test_all_types_and_invalid_input(self):
        path=f'/api/v1/cases/{self.cid}/issue-reports'
        for category in ('rent','furniture','repairs','tenancy','moveout','post_tenancy','other'):
            response=self.client.post(path,json=self.report(request_id=category,category=category));self.assertEqual(response.status_code,200,response.text)
        for change in ({'category':'unknown'},{'description':'  '},{'created_at':'2020-01-01'},{'attachment_ids':['foreign-file']}):
            response=self.client.post(path,json=self.report(**change));self.assertIn(response.status_code,(422,404),response.text)

    def test_files_stale_advice_and_legacy_history_are_preserved(self):
        from server.tests.test_operator_inbox import OperatorInboxTests
        helper=OperatorInboxTests();helper.client=self.client;helper.headers={}
        helper.config=self.client.get('/api/v1/demo-config').json();helper.templates=self.client.get('/api/v1/aftercare/template-commands').json()
        helper.dispute('Fictional older home')
        # Legacy direct reports remain in the new history without changing tenancy records.
        old_case=self.client.post('/api/v1/cases',json={}).json()['case_id']
        tenancy=dict(helper.config['tenancy_template'],address='Fictional legacy home',confirmed=True,baseline_evidence_refs=[])
        created=helper.command(old_case,0,'create',{'tenancy':tenancy,'evidence':[]})
        helper.command(old_case,created['version'],'report_issue',{'category':'cleaning','title':'Older report','description':'Original older report','requested_outcome':'Check records','amount_cents':None,'evidence_refs':[],'tenant_confirmed':True})
        pdf=b'%PDF-1.4\n%%EOF\n'
        result=self.client.post(f'/api/v1/cases/{self.cid}/living-services/attachments?purpose=moveout',content=pdf,headers={'Content-Type':'application/pdf','X-Filename':'receipt.pdf','X-Request-Id':'pdf-once'})
        self.assertEqual(result.status_code,200,result.text);file=result.json()
        path=f'/api/v1/cases/{self.cid}/issue-reports'
        created=self.client.post(path,json=self.report(attachment_ids=[file['attachment_id']])).json()
        history=self.client.get('/api/v1/issue-reports').json()['items']
        self.assertEqual(history[0]['review_id'],created['review_id'])
        self.assertTrue(any(row['report'].get('description')=='Original older report' for row in history))
        self.assertEqual(history[0]['attachments'],[file])
        other=self.client.post('/api/v1/cases',json={}).json()['case_id']
        self.assertEqual(self.client.post(f'/api/v1/cases/{other}/issue-reports',json=self.report(attachment_ids=[file['attachment_id']])).status_code,404)
        path=f"/api/v1/issue-reports/{created['review_id']}/advice"
        self.assertEqual(self.client.post(path,json={'request_id':'stale','expected_version':2,'note':'Stale advice'}).status_code,409)
        before=self.client.get('/api/v1/issue-reports').json()
        self.assertEqual(self.client.post(path,json={'request_id':'blank','expected_version':1,'note':'   '}).status_code,422)
        self.assertEqual(self.client.get('/api/v1/issue-reports').json(),before)
