"""Case-owned living records: explicit confirmation, durable retries and truthful drafts."""
import copy
import tempfile
import unittest

from server.app.adapters.profiles import ProfilesAdapter
from server.app.adapters.services import Services
from server.app.common import ApiError
from server.app.settings import Settings


DIRECTORY = {'checked_on': '2026-10-22', 'providers': [
    {'id': 'power', 'name': 'Power', 'categories': ['electricity', 'gas'],
     'website': 'https://power.example', 'contact_url': 'https://power.example/contact',
     'phone': None, 'coverage': 'NSW', 'source_url': 'https://power.example',
     'checked_on': '2026-10-22', 'notes': ''},
    {'id': 'clean', 'name': 'Cleaner', 'categories': ['cleaner'],
     'website': 'https://clean.example', 'contact_url': 'https://clean.example/contact',
     'phone': None, 'coverage': 'Sydney', 'source_url': 'https://clean.example',
     'checked_on': '2026-10-22', 'notes': ''},
]}


class LivingServiceTests(unittest.TestCase):
    def setUp(self):
        from server.app.living.service import LivingService
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ctx = Services(Settings(runtime_dir=self.temp.name))
        self.cid = ProfilesAdapter(self.ctx).create_case({})['case_id']
        self.other = ProfilesAdapter(self.ctx).create_case({})['case_id']
        self.service = LivingService(self.ctx, providers=DIRECTORY)

    def envelope(self, values, version=0, request='save'):
        return {'request_id': request, 'expected_version': version, 'confirmed': True, 'values': values}

    def assert_error(self, code, action):
        with self.assertRaises(ApiError) as raised:
            action()
        self.assertEqual(raised.exception.code, code)

    def profile_values(self, **changes):
        values = self.service.read(self.cid)['profile']
        values.update(changes)
        return values

    def repair_values(self):
        return {'title': 'Leaking tap', 'description': 'Kitchen tap drips continuously.',
                'location': 'Kitchen', 'priority': 'normal'}

    def test_read_defaults_are_blank_without_mutating_case_or_persisting_record(self):
        with self.ctx.repo.transaction() as db:
            original = self.ctx.get(db, 'case', self.cid)
        record = self.service.read(self.cid)
        self.assertEqual(record['version'], 0)
        self.assertEqual(record['profile']['address'], '')
        self.assertIsNone(record['profile']['bedrooms'])
        self.assertIsNone(record['profile']['has_pets'])
        self.assertEqual(record['repairs'], [])
        self.assertEqual(record['bookings'], [])
        with self.ctx.repo.transaction() as db:
            self.assertEqual(original, self.ctx.get(db, 'case', self.cid))
            self.assertEqual(db.execute("SELECT count(*) FROM objects WHERE kind LIKE 'living%'").fetchone()[0], 0)
        self.assert_error('not_found', lambda: self.service.read('missing'))

    def test_profile_is_confirmed_versioned_and_retry_replays_before_version_check(self):
        body = self.envelope(self.profile_values(address='1 Main Street', agent_email='agent@example.com'))
        saved = self.service.profile(self.cid, body)
        self.assertEqual(saved['version'], 1)
        self.assertEqual(self.service.profile(self.cid, body), saved)
        self.assert_error('request_conflict', lambda: self.service.profile(self.cid, {**body, 'values': self.profile_values(address='Other')}))
        self.assert_error('version_conflict', lambda: self.service.profile(self.cid, {**body, 'request_id':'other'}))
        self.assert_error('confirmation_required', lambda: self.service.profile(self.cid, {**body, 'request_id':'no', 'confirmed':False}))
        saved['profile']['address'] = 'client mutation'
        self.assertEqual(self.service.read(self.cid)['profile']['address'], '1 Main Street')

    def test_profile_validates_full_shape_nullable_types_dates_contacts_and_providers(self):
        for changes in ({'agent_email':'agent@example.com\r\nBcc: x@x.com'}, {'agent_email':'broken'},
                        {'agent_email':'.bad@example.com'}, {'agent_email':'a..b@example.com'},
                        {'agent_phone':'call me'}, {'emergency_phone':'000\nX'}, {'postcode':'abc'},
                        {'move_out_date':'2026-02-30'}, {'bedrooms':True}, {'bathrooms':-1},
                        {'has_pets':'yes'}, {'utilities': {'electricity':'power'}}):
            with self.subTest(changes=changes):
                self.assert_error('invalid_input', lambda: self.service.profile(self.cid,self.envelope(self.profile_values(**changes))))
        values = self.profile_values(); values.pop('address')
        self.assert_error('invalid_input', lambda:self.service.profile(self.cid,self.envelope(values)))
        values = self.profile_values(); values['utilities']['internet'] = 'power'
        self.assert_error('invalid_provider', lambda:self.service.profile(self.cid,self.envelope(values)))
        values = self.profile_values(); values['utilities']['electricity'] = 'power'
        saved = self.service.profile(self.cid,self.envelope(values))
        self.assertEqual(saved['profile']['utilities']['electricity'], 'power')

    def test_repair_uses_only_saved_facts_and_never_sends_email(self):
        profile = self.profile_values(address='1 Main Street', agent_name='Alex', agent_email='alex@example.com')
        self.service.profile(self.cid,self.envelope(profile))
        body = self.envelope(self.repair_values(),version=1,request='repair')
        saved = self.service.repair(self.cid,body)
        entry = saved['repairs'][0]
        self.assertEqual(entry['status'],'prepared')
        self.assertEqual(entry['email']['to'],'alex@example.com')
        self.assertEqual(entry['email']['delivery_status'],'prepared_not_sent')
        self.assertIn('1 Main Street',entry['email']['body'])
        self.assertIn('Kitchen tap drips continuously.',entry['email']['body'])
        self.assertNotRegex(entry['email']['body'].lower(),r'\blease\b')
        self.assertEqual(self.service.repair(self.cid,body),saved)
        blank = self.service.repair(self.other,self.envelope(self.repair_values()))['repairs'][0]
        self.assertEqual(blank['email']['to'],'')
        self.assertNotIn('1 Main Street',blank['email']['body'])

    def test_repair_status_requires_case_ownership_and_retains_email_snapshot(self):
        saved = self.service.repair(self.cid,self.envelope(self.repair_values()))
        entry = saved['repairs'][0]
        body = self.envelope({'status':'contacted'},version=1,request='status')
        changed = self.service.update_repair(self.cid,entry['repair_id'],body)
        self.assertEqual(changed['repairs'][0]['status'],'contacted')
        self.assertEqual(changed['repairs'][0]['email'],entry['email'])
        self.assertEqual(self.service.update_repair(self.cid,entry['repair_id'],body),changed)
        self.assert_error('not_found',lambda:self.service.update_repair(self.other,entry['repair_id'],self.envelope({'status':'resolved'})))
        self.assert_error('invalid_input',lambda:self.service.repair(self.other,self.envelope({**self.repair_values(),'title':'Tap\r\nBcc:bad'})))

    def test_booking_checks_provider_category_and_case_owned_updates(self):
        values={'provider_id':'clean','service_date':'2026-11-01','quote_amount':None,'status':'considering','notes':''}
        saved=self.service.booking(self.cid,self.envelope(values))
        booking=saved['bookings'][0]
        self.assertEqual(booking['provider_id'],'clean')
        update=self.envelope({**values,'booking_id':booking['booking_id'],'status':'booked','quote_amount':125.5},version=1,request='update')
        result=self.service.booking(self.cid,update)
        self.assertEqual(len(result['bookings']),1)
        self.assertEqual(result['bookings'][0]['status'],'booked')
        self.assertEqual(self.service.booking(self.cid,update),result)
        self.assert_error('not_found',lambda:self.service.booking(self.other,self.envelope({**values,'booking_id':booking['booking_id']})))
        self.assert_error('invalid_provider',lambda:self.service.booking(self.other,self.envelope({**values,'provider_id':'power'})))
        self.assert_error('invalid_input',lambda:self.service.booking(self.other,self.envelope({**values,'quote_amount':True})))
        self.assert_error('invalid_reference',lambda:self.service.booking(self.other,self.envelope({**values,'booking_id':None})))

    def test_profile_proposal_is_partial_preview_until_explicit_apply(self):
        before=self.service.read(self.cid)
        proposal=self.service.prepare_proposal(self.cid,'profile',{'agent_email':'agent@example.com'},'My agent email is agent@example.com')
        self.assertEqual(proposal['expected_version'],0)
        self.assertEqual(proposal['status'],'pending')
        self.assertTrue(proposal['summary'])
        self.assertIsInstance(proposal['summary'],list)
        self.assertTrue(any('agent@example.com' in line for line in proposal['summary']))
        self.assertEqual(self.service.read(self.cid),before)
        body={'request_id':'apply','expected_version':0,'confirmed':True}
        self.assert_error('not_found',lambda:self.service.apply(self.other,proposal['proposal_id'],body))
        self.assert_error('confirmation_required',lambda:self.service.apply(self.cid,proposal['proposal_id'],{**body,'confirmed':False}))
        saved=self.service.apply(self.cid,proposal['proposal_id'],body)
        self.assertEqual(saved['profile']['agent_email'],'agent@example.com')
        self.assertEqual(saved['profile']['address'],'')
        self.assertEqual(self.service.apply(self.cid,proposal['proposal_id'],body),saved)
        self.assert_error('proposal_applied',lambda:self.service.apply(self.cid,proposal['proposal_id'],{**body,'request_id':'again','expected_version':1}))

    def test_stale_proposal_does_not_overwrite_new_profile(self):
        proposal=self.service.prepare_proposal(self.cid,'profile',{'address':'Old address'},'Address')
        self.service.profile(self.cid,self.envelope(self.profile_values(address='New address')))
        self.assert_error('version_conflict',lambda:self.service.apply(self.cid,proposal['proposal_id'],{'request_id':'apply','expected_version':0,'confirmed':True}))
        self.assertEqual(self.service.read(self.cid)['profile']['address'],'New address')

    def test_repair_proposal_only_creates_email_after_confirmation(self):
        proposal=self.service.prepare_proposal(self.cid,'repair',self.repair_values(),'Please draft a repair request')
        self.assertTrue(any('Kitchen tap drips continuously.' in line for line in proposal['summary']))
        self.assertEqual(self.service.read(self.cid)['repairs'],[])
        saved=self.service.apply(self.cid,proposal['proposal_id'],{'request_id':'apply','expected_version':0,'confirmed':True})
        self.assertEqual(len(saved['repairs']),1)
        self.assertEqual(saved['repairs'][0]['email']['delivery_status'],'prepared_not_sent')
        self.assert_error('invalid_input',lambda:self.service.prepare_proposal(self.cid,'profile',{'signed_lease':True},'test'))

    def test_directory_returns_isolated_copy(self):
        result=self.service.directory(); result['providers'][0]['name']='mutated'
        self.assertEqual(self.service.directory()['providers'][0]['name'],'Power')

    def test_partial_utility_proposal_preserves_other_choices_and_has_reviewable_summary(self):
        proposal=self.service.prepare_proposal(self.cid,'profile',{'utilities':{'electricity':'power'}},'Choose power')
        self.assertTrue(any('Power' in line and 'Electricity' in line for line in proposal['summary']))
        saved=self.service.apply(self.cid,proposal['proposal_id'],{'request_id':'apply','expected_version':0,'confirmed':True})
        self.assertEqual(saved['profile']['utilities'],{'electricity':'power','gas':None,'internet':None,'water':None})

    def test_completed_receipt_remains_replayable_after_a_later_write(self):
        body=self.envelope(self.profile_values(address='First'))
        first=self.service.profile(self.cid,body)
        self.service.profile(self.cid,self.envelope(self.profile_values(address='Second'),version=1,request='second'))
        self.assertEqual(self.service.profile(self.cid,body),first)
        self.assertEqual(self.service.read(self.cid)['profile']['address'],'Second')

    def test_route_bound_methods_accept_json_body_and_use_standard_error_envelope(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from server.app.http import install_error_handlers
        app=FastAPI()
        install_error_handlers(app,self.ctx)
        app.get('/cases/{case_id}/living-services')(self.service.read)
        app.post('/cases/{case_id}/living-services/profile')(self.service.profile)
        client=TestClient(app)
        path='/cases/'+self.cid+'/living-services'
        result=client.post(path+'/profile',json=self.envelope(self.profile_values(address='1 Real Street')))
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['profile']['address'],'1 Real Street')
        denied=client.post(path+'/profile',json=self.envelope(self.profile_values(),request='new'))
        self.assertEqual(denied.status_code,409)
        self.assertEqual(denied.json()['error']['code'],'version_conflict')


if __name__ == '__main__':
    unittest.main()
