"""Real-provider boundary, local drafts and explicit save for repair polishing."""
import copy
import unittest

from server.app.ai.provider import ProviderError
from server.tests import test_living_services as living_tests


class Stub:
    def __init__(self):
        self.calls = []
        self.output = {'subject': 'Kitchen tap repair request', 'body': 'Dear Alex,\n\nThe kitchen tap is leaking. Could you please arrange a repair?\n\nThank you.'}
        self.fail = False

    def call(self, context):
        self.calls.append(copy.deepcopy(context))
        if self.fail:
            raise ProviderError('ai_timeout', {'task': 'repair_email_polish'})
        return copy.deepcopy(self.output), {'task':'repair_email_polish','provider':'test','model':'test','status':'succeeded','attempted':True}


class RepairEmailAITests(unittest.TestCase):
    envelope = living_tests.LivingServiceTests.envelope
    assert_error = living_tests.LivingServiceTests.assert_error
    repair_values = living_tests.LivingServiceTests.repair_values
    def setUp(self):
        living_tests.LivingServiceTests.setUp(self)
        from server.app.living.email_ai import RepairEmailAI
        self.provider = Stub()
        self.ctx.ai_provider = self.provider
        self.ai = RepairEmailAI(self.ctx)
        self.body = {'request_id':'polish-1','allow_external_ai':True,
            'draft':'厨房水龙头漏水，请安排维修。','recipient_name':'Alex',
            'language':'en','tone':'polite','title':'','location':'厨房','priority':'normal'}

    def test_polish_is_read_only_and_retry_replays(self):
        before = self.service.read(self.cid)
        result = self.ai.polish(self.cid, self.body)
        self.assertEqual(result['subject'], self.provider.output['subject'])
        self.assertEqual(self.ai.polish(self.cid, self.body), result)
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(self.service.read(self.cid), before)
        context = self.provider.calls[0]
        self.assertEqual(context['task'], 'repair_email_polish')
        self.assertEqual(context['draft'], self.body['draft'])
        self.assertNotIn('profile', context)
        self.assertNotIn('case_id', context)
        self.assertNotIn('agent_email', context)

    def test_consent_case_and_input_checked_before_provider(self):
        self.assert_error('ai_consent_required', lambda:self.ai.polish(self.cid,{**self.body,'allow_external_ai':False}))
        self.assert_error('not_found', lambda:self.ai.polish('missing',self.body))
        for patch in ({'draft':' '},{'recipient_name':'Alex\nBcc:other'},{'language':'fr'},{'tone':'rude'},{'draft':'x'*5001}):
            self.assert_error('invalid_input', lambda:self.ai.polish(self.cid,{**self.body,**patch}))
        self.assertEqual(self.provider.calls, [])

    def test_request_identity_and_case_scope(self):
        self.ai.polish(self.cid,self.body)
        self.assert_error('request_conflict', lambda:self.ai.polish(self.cid,{**self.body,'draft':'Other issue'}))
        self.ai.polish(self.other,self.body)
        self.assertEqual(len(self.provider.calls),2)

    def test_bad_output_is_not_saved_and_can_retry(self):
        for output in ({'subject':'x\nBcc: bad','body':'test'},{'subject':'x','body':''},
                       {'subject':'x','body':'test','send':True},{'subject':4,'body':'test'}):
            self.provider.output = output
            self.assert_error('ai_invalid_response', lambda:self.ai.polish(self.cid,self.body))
        self.provider.output = {'subject':'Repair request','body':'Dear Alex, please arrange a repair.'}
        self.assertEqual(self.ai.polish(self.cid,self.body)['subject'],'Repair request')
        self.assertEqual(self.service.read(self.cid)['repairs'],[])

    def test_provider_failure_is_honest_and_retryable(self):
        self.provider.fail = True
        self.assert_error('ai_unavailable', lambda:self.ai.polish(self.cid,self.body))
        self.provider.fail = False
        self.ai.polish(self.cid,self.body)
        self.assertEqual(len(self.provider.calls),2)

    def test_save_preserves_reviewed_email_and_original_issue(self):
        values = {**self.repair_values(),'recipient_name':'Alex',
            'email_draft':{'subject':'My edited subject','body':'Dear Alex,\n\nMy edited wording.'}}
        record = self.service.repair(self.cid,self.envelope(values))
        entry = record['repairs'][0]
        self.assertEqual(entry['description'],values['description'])
        self.assertEqual(entry['email']['subject'],values['email_draft']['subject'])
        self.assertEqual(entry['email']['body'],values['email_draft']['body'])
        self.assertEqual(entry['email']['delivery_status'],'prepared_not_sent')
        self.assertEqual(self.service.read(self.cid)['repairs'][0],entry)
        self.assert_error('custom_email_requires_polish', lambda:self.service.update_repair(self.cid,entry['repair_id'],
            self.envelope({'email_tone':'polite'},version=1,request='tone-change')))

    def test_manual_email_validation(self):
        for draft in ({'subject':'bad\nheader','body':'text'},{'subject':'ok','body':''},
                      {'subject':'ok','body':'text','to':'elsewhere@example.com'}):
            self.assert_error('invalid_input', lambda:self.service.repair(self.cid,self.envelope({**self.repair_values(),'email_draft':draft})))
