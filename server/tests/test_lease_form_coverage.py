"""Official form roles, explicit choices and completion requirements stay aligned."""
from copy import deepcopy
from io import BytesIO
import unittest
from pypdf import PdfReader
from server.app.lease_drafts.fields import DEFAULTS, validate_fields, questions
from server.app.lease_drafts.pdf import field_values, generate_pdf, template_metadata, widget_name


class LeaseFormCoverageTests(unittest.TestCase):
    def values(self,**changes):
        return validate_fields({**deepcopy(DEFAULTS),**changes})

    def test_two_agents_map_to_separate_official_sections(self):
        f=self.values(agent_name='Landlord Agent',agent_contact='0400000001',agent_notice_address='1 Agency Road',
            agent_notice_suburb='Rhodes',agent_notice_state='NSW',agent_notice_postcode='2138',
            tenant_agent_name='Tenant Representative',tenant_agent_contact='0400000002',tenant_agent_notice_address='2 Tenant Road',
            tenant_agent_notice_suburb='Glebe',tenant_agent_notice_state='NSW',tenant_agent_notice_postcode='2037')
        values=field_values(f)
        for name,value in {'Text field 2.15':'Landlord Agent','Text field 2.20':'0400000001',
            'Text field 2.21':'Tenant Representative','Text field 2.22':'2 Tenant Road','Text field 2.23':'Glebe',
            'Text field 2.24':'NSW','Text field 2.25':'2037','Text field 2.26':'0400000002'}.items():
            self.assertEqual(values[name],value)
        old=self.values(agent_name='Existing Agency')
        self.assertEqual(field_values(old)['Text field 2.15'],'Existing Agency')
        self.assertNotIn('Text field 2.21',field_values(old))

    def test_explicit_choices_and_conditional_email_battery_fields(self):
        f=self.values(water_usage='yes',electricity_embedded='no',gas_embedded='no',smoke_alarm_type='both',
            smoke_battery_replaceable='yes',smoke_battery_type='AA',smoke_backup_replaceable='yes',smoke_backup_type='9V',
            smoke_strata_responsible='yes',strata_bylaws='yes',landlord_email_consent='yes',landlord_notice_email='owner@example.com',
            tenant_email_consent='no',tenant_notice_email='unused@example.com',bond_recipient='rbo')
        v=field_values(f)
        for key,value in {'Check Box 4.8':'/Yes','Check Box 4.9':'/No','Check Box 4.10':'/No',
            'Check Box 4.11':'/Yes','Check Box 4.12':'/Yes','Text field 4.18':'AA','Text field 4.21':'9V',
            'Check Box 4.22':'/Yes','Check Box 5.1':'/Yes','Check Box 5.3':'/Yes',
            'Text field 5.5':'owner@example.com','Check Box 5.6':'/No',
            'Check Box 4.1':'/NSW Fair Trading through Rental Bond Online'}.items():self.assertEqual(v[key],value,key)
        self.assertNotIn('Text field 5.8',v)
        empty=field_values(self.values())
        for key in ('Check Box 4.8','Check Box 4.9','Check Box 4.10','Check Box 5.3','Check Box 5.6'):
            self.assertNotIn(key,empty)

    def test_completion_questions_are_conditional_not_invented_defaults(self):
        f=self.values(agent_name='Agency',tenant_agent_name='Representative',landlord_email_consent='yes',smoke_alarm_type='battery',smoke_battery_replaceable='yes')
        missing={q['field'] for q in questions(f)}
        for key in ('tenant_notice_address','max_occupants','payment_method','first_rent_date','rent_due_day',
                    'water_usage','electricity_embedded','gas_embedded','strata_bylaws','agent_contact','agent_notice_address',
                    'tenant_agent_contact','tenant_agent_notice_address','landlord_notice_email','smoke_battery_type'):
            self.assertIn(key,missing)
        self.assertNotIn('landlord_notice_address',missing)
        self.assertNotIn('smoke_backup_type',missing)
        self.assertIn('landlord_notice_address',{q['field'] for q in questions(self.values())})
        self.assertNotIn('tenant_agent_name',{q['field'] for q in questions(self.values())})

    def test_written_pdf_has_values_in_field_tree_and_widgets_and_blank_signatures(self):
        f=self.values(agent_name='Agency One',agent_contact='0400000001',tenant_agent_name='Representative Two',
            tenant_agent_contact='0400000002',water_usage='no',electricity_embedded='yes',smoke_alarm_type='battery',
            tenant_email_consent='yes',tenant_notice_email='tenant@example.com')
        draft={'draft_id':'coverage','version':1,'fields':f,'template':template_metadata(),'questions':questions(f)}
        data=generate_pdf(draft);reader=PdfReader(BytesIO(data));saved=reader.get_fields()
        expected=field_values(f)
        for name,value in expected.items():self.assertEqual(str(saved[name].get('/V')),value,name)
        found=set()
        for page in reader.pages:
            for ref in page.get('/Annots',[]):
                obj=ref.get_object();name=widget_name(obj)
                if name not in expected:continue
                node=obj
                while '/V' not in node and node.get('/Parent'):node=node['/Parent'].get_object()
                self.assertEqual(str(node.get('/V')),expected[name],name)
                self.assertTrue(obj.get('/AP',{}).get('/N'))
                found.add(name)
        self.assertEqual(set(expected),found)
        self.assertTrue(all(not field.get('/V') for field in saved.values() if field.get('/FT')=='/Sig'))

    def test_not_applicable_choices_clear_stale_hidden_values_and_ai_cannot_choose_consent(self):
        from server.app.common import ApiError
        from server.app.lease_drafts.ai import grounded_patch
        f=self.values(smoke_alarm_type='hardwired',smoke_battery_replaceable='yes',smoke_battery_type='AA',
            tenant_email_consent='no',tenant_notice_email='not-an-email')
        self.assertIsNone(f['smoke_battery_replaceable'])
        self.assertEqual(f['smoke_battery_type'],'')
        self.assertEqual(f['tenant_notice_email'],'')
        with self.assertRaises(ApiError):grounded_patch({'fields':[{'field':'tenant_email_consent','value':'yes','quote':'yes'}]},'yes')
