import unittest
from server.tests import test_living_tenancy as fixtures

class LivingHomeTests(unittest.TestCase):
    setUp=fixtures.LivingTenancyTests.setUp
    select=fixtures.LivingTenancyTests.select
    draft=fixtures.LivingTenancyTests.draft

    def test_home_includes_saved_utilities_and_all_service_records_without_mutation(self):
        from server.app.living.home import LivingHome
        providers=self.living.directory()['providers']
        gas=next(p for p in providers if 'gas' in p['categories'])
        mover=next(p for p in providers if 'removalist' in p['categories'])
        values=self.living.read(self.cid)['profile'];values['utilities']['gas']=gas['id']
        record=self.living.profile(self.cid,{'request_id':'utilities','expected_version':0,'confirmed':True,'values':values})
        record=self.living.booking(self.cid,{'request_id':'moving','expected_version':record['version'],'confirmed':True,'values':{'provider_id':mover['id'],'service_date':'2026-11-10','quote_amount':350,'status':'completed','notes':'Fictional completed service'}})
        summary=LivingHome(self.ctx).read(self.cid)
        self.assertEqual(summary['profile']['utilities']['gas'],gas['id'])
        self.assertEqual(summary['bookings'],record['bookings'])
        self.assertEqual(summary['expected_version'],record['version'])
        self.assertEqual(self.living.read(self.cid),record)
        summary['bookings'][0]['notes']='Caller change'
        self.assertEqual(self.living.read(self.cid)['bookings'][0]['notes'],'Fictional completed service')

    def test_selected_home_is_a_read_only_reference_with_dedicated_locality(self):
        from server.app.living.home import LivingHome
        self.select()
        with self.ctx.repo.transaction() as db:
            case=self.ctx.get(db,'case',self.cid);snapshot=case['selection']['listing_snapshot']
            before=list(db.execute('SELECT kind,id,body FROM objects ORDER BY kind,id'))
        result=LivingHome(self.ctx).read(self.cid)
        self.assertEqual(result['values']['address'],snapshot['address'])
        self.assertEqual(result['values']['suburb'],snapshot['suburb'])
        self.assertEqual(result['values']['postcode'],snapshot['postcode'])
        self.assertEqual(result['values']['agent_email'],'')
        self.assertEqual(result['sources']['address'],'Selected property')
        with self.ctx.repo.transaction() as db:self.assertEqual(before,list(db.execute('SELECT kind,id,body FROM objects ORDER BY kind,id')))
        self.assertEqual(result['profile']['address'],'')

    def test_saved_home_and_contact_group_win_over_other_selected_home(self):
        from server.app.living.home import LivingHome
        self.select();self.draft()
        values=self.living.read(self.cid)['profile'];values.update(address='9 Fictional Saved Street',suburb='Saved suburb',postcode='2000',agent_name='Saved Agent',agent_email='',agent_phone='0491 570 000',notes='Keep notes',own_furniture='Keep furniture')
        self.living.profile(self.cid,{'request_id':'save','expected_version':0,'confirmed':True,'values':values})
        result=LivingHome(self.ctx).read(self.cid)
        self.assertEqual(result['values']['address'],'9 Fictional Saved Street')
        self.assertEqual(result['values']['agent_name'],'Saved Agent')
        self.assertEqual(result['values']['agent_email'],'')
        self.assertEqual(result['profile']['notes'],'Keep notes')
        self.assertEqual(result['profile']['own_furniture'],'Keep furniture')

    def test_draft_contacts_only_fill_for_same_home_and_never_mix_roles(self):
        from server.app.living.home import LivingHome
        self.select();draft=self.draft()
        result=LivingHome(self.ctx).read(self.cid)
        self.assertEqual(result['values']['agent_name'],'Alex Agent')
        self.assertEqual(result['values']['agent_email'],'alex@example.com')
        self.draft({'address':'Different Fictional House','agent_name':'Other Agent'},request_id='different',draft_id=draft['draft_id'],expected_version=1)
        result=LivingHome(self.ctx).read(self.cid)
        self.assertEqual(result['values']['agent_name'],'')
        self.assertEqual(result['values']['agent_email'],'')
