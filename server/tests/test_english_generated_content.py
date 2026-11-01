"""Generated English drafts must not silently publish a different output language."""
import tempfile,unittest
from fastapi.testclient import TestClient
from server.app.main import create_app

class EmailProvider:
    def __init__(self):self.output={'subject':'维修申请','body':'您好，请维修厨房水槽。'}
    def public_config(self):return {'enabled':True,'configured':True,'provider':'test','model':'test','timeout_seconds':1}
    def call(self,context):return self.output,{'task':context['task'],'status':'succeeded'}

class EnglishGeneratedDraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.provider=EmailProvider();self.app=create_app(runtime_dir=self.tmp.name,ai_provider=self.provider)
        self.client=TestClient(self.app);self.case=self.client.post('/api/v1/cases',json={}).json()
        self.path='/api/v1/cases/'+self.case['case_id']+'/living-services/repair-email/polish'
        self.body={'request_id':'language-check','allow_external_ai':True,'draft':'厨房水槽漏水','recipient_name':'',
                   'language':'en','tone':'polite','title':'','location':'','priority':'normal'}
    def test_wrong_language_email_is_rejected_and_original_input_is_not_saved(self):
        response=self.client.post(self.path,json=self.body)
        self.assertEqual(response.status_code,502,response.text)
        self.assertEqual(response.json()['error']['code'],'ai_invalid_response')
        self.assertNotRegex(response.json()['error']['message'],r'[\u3400-\u9fff]')
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']+'/living-services').json()['repairs'],[])
    def test_tenant_name_from_the_supplied_draft_is_preserved_in_english(self):
        self.provider.output={'subject':'Kitchen sink repair request','body':'Dear Alex,\n\nMy name is 张三. The kitchen sink is leaking. Could you please arrange a repair?\n\nThank you.'}
        response=self.client.post(self.path,json={**self.body,'recipient_name':'Alex','draft':'我叫张三，厨房水槽漏水，请安排维修。'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('My name is 张三',response.json()['body'])

    def test_user_supplied_name_is_preserved_inside_an_english_email(self):
        self.provider.output={'subject':'Kitchen sink repair request','body':'Dear 王先生,\n\nThe kitchen sink is leaking. Could you please arrange a repair?\n\nThank you.'}
        response=self.client.post(self.path,json={**self.body,'recipient_name':'王先生'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('Dear 王先生',response.json()['body'])

    def test_english_introduction_preserves_the_supplied_name(self):
        self.provider.output={'subject':'Kitchen sink repair request','body':'Dear Alex,\n\nI am 张三. The kitchen sink is leaking. Could you please arrange a repair?\n\nThank you.'}
        response=self.client.post(self.path,json={**self.body,'recipient_name':'Alex','draft':'I am 张三. The kitchen sink is leaking.'})
        self.assertEqual(response.status_code,200,response.text)

    def test_english_email_preserves_grounded_location_but_rejects_invented_place(self):
        self.provider.output={'subject':'Repair request','body':'The tap at 天鹅楼 is leaking. Please arrange an inspection and repair.'}
        body={**self.body,'draft':'The tap at 天鹅楼 is leaking.','location':'天鹅楼'}
        response=self.client.post(self.path,json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('天鹅楼',response.json()['body'])
        self.provider.output['body']='The tap at 未提供的楼名 is leaking. Please arrange an inspection and repair.'
        response=self.client.post(self.path,json={**body,'request_id':'invented-place'})
        self.assertEqual(response.status_code,502,response.text)
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']+'/living-services').json()['repairs'],[])

    def test_english_introduction_preserves_a_supplied_korean_name(self):
        self.provider.output={'subject':'Repair request','body':'My name is 김민수. The kitchen tap is leaking. Please arrange an inspection and repair.'}
        response=self.client.post(self.path,json={**self.body,'draft':'My name is 김민수. The kitchen tap is leaking.'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('김민수',response.json()['body'])

if __name__=='__main__':unittest.main()
