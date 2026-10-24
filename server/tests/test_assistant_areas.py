"""Real catalogue and persisted conversation; model transport alone is controlled."""
from unittest.mock import patch
import unittest
from server.tests import test_assistant_api as harness


class AssistantAreaTests(unittest.TestCase):
    setUp=harness.AssistantTests.setUp
    conversation=harness.AssistantTests.conversation
    send=harness.AssistantTests.send

    def ask(self,c,brief=None,areas=None,request='area',text='Burwood 和 Rhodes 哪个适合喜欢餐饮和公园的人？'):
        self.provider.result={'intent':'area_advice','brief_patch':brief or {}}
        if areas is not None:self.provider.result['areas']=areas
        return self.send(c,request,text)

    def test_area_comparison_is_sourced_shared_and_does_not_save_profile(self):
        c=self.conversation()
        r=self.ask(c,{'lifestyle_priorities':['food','parks'],'budget_amount':800,'budget_period':'week',
                      'budget_scope':'whole_property','min_bedrooms':2},['Burwood','Rhodes'])
        self.assertEqual(r.status_code,200,r.text)
        c=r.json(); answer=c['messages'][-1]
        self.assertEqual(answer['intent'],'area_advice')
        self.assertEqual(answer['area_advice']['coverage'],{'covered_suburbs':12,'catalog_suburbs':71})
        self.assertTrue(answer['area_advice']['areas'][0]['evidence'])
        self.assertFalse(answer['listings']); self.assertFalse(answer['actions'])
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)
        shared=self.client.get(self.base+'/area-advice')
        self.assertEqual(shared.status_code,200,shared.text)
        self.assertFalse(shared.json()['stale'])
        self.assertEqual(shared.json()['message']['area_advice'],answer['area_advice'])
        c=self.ask(c,{'lifestyle_priorities':['library']},request='change',text='其他条件保留，改为更看重图书馆').json()
        self.assertEqual(c['rental_brief']['budget_amount'],800)
        self.assertEqual(c['rental_brief']['lifestyle_priorities'],['library'])
        self.assertTrue(all('food' not in a['matched_topics'] for a in c['messages'][-1]['area_advice']['areas']))
        self.assertIn('area_knowledge',next(i for i in reversed(self.provider.inputs) if i['task']=='assistant_intent'))
        c=self.ask(c,{'lifestyle_priorities':[]},request='clear',text='生活配套没有特别要求').json()
        self.assertEqual(c['rental_brief']['lifestyle_priorities'],[])

    def test_unsupported_facts_and_uncovered_area_have_visible_gaps(self):
        r=self.ask(self.conversation(),{'lifestyle_priorities':['quiet','safety']},['Carlton','Rhodes'])
        self.assertEqual(r.status_code,200,r.text)
        areas=r.json()['messages'][-1]['area_advice']['areas']
        self.assertFalse(areas[0]['evidence'])
        self.assertTrue(all(a['missing_topics']==['quiet','safety'] for a in areas))
        self.assertTrue(all(not a['matched_topics'] for a in areas))

    def test_model_cannot_invent_sources_topics_or_unknown_areas(self):
        for index,result in enumerate((
            {'intent':'area_advice','areas':['Made Up Place']},
            {'intent':'area_advice','brief_patch':{'lifestyle_priorities':['quiet_guaranteed']}},
            {'intent':'area_advice','source_url':'https://example.com'},
            {'intent':'area_advice','brief_patch':{'lifestyle_priorities':['food','food']}},
        )):
            self.provider.result=result
            r=self.send(self.conversation(),request='invalid-'+str(index))
            self.assertEqual(r.status_code,502,r.text)

    def test_shared_data_invalidated_by_new_brief_and_dataset_revision(self):
        c=self.ask(self.conversation(),{'lifestyle_priorities':['parks']},['Rhodes']).json()
        with patch('server.app.assistant.areas.AreaKnowledge') as cls:
            cls.return_value.fingerprint='new-version'
            shared=self.client.get(self.base+'/area-advice').json()
            self.assertTrue(shared['stale']); self.assertTrue(any('区域资料' in s for s in shared['stale_reasons']))
        self.provider.result={'intent':'collect_preferences','brief_patch':{'budget_amount':700}}
        changed=self.send(c,'budget','预算上限改成700')
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertTrue(self.client.get(self.base+'/area-advice').json()['stale'])

    def test_area_question_keeps_destination_and_returns_to_recommendation_flow(self):
        from server.tests.test_assistant_commute import AssistantCommuteTests
        c=self.conversation()
        self.provider.result={'intent':'recommend_areas','brief_patch':AssistantCommuteTests.ready_brief(self)}
        c=self.send(c,'commute','帮我按预算和通勤推荐').json()
        c=self.ask(c,{'lifestyle_priorities':['parks']},['Rhodes'],request='area-after').json()
        self.assertEqual(c['rental_brief']['destination_query'],'University of Sydney')
        self.assertEqual(c['dialogue_mode'],'recommend_areas')

    def test_commute_lifestyle_enrichment_does_not_change_hard_eligibility(self):
        from server.app.areas.evidence import AreaKnowledge
        from server.app.assistant.areas import enrich_commute
        answer={'commute_recommendation':{'criteria':{'lifestyle_priorities':['food']},
                  'areas':[{'suburb':'Burwood'},{'suburb':'Rhodes'}]},'listings':[]}
        catalog=type('C',(),{'suburbs':['Burwood','Rhodes'],'matching':lambda self,f:[]})()
        enrich_commute(answer,catalog,AreaKnowledge())
        self.assertEqual(answer['listings'],[])
        self.assertIn('area_context',answer['commute_recommendation']['areas'][0])
        self.assertTrue(answer['commute_recommendation']['area_knowledge_fingerprint'])

    def test_new_conversation_lifestyle_or_commute_intake_invalidates_other_shared_preview(self):
        from server.app.assistant.service import signature
        from server.app.common import now
        c=self.ask(self.conversation(),{'lifestyle_priorities':['parks']},['Rhodes']).json()
        repo=self.client.app.state.repository
        with repo.transaction() as db:
            repo.put(db,'assistant_commute_report',self.case['case_id'],{
                'conversation_id':c['conversation_id'],'brief':c['rental_brief'],'case_signature':signature(self.case),
                'catalog_fingerprint':self.client.get('/api/v1/listings?page_size=1').json()['catalog']['fingerprint'],
                'created_at':now(),'message':{'commute_recommendation':{'status':'unavailable'}}})
        new=self.ask(self.conversation(),{'lifestyle_priorities':['library']},['Burwood'],request='new-area').json()
        self.assertTrue(self.client.get(self.base+'/commute-recommendation').json()['stale'])
        self.provider.result={'intent':'recommend_areas','brief_patch':{'budget_amount':850}}
        r=self.send(self.conversation(),'new-commute','我想按学校通勤推荐房源')
        self.assertEqual(r.status_code,200,r.text)
        self.assertTrue(self.client.get(self.base+'/area-advice').json()['stale'])

    def test_saved_area_report_expires_when_evidence_review_date_passes(self):
        from datetime import date
        self.ask(self.conversation(),{'lifestyle_priorities':['food']},['Burwood'])
        with patch('server.app.areas.evidence.sydney_today',return_value=date(2030,1,1)):
            result=self.client.get(self.base+'/area-advice').json()
            self.assertTrue(result['stale'])
            self.assertTrue(any('重新核对' in s for s in result['stale_reasons']))

    def test_new_general_intake_with_lifestyle_change_invalidates_shared_area_report(self):
        self.ask(self.conversation(),{'lifestyle_priorities':['parks']},['Rhodes'])
        self.provider.result={'intent':'collect_preferences','brief_patch':{'lifestyle_priorities':['library']}}
        r=self.send(self.conversation(),'new-general-intake','我更看重图书馆，帮我整理租房需求')
        self.assertEqual(r.status_code,200,r.text)
        self.assertTrue(self.client.get(self.base+'/area-advice').json()['stale'])
