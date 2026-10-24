"""Commute intake and shared previews retain explicit, owned conversation data."""
from unittest.mock import patch
from copy import deepcopy
import unittest
import json,tempfile
from pathlib import Path
from types import SimpleNamespace
from server.tests import test_assistant_api as harness

DEST = {'id':'nsw-campus-1','label':'University of Sydney, Camperdown NSW',
        'latitude':-33.888,'longitude':151.187,'precision':'address_point','source_url':'https://www.nsw.gov.au/'}

class Resolver:
    def __init__(self):self.calls=[]
    def search(self,q,limit=5):self.calls.append(q);return [deepcopy(DEST)]

class AssistantCommuteTests(unittest.TestCase):
    setUp=harness.AssistantTests.setUp
    conversation=harness.AssistantTests.conversation
    send=harness.AssistantTests.send

    def test_chinese_destination_alias_preserves_explicit_campus(self):
        from server.app.assistant.commute import normalized_query
        self.assertEqual(normalized_query('悉尼大学 Camperdown校区'),'University of Sydney Camperdown')
        self.assertEqual(normalized_query('悉尼科技大学'),'University of Technology')
        self.assertEqual(normalized_query('UTS'),'University of Technology')

    def test_location_sidecar_is_loaded_only_for_current_catalogue(self):
        from server.app.assistant.commute import location_points
        from server.app.common import now
        with tempfile.TemporaryDirectory() as tmp:
            catalog=SimpleNamespace(path=Path(tmp)/'listings.json',fingerprint='current')
            self.assertEqual(location_points(catalog),{})
            sidecar=catalog.path.with_name('locations.json')
            sidecar.write_text(json.dumps({'catalog_fingerprint':'old','queried_at':now(),'points':{'domain:1':DEST}}))
            self.assertEqual(location_points(catalog),{})
            sidecar.write_text(json.dumps({'catalog_fingerprint':'current','queried_at':now(),'points':{'domain:1':DEST}}))
            self.assertEqual(location_points(catalog),{'domain:1':DEST})
            sidecar.write_text('{broken')
            self.assertEqual(location_points(catalog),{})

    def recommend(self,c,patch_value,request='rec',text='帮我推荐区域',**kwargs):
        self.provider.result={'intent':'recommend_areas','brief_patch':patch_value}
        return self.send(c,request,text,**kwargs)

    def ready_brief(self):
        return {'recommend_areas':True,'suburb':None,'budget_amount':850,'budget_period':'week','budget_scope':'whole_property',
                'min_bedrooms':2,'min_bathrooms':1,'min_car_spaces':0,'occupants':1,
                'destination_query':'University of Sydney','arrival_time':'09:00','commute_max_minutes':40,
                'commute_mode':'public_transport','travel_day':'weekday'}

    def test_unknown_area_starts_focused_intake_without_requiring_suburb(self):
        r=self.recommend(self.conversation(),{},text='刚来悉尼，不知道住哪，帮我推荐')
        self.assertEqual(r.status_code,200,r.text);c=r.json()
        self.assertIn('预算',c['messages'][-1]['content']);self.assertNotIn('想住哪个区域',c['messages'][-1]['content'])
        self.assertEqual(c['dialogue_mode'],'recommend_areas')
        r=self.recommend(c,{'budget_amount':850,'budget_period':'week','budget_scope':'whole_property','min_bedrooms':2},'next','每周整套850，两卧')
        self.assertEqual(r.status_code,200,r.text);text=r.json()['messages'][-1]['content']
        self.assertIn('学校',text);self.assertNotIn('想住哪个区域',text)
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)

    def test_destination_lookup_requires_separate_data_consent_and_selection(self):
        resolver=Resolver();c=self.conversation()
        with patch('server.app.assistant.commute.resolver_for',return_value=resolver):
            r=self.recommend(c,self.ready_brief())
            self.assertEqual(r.status_code,200,r.text);c=r.json();self.assertFalse(resolver.calls)
            self.assertIn('位置',c['messages'][-1]['content'])
            r=self.recommend(c,{},'lookup','查询学校位置',allow_external_data=True)
            self.assertEqual(r.status_code,200,r.text);c=r.json()
            self.assertEqual(resolver.calls,['University of Sydney'])
            self.assertEqual(c['messages'][-1]['destination_options'][0],DEST)
            self.assertNotIn('commute_recommendation',c['messages'][-1])
            r=self.recommend(c,{'destination_id':'nsw-other'},'bad','选择nsw-other',allow_external_data=True)
            self.assertEqual(r.status_code,422)
            r=self.recommend(c,{'destination_id':DEST['id']},'silent','就选第一个',allow_external_data=True)
            self.assertEqual(r.status_code,422)

    def test_selected_destination_generates_shared_preview_without_profile_write(self):
        resolver=Resolver();c=self.conversation()
        def answer(ctx,brief,destination,allow_external):
            self.assertTrue(allow_external);self.assertEqual(destination,DEST)
            self.assertEqual(brief['commute_max_minutes'],40)
            return {'intent':'recommend_areas','agent':'agent2','content':'接口未配置，通勤待查询。','actions':[],
                    'listings':[], 'commute_recommendation':{'status':'unavailable','criteria':brief,'queried_at':'2099-01-01T00:00:00Z',
                    'destination':destination,'areas':[],'routes':[],'limitations':['NSW接口未配置']}}
        with patch('server.app.assistant.commute.resolver_for',return_value=resolver),patch('server.app.assistant.commute.plan_routes',side_effect=answer):
            c=self.recommend(c,self.ready_brief(),allow_external_data=True).json()
            r=self.recommend(c,{'destination_id':DEST['id']},'pick','选择地点 '+DEST['id'],allow_external_data=True)
            self.assertEqual(r.status_code,200,r.text);c=r.json()
            latest=self.client.get(self.base+'/commute-recommendation').json()
            self.assertFalse(latest['stale']);self.assertEqual(latest['conversation_id'],c['conversation_id'])
            self.assertEqual(latest['message']['commute_recommendation']['status'],'unavailable')
            self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)
            r=self.recommend(c,{'commute_max_minutes':50},'change','放宽到50分钟')
            self.assertEqual(r.status_code,200,r.text)
            self.assertTrue(self.client.get(self.base+'/commute-recommendation').json()['stale'])
            self.assertEqual(r.json()['rental_brief']['budget_amount'],850)
            self.assertIn('commute',self.provider.inputs[-1])

    def test_new_conversation_intake_invalidates_previous_shared_result(self):
        repo=self.client.app.state.repository;c=self.conversation()
        from server.app.assistant.service import signature
        from server.app.common import now
        with repo.transaction() as db:
            saved=repo.get(db,'assistant_conversation',c['conversation_id']);saved['rental_brief']={}
            repo.put(db,'assistant_conversation',c['conversation_id'],saved)
            repo.put(db,'assistant_commute_report',self.case['case_id'],{'conversation_id':c['conversation_id'],
                'brief':{},'case_signature':signature(self.case),'catalog_fingerprint':self.client.get('/api/v1/listings?page_size=1').json()['catalog']['fingerprint'],
                'created_at':now(),'message':{'commute_recommendation':{'status':'unavailable'}}})
        self.assertFalse(self.client.get(self.base+'/commute-recommendation').json()['stale'])
        response=self.recommend(self.conversation(),{},'new-intake')
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(self.client.get(self.base+'/commute-recommendation').json()['stale'])

    def test_changed_destination_clears_previous_selection_and_options(self):
        resolver=Resolver();c=self.conversation()
        with patch('server.app.assistant.commute.resolver_for',return_value=resolver):
            c=self.recommend(c,self.ready_brief(),allow_external_data=True).json()
            with self.client.app.state.repository.transaction() as db:
                stored=self.client.app.state.repository.get(db,'assistant_conversation',c['conversation_id'])
                stored['rental_brief']['destination_id']=DEST['id']
                self.client.app.state.repository.put(db,'assistant_conversation',c['conversation_id'],stored)
            r=self.recommend(c,{'destination_query':'UNSW'},'new','目的地改为UNSW')
            self.assertEqual(r.status_code,200,r.text)
            self.assertNotIn('destination_id',r.json()['rental_brief'])
            self.assertFalse(r.json().get('commute_destination_options'))

    def test_explicit_choice_wins_over_model_rewriting_its_search_label(self):
        resolver=Resolver();c=self.conversation()
        with patch('server.app.assistant.commute.resolver_for',return_value=resolver),patch('server.app.assistant.commute.plan_routes',return_value={'intent':'recommend_areas','agent':'agent2','content':'完成','listings':[],'actions':[]}):
            c=self.recommend(c,self.ready_brief(),allow_external_data=True).json()
            r=self.recommend(c,{'destination_id':DEST['id'],'destination_query':DEST['label']},'choice','我的通勤目的地选择：'+DEST['label']+'（地点编号 '+DEST['id']+'）',allow_external_data=True)
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json()['rental_brief']['destination_id'],DEST['id'])
            self.assertEqual(len(resolver.calls),1)

    def test_schema_rejects_invented_coordinates_and_bad_times(self):
        for index,invalid in enumerate(({'latitude':-33.8},{'arrival_time':'28:90'},{'commute_max_minutes':0},{'commute_max_minutes':999})):
            r=self.recommend(self.conversation(),invalid,request="bad-"+str(index))
            self.assertEqual(r.status_code,502,r.text)
        other=self.client.post('/api/v1/cases',json={}).json()['case_id']
        self.assertEqual(self.client.get(self.base.replace(self.case['case_id'],other)+'/commute-recommendation').status_code,200)
        self.assertIsNone(self.client.get(self.base.replace(self.case['case_id'],other)+'/commute-recommendation').json())

    def test_confirming_housing_needs_preserves_conversation_commute_slots(self):
        brief={**self.ready_brief(),'rental_mode':'whole_property'}
        c=self.recommend(self.conversation(),brief).json()
        prepared=self.client.post(self.base+'/conversations/'+c['conversation_id']+'/proposals',json={
            'request_id':'sync','expected_revision':c['revision'],'expected_profile_fingerprint':self.case['draft']['fingerprint'],
            'brief':c['rental_brief']})
        self.assertEqual(prepared.status_code,200,prepared.text)
        applied=self.client.post(self.base+'/proposals/'+prepared.json()['proposal_id']+'/apply',json={'request_id':'apply-sync','confirmed':True})
        self.assertEqual(applied.status_code,200,applied.text)
        conversation=applied.json()['conversation']
        self.assertEqual(conversation['rental_brief']['arrival_time'],'09:00')
        self.assertEqual(conversation['rental_brief']['commute_max_minutes'],40)
        self.assertEqual(conversation['dialogue_mode'],'recommend_areas')

    def test_direct_saved_budget_proposal_keeps_commute_intake_before_confirmation(self):
        c=self.recommend(self.conversation(),self.ready_brief()).json()
        self.provider.result={'intent':'update_preferences','preference_patch':{'budget':{'maximum':900}}}
        response=self.send(c,'edit-saved','把已保存的最高周预算改为900，其他条件保留')
        self.assertEqual(response.status_code,200,response.text);c=response.json()
        self.assertEqual(c['dialogue_mode'],'recommend_areas')
        self.assertEqual(c['rental_brief']['budget_amount'],900)
        self.assertEqual(c['rental_brief']['destination_query'],'University of Sydney')
        self.assertEqual(c['rental_brief']['commute_max_minutes'],40)
        self.assertEqual(c['rental_brief']['min_bedrooms'],2)
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)
