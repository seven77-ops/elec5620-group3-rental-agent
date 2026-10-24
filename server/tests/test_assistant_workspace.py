"""Cross-page sync uses real Agent1, catalogue reports and candidate persistence."""
from copy import deepcopy
import tempfile
import unittest
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.tests.test_assistant_api import IntentProvider


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.provider=IntentProvider()
        self.client=TestClient(create_app(runtime_dir=self.temp.name,ai_provider=self.provider))
        self.case=self.client.post('/api/v1/cases',json={}).json()
        self.base='/api/v1/cases/'+self.case['case_id']+'/assistant'
        self.c=self.client.post(self.base+'/conversations',json={}).json()
        self.path=self.base+'/conversations/'+self.c['conversation_id']
        self.brief={'suburb':'Rhodes','budget_amount':1500,'budget_period':'week','budget_scope':'whole_property',
            'occupants':1,'min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':1,'rental_mode':'whole_property'}

    def read_case(self):
        return self.client.get('/api/v1/cases/'+self.case['case_id']).json()

    def prepare(self,**changes):
        body={'request_id':'prepare-one','expected_revision':self.c['revision'],
            'expected_profile_fingerprint':self.read_case()['draft']['fingerprint'],'brief':self.brief,**changes}
        return self.client.post(self.path+'/proposals',json=body)

    def sync(self):
        p=self.prepare(); self.assertEqual(p.status_code,200,p.text)
        r=self.client.post(self.base+'/proposals/'+p.json()['proposal_id']+'/apply',
            json={'request_id':'apply-one','confirmed':True})
        self.assertEqual(r.status_code,200,r.text)
        self.c=r.json()['conversation']; return r.json()['case']

    def choose(self,listing_id,**changes):
        body={'request_id':'select-one','expected_revision':self.c['revision'],
            'expected_profile_fingerprint':self.read_case()['draft']['fingerprint'],
            'listing_id':listing_id,'confirmed':True,**changes}
        return self.client.post(self.path+'/selections',json=body)

    def test_prepare_is_reviewable_idempotent_and_apply_links_report_to_profile(self):
        r=self.prepare(); self.assertEqual(r.status_code,200,r.text)
        value=r.json(); self.assertEqual(self.prepare().json(),value)
        self.assertEqual(self.read_case(),self.case)
        self.assertIn('1500',' '.join(value['summary']))
        self.assertEqual(value['conversation']['rental_brief'],self.brief)
        self.assertFalse(self.provider.inputs)
        applied=self.client.post(self.base+'/proposals/'+value['proposal_id']+'/apply',json={'request_id':'apply','confirmed':True})
        self.assertEqual(applied.status_code,200,applied.text)
        case=applied.json()['case']; profile=case['confirmations'][-1]['profile']
        self.assertEqual(profile['housing_preferences']['suburb'],'Rhodes')
        self.assertEqual(profile['budget']['scope'],'whole_property')
        context=self.client.get('/api/v1/cases/'+case['case_id']+'/recommendation-context').json()
        report=self.client.get('/api/v1/evaluations/'+case['evaluations'][-1]['run_id']).json()['report']
        self.assertEqual(context['filters'],report['filters'])
        self.assertEqual(report['profile_fingerprint'],case['draft']['fingerprint'])
        self.assertEqual(report['filter_source'],'confirmed_profile')

    def test_incomplete_invalid_or_stale_requirement_changes_do_not_touch_profile(self):
        for index,brief in enumerate(({**self.brief,'budget_scope':'unknown'},
                {**self.brief,'min_bedrooms':True},{**self.brief,'suburb':'NotASuburb'})):
            r=self.prepare(request_id='bad-'+str(index),brief=brief)
            self.assertEqual(r.status_code,422,r.text)
        self.assertEqual(self.prepare(expected_revision=99).status_code,409)
        self.assertEqual(self.prepare(expected_profile_fingerprint='stale').status_code,409)
        self.assertEqual(self.read_case(),self.case)
        other=self.client.post('/api/v1/cases',json={}).json()['case_id']
        r=self.client.post(self.path.replace(self.case['case_id'],other)+'/proposals',json={
            'request_id':'other','expected_revision':0,'expected_profile_fingerprint':self.case['draft']['fingerprint'],'brief':self.brief})
        self.assertEqual(r.status_code,404)

    def test_chat_candidate_is_explicit_durable_and_visible_in_case(self):
        case=self.sync(); row=self.c['messages'][-1]['listings'][0]
        self.assertEqual(self.choose(row['listing_id'],confirmed=False).status_code,422)
        self.assertIsNone(self.read_case()['selection'])
        r=self.choose(row['listing_id']); self.assertEqual(r.status_code,200,r.text)
        value=r.json(); self.assertEqual(self.choose(row['listing_id']).json(),value)
        saved=self.read_case()['selection']
        self.assertEqual(saved['listing_id'],row['listing_id'])
        self.assertEqual(saved['profile_version'],case['confirmations'][-1]['version'])
        self.assertEqual(saved['listing_snapshot']['address'],row['address'])
        self.assertFalse(saved['contract_ready'])
        self.assertFalse(self.provider.inputs)
        fresh=TestClient(create_app(runtime_dir=self.temp.name,ai_provider=self.provider))
        self.assertEqual(fresh.get('/api/v1/cases/'+case['case_id']).json()['selection'],saved)

    def test_unknown_and_outside_profile_cards_are_rejected_without_partial_report(self):
        self.provider.result={'intent':'search','filters':{'suburb':'Parramatta','max_weekly_rent':1500}}
        r=self.client.post(self.path+'/messages',json={'request_id':'preview','expected_revision':0,
            'message':'只预览Parramatta','allow_external_ai':True})
        self.assertEqual(r.status_code,200,r.text); self.c=r.json()
        outside=self.c['messages'][-1]['listings'][0]['listing_id']
        self.sync(); before=self.read_case()
        self.assertEqual(self.choose('domain:missing').status_code,422)
        r=self.choose(outside); self.assertEqual(r.status_code,409,r.text)
        self.assertEqual(self.read_case(),before)
        row=self.c['messages'][-1]['listings'][0]
        self.assertEqual(self.choose(row['listing_id'],expected_profile_fingerprint='old').status_code,409)

    def test_needs_panel_preserves_other_conditions_from_the_pending_ai_proposal(self):
        self.provider.result={'intent':'update_preferences','preference_patch':{
            'budget':{'maximum':1300},'lease_months':6,'housing_preferences':{'suburb':'Rhodes','min_bedrooms':2}}}
        r=self.client.post(self.path+'/messages',json={'request_id':'ai-needs','expected_revision':0,
            'message':'预算上限改成1300，租六个月，Rhodes两卧','allow_external_ai':True})
        self.assertEqual(r.status_code,200,r.text); self.c=r.json()
        self.assertEqual(self.c.get('rental_brief',{}).get('budget_amount'),1300)
        case=self.sync()
        self.assertEqual(case['draft']['profile']['budget']['maximum'],1500)
        self.assertEqual(case['draft']['profile']['lease_months'],6)

    def test_candidate_accepts_full_length_public_request_ids(self):
        self.sync(); row=self.c['messages'][-1]['listings'][0]
        r=self.choose(row['listing_id'],request_id='s'*80)
        self.assertEqual(r.status_code,200,r.text)

    def test_prepared_manual_requirements_take_priority_over_an_older_preview(self):
        self.provider.result={'intent':'search','filters':{'suburb':'Rhodes','max_weekly_rent':800}}
        r=self.client.post(self.path+'/messages',json={'request_id':'old-preview','expected_revision':0,
            'message':'Rhodes800只看一下','allow_external_ai':True})
        self.c=r.json()
        prepared=self.prepare(); self.assertEqual(prepared.status_code,200,prepared.text)
        c=prepared.json()['conversation']
        self.assertEqual(c['dialogue_mode'],'collect_preferences')
        self.assertEqual(c['rental_brief']['budget_amount'],1500)
        self.assertEqual(self.read_case(),self.case)

    def test_changed_card_facts_require_a_fresh_query_before_selection(self):
        self.sync(); row=self.c['messages'][-1]['listings'][0]
        repo=self.client.app.state.repository
        with repo.transaction() as db:
            c=repo.get(db,'assistant_conversation',self.c['conversation_id'])
            c['messages'][-1]['listings'][0]['weekly_rent']=1
            repo.put(db,'assistant_conversation',c['conversation_id'],c)
        before=self.read_case()
        r=self.choose(row['listing_id'])
        self.assertEqual(r.status_code,409,r.text)
        self.assertEqual(self.read_case(),before)
