"""Lease sources remain read-only previews until a current, explicit tenancy import."""
import copy
from contextlib import closing
import tempfile
import unittest

from server.app.adapters.services import Services
from server.app.adapters.real_agent2 import RealProfilesAdapter
from server.app.common import ApiError
from server.app.lease_drafts.service import LeaseDraftService
from server.app.living.service import LivingService
from server.app.settings import Settings, TENANT


class LivingTenancyTests(unittest.TestCase):
    def setUp(self):
        from server.app.living.tenancy import LivingTenancy
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ctx=Services(Settings(runtime_dir=self.temp.name))
        self.profiles=RealProfilesAdapter(self.ctx)
        self.case=self.profiles.create_case({});self.cid=self.case['case_id']
        self.other=self.profiles.create_case({})['case_id']
        self.living=LivingService(self.ctx)
        self.service=LivingTenancy(self.ctx)
        self.drafts=LeaseDraftService(self.ctx)

    def error(self, code, action):
        with self.assertRaises(ApiError) as result:action()
        self.assertEqual(result.exception.code,code)

    def select(self, index=0):
        if not self.case['confirmations']:
            self.case=self.profiles.confirm(self.cid,{'draft_revision':self.case['draft']['revision'],
                'fingerprint':self.case['draft']['fingerprint'],'review_token':self.case['agent1']['review_token']})
        run=self.profiles.evaluation(self.cid,{'request_id':'run','confirmation_version':1})
        row=run['report']['pending_confirmation'][index]
        self.profiles.select(self.cid,{'request_id':'select-'+str(index),'run_id':run['run_id'],'listing_id':row['listing_id'],'confirmed':True})
        return row

    def draft(self, fields=None, **extra):
        context=self.drafts.context(self.cid)
        body={'request_id':'draft','context_token':context['context_token'],'expected_version':0,
              'confirmed':True,'applicability_confirmed':True,'fields':{**context['defaults'],
              'rental_mode':'whole_property','agent_name':'Alex Agent',
              'agent_contact':'Email: alex@example.com; Phone: +61 2 9000 1234',
              'start_date':'2026-11-01','end_date':'2027-11-01',**(fields or {})},**extra}
        return self.drafts.save(self.cid,body)

    def apply_body(self, preview, fields=None, **extra):
        return {'request_id':'import','expected_version':preview['expected_version'],'confirmed':True,
                'actual_tenancy_confirmed':True,'source_token':preview['source']['token'],
                'fields':fields or list(preview['values']),**extra}

    def seed_aftercare(self, address='Confirmed Home', carpeted=False):
        template=copy.deepcopy(self.ctx.settings.templates['create'])
        tenancy=template['tenancy'];tenancy.update(confirmed=True,address=address,tenant_id=TENANT,tenancy_id='tenancy-real')
        response=self.ctx.aftercare.submit({'schema_version':'1.0','case_id':'aftercare-real','request_id':'aftercare-create',
            'actor_id':TENANT,'actor_role':'tenant','expected_version':0,'operation':'create','payload':template,
            'as_of':'2026-10-22T10:00:00+11:00'})
        # Explicit confirmed record owns known fields; do not derive dates or names from task state.
        with closing(self.ctx.aftercare.connect()) as connection:
            import json
            record=response['case'];record['tenancy']['carpeted']=carpeted
            connection.execute('UPDATE cases SET document=? WHERE case_id=?',(json.dumps(record),'aftercare-real'))
        with self.ctx.repo.transaction() as db:
            case=self.ctx.get(db,'case',self.cid);case['aftercare_case_id']='aftercare-real'
            self.ctx.repo.put(db,'case',self.cid,case)
            self.ctx.repo.put(db,'aftercare_mapping','aftercare-real',{'case_id':self.cid})

    def test_no_source_and_preview_never_write_or_confirm_advertisement(self):
        self.select()
        with self.ctx.repo.transaction() as db:
            before=list(db.execute('SELECT kind,id,body FROM objects ORDER BY kind,id'))
        preview=self.service.preview(self.cid)
        self.assertIsNone(preview['source']);self.assertEqual(preview['values'],{})
        self.assertEqual(preview['expected_version'],0);self.assertFalse(preview['changed'])
        with self.ctx.repo.transaction() as db:
            self.assertEqual(before,list(db.execute('SELECT kind,id,body FROM objects ORDER BY kind,id')))

    def test_draft_values_require_both_confirmations_and_selected_fields_only(self):
        self.select();self.draft()
        preview=self.service.preview(self.cid)
        self.assertEqual(preview['source']['kind'],'lease_draft');self.assertTrue(preview['source']['current'])
        self.assertEqual(preview['values']['agent_email'],'alex@example.com')
        self.assertEqual(preview['values']['agent_phone'],'+61 2 9000 1234')
        self.assertEqual(preview['values']['lease_start_date'],'2026-11-01')
        self.assertEqual(preview['values']['lease_end_date'],'2027-11-01')
        self.assertTrue(preview['source']['warning'])
        body=self.apply_body(preview,['address','agent_email'])
        self.error('confirmation_required',lambda:self.service.apply(self.cid,{**body,'confirmed':False}))
        self.error('confirmation_required',lambda:self.service.apply(self.cid,{**body,'actual_tenancy_confirmed':False}))
        saved=self.service.apply(self.cid,body)
        self.assertEqual(saved['version'],1);self.assertEqual(saved['profile']['agent_email'],'alex@example.com')
        self.assertEqual(saved['profile']['agent_name'],'')
        self.assertTrue(saved['tenancy_source']['actual_tenancy_confirmed'])
        self.assertEqual(saved['tenancy_source']['fields'],['address','agent_email'])
        self.assertEqual(self.service.apply(self.cid,body),saved)
        self.error('request_conflict',lambda:self.service.apply(self.cid,{**body,'fields':['address']}))

    def test_nonempty_values_preserve_profile_and_all_existing_service_records(self):
        self.select();self.draft({'agent_name':'','agent_contact':'','landlord_name':'Owner',
            'landlord_contact':'owner@example.com','end_date':None})
        profile=self.living.read(self.cid)['profile'];profile.update(agent_phone='02 9000 1111',notes='keep me')
        saved=self.living.profile(self.cid,{'request_id':'save','expected_version':0,'confirmed':True,'values':profile})
        with self.ctx.repo.transaction() as db:
            saved['repairs']=[{'repair_id':'kept'}];saved['bookings']=[{'booking_id':'kept'}]
            self.ctx.repo.put(db,'living_services',self.cid,saved)
            original=self.ctx.get(db,'case',self.cid)
        preview=self.service.preview(self.cid)
        self.assertEqual(preview['values']['agent_name'],'Owner')
        self.assertEqual(preview['values']['agent_email'],'owner@example.com')
        self.assertNotIn('agent_phone',preview['values']);self.assertNotIn('lease_end_date',preview['values'])
        result=self.service.apply(self.cid,self.apply_body(preview))
        self.assertEqual(result['profile']['agent_phone'],'02 9000 1111');self.assertEqual(result['profile']['notes'],'keep me')
        self.assertEqual(result['repairs'],saved['repairs']);self.assertEqual(result['bookings'],saved['bookings'])
        with self.ctx.repo.transaction() as db:self.assertEqual(original,self.ctx.get(db,'case',self.cid))

    def test_import_allows_lease_dates_but_never_sets_planned_move_out_date(self):
        self.select();self.draft()
        preview=self.service.preview(self.cid)
        result=self.service.apply(self.cid,self.apply_body(preview))
        self.assertEqual(result['profile']['lease_end_date'],'2027-11-01')
        self.assertIsNone(result['profile']['move_out_date'])

    def test_changed_candidate_stales_draft_and_cross_case_source_token_is_rejected(self):
        self.select();self.draft();preview=self.service.preview(self.cid)
        self.error('source_changed',lambda:self.service.apply(self.other,self.apply_body(preview)))
        self.select(1)
        stale=self.service.preview(self.cid)
        self.assertFalse(stale['source']['current'])
        self.error('source_changed',lambda:self.service.apply(self.cid,self.apply_body(preview)))

    def test_draft_revision_and_record_revision_require_fresh_preview(self):
        self.select();draft=self.draft();preview=self.service.preview(self.cid)
        self.draft({'agent_name':'Other Agent'},request_id='revision',draft_id=draft['draft_id'],expected_version=1)
        self.error('source_changed',lambda:self.service.apply(self.cid,self.apply_body(preview)))
        fresh=self.service.preview(self.cid)
        profile=self.living.read(self.cid)['profile']
        self.living.profile(self.cid,{'request_id':'save','expected_version':0,'confirmed':True,'values':profile})
        self.error('version_conflict',lambda:self.service.apply(self.cid,self.apply_body(fresh)))

    def test_empty_unknown_and_duplicate_selected_fields_are_rejected(self):
        self.select();self.draft();preview=self.service.preview(self.cid)
        for fields in ([],['utilities'],['address','address']):
            body=self.apply_body(preview);body['fields']=fields
            self.error('invalid_input',lambda:self.service.apply(self.cid,body))

    def test_confirmed_aftercare_uses_same_home_current_draft_contacts_and_dates(self):
        self.select();self.draft({'address':'Confirmed Home'});self.seed_aftercare()
        preview=self.service.preview(self.cid)
        self.assertEqual(preview['source']['kind'],'aftercare')
        self.assertEqual(preview['values'],{'address':'Confirmed Home','carpeted':False,
            'agent_name':'Alex Agent','agent_email':'alex@example.com','agent_phone':'+61 2 9000 1234',
            'lease_start_date':'2026-11-01','lease_end_date':'2027-11-01'})
        self.assertIn('未签署草稿',preview['source']['warning'])
        result=self.service.apply(self.cid,self.apply_body(preview))
        self.assertEqual(result['profile']['address'],'Confirmed Home');self.assertFalse(result['profile']['carpeted'])
        self.assertEqual(result['profile']['agent_email'],'alex@example.com')
        self.assertEqual(result['profile']['lease_start_date'],'2026-11-01')

    def test_same_home_supplement_draft_revision_changes_aftercare_token(self):
        self.select();draft=self.draft({'address':'Confirmed Home'});self.seed_aftercare()
        before=self.service.preview(self.cid)
        self.draft({'address':'Confirmed Home','agent_name':'Updated Agent'},request_id='revised',
            draft_id=draft['draft_id'],expected_version=1)
        after=self.service.preview(self.cid)
        self.assertEqual(after['source']['kind'],'aftercare')
        self.assertEqual(after['values']['agent_name'],'Updated Agent')
        self.assertNotEqual(before['source']['token'],after['source']['token'])
        self.error('source_changed',lambda:self.service.apply(self.cid,self.apply_body(before)))

    def test_stale_same_home_draft_never_supplements_confirmed_aftercare(self):
        self.select();self.draft({'address':'Confirmed Home'});self.seed_aftercare()
        self.select(1)
        preview=self.service.preview(self.cid)
        self.assertEqual(preview['source']['kind'],'aftercare')
        self.assertEqual(preview['values'],{'address':'Confirmed Home','carpeted':False})

    def test_new_home_draft_is_explicit_and_preserves_existing_household_records(self):
        self.select();self.draft({'address':'New Home'});self.seed_aftercare('Old Home')
        preview=self.service.preview(self.cid)
        self.assertEqual(preview['source']['kind'],'lease_draft')
        self.assertTrue(preview['source']['current']);self.assertIn('地址',preview['source']['warning'])
        self.assertIn('保留',preview['source']['warning'])

    def test_aftercare_task_changes_do_not_change_source_token_but_tenancy_changes_do(self):
        self.seed_aftercare();preview=self.service.preview(self.cid)
        with closing(self.ctx.aftercare.connect()) as connection:
            import json
            row=connection.execute('SELECT document FROM cases WHERE case_id=?',('aftercare-real',)).fetchone()
            value=json.loads(row[0]);value['version']+=1;value['plan']={'some':'unrelated task data'}
            connection.execute('UPDATE cases SET document=? WHERE case_id=?',(json.dumps(value),'aftercare-real'))
        self.assertEqual(self.service.preview(self.cid)['source']['token'],preview['source']['token'])
        with closing(self.ctx.aftercare.connect()) as connection:
            value['tenancy']['address']='Updated Home'
            connection.execute('UPDATE cases SET document=? WHERE case_id=?',(json.dumps(value),'aftercare-real'))
        self.assertNotEqual(self.service.preview(self.cid)['source']['token'],preview['source']['token'])
        self.error('source_changed',lambda:self.service.apply(self.cid,self.apply_body(preview)))

    def test_invalid_or_ambiguous_contacts_are_not_offered(self):
        self.select();self.draft({'agent_contact':'Bad a..b@example.com; meeting 2026-11-01'})
        preview=self.service.preview(self.cid)
        self.assertNotIn('agent_email',preview['values']);self.assertNotIn('agent_phone',preview['values'])
        self.draft({'agent_contact':'alex@example.com, other@example.com'},request_id='second')
        self.assertNotIn('agent_email',self.service.preview(self.cid)['values'])

    def test_missing_agent_name_never_mixes_landlord_name_and_email_with_agent_phone(self):
        self.select();self.draft({'agent_name':'','agent_contact':'Phone: 02 9000 2222',
            'landlord_name':'Different Owner','landlord_contact':'owner@example.com'})
        values=self.service.preview(self.cid)['values']
        self.assertEqual(values['agent_phone'],'02 9000 2222')
        self.assertNotIn('agent_email',values);self.assertNotIn('agent_name',values)

    def test_a_date_in_contact_field_is_not_a_phone_number(self):
        self.select();self.draft({'agent_contact':'2026-11-01'})
        self.assertNotIn('agent_phone',self.service.preview(self.cid)['values'])

    def test_preview_cannot_follow_another_cases_saved_draft_or_aftercare_mapping(self):
        self.select();draft=self.draft()
        with self.ctx.repo.transaction() as db:
            self.ctx.repo.put(db,'lease_draft_index',self.other,[{'draft_id':draft['draft_id']}])
        self.error('not_found',lambda:self.service.preview(self.other))
        self.seed_aftercare()
        with self.ctx.repo.transaction() as db:
            case=self.ctx.get(db,'case',self.other);case['aftercare_case_id']='aftercare-real'
            self.ctx.repo.put(db,'case',self.other,case)
            self.ctx.repo.put(db,'lease_draft_index',self.other,[])
        self.error('not_found',lambda:self.service.preview(self.other))

    def test_existing_import_receipt_replays_after_source_and_profile_change(self):
        self.select();self.draft();preview=self.service.preview(self.cid)
        body=self.apply_body(preview,['address']);saved=self.service.apply(self.cid,body)
        self.select(1)
        values=self.living.read(self.cid)['profile'];values['notes']='later edit'
        self.living.profile(self.cid,{'request_id':'later','expected_version':1,'confirmed':True,'values':values})
        self.assertEqual(self.service.apply(self.cid,body),saved)
        self.assertEqual(self.living.read(self.cid)['profile']['notes'],'later edit')


if __name__=='__main__':unittest.main()
