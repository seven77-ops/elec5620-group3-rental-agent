"""Partial saved-field edits retain explicitly supplied working housing requirements."""
from copy import deepcopy
import unittest
from server.tests import test_assistant_api as harness
from server.app.assistant.recommendation_options import filters_for
from server.app.real_data.catalog import RealCatalog


class PreferenceUpdateContextTests(unittest.TestCase):
    setUp = harness.AssistantTests.setUp
    conversation = harness.AssistantTests.conversation
    send = harness.AssistantTests.send
    apply = harness.AssistantTests.apply

    def seeded(self, commute=True):
        c = self.conversation()
        self.before = {'budget_amount':900,'budget_period':'week','budget_scope':'whole_property',
            'suburb':None,'min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':0,'occupants':2}
        if commute:
            self.before.update(commute_mode='public_transport',commute_max_minutes=50,
                max_transfers=2,commute_preference='include',recommend_areas=True)
        c.update(rental_brief=deepcopy(self.before),last_search_filters=filters_for(self.before),
            dialogue_mode='recommend_areas' if commute else 'search')
        with self.client.app.state.repository.transaction() as db:
            self.client.app.state.repository.put(db,'assistant_conversation',c['conversation_id'],c)
        return c

    def propose(self,c,patch):
        self.provider.result={'intent':'update_preferences','preference_patch':patch}
        r=self.send(c,'budget-edit','Change only my maximum budget to AUD 1000 per week. Keep all my other requirements unchanged.')
        self.assertEqual(r.status_code,200,r.text)
        proposed=r.json()
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)
        action=proposed['messages'][-1]['actions'][0]
        return proposed,action

    def test_budget_only_update_preserves_unconfirmed_rooms_commute_and_actual_results(self):
        c,action=self.propose(self.seeded(),{'budget':{'maximum':1000}})
        summary=' '.join(action['summary'])
        self.assertIn('At least 2 bedrooms',summary)
        self.assertIn('At least 2 bathrooms',summary)
        self.assertIn('50',summary)
        response=self.apply(action['proposal_id']);self.assertEqual(response.status_code,200,response.text)
        result=response.json();profile=result['case']['draft']['profile'];current=result['conversation']
        self.assertEqual(profile['housing_preferences']['min_bedrooms'],2)
        self.assertEqual(profile['housing_preferences']['min_bathrooms'],2)
        self.assertEqual(profile['student_commute'],{'mode':'public_transport','maximum_minutes':50,'max_transfers':2})
        self.assertEqual(profile['budget']['scope'],'whole_property')
        expected={**filters_for(self.before),'max_weekly_rent':1000}
        expected=RealCatalog().filters(expected)
        self.assertEqual(current['last_search_filters'],expected)
        rows=current['messages'][-1]['listings'];self.assertTrue(rows)
        self.assertTrue(all(r['bedrooms']>=2 and r['bathrooms']>=2 and r['weekly_rent']<=1000 for r in rows))
        from server.app.commute.matching import reference_matches
        self.assertTrue(all(reference_matches(r,expected) for r in rows))
        self.assertEqual({r['listing_id'] for r in rows},{r['listing_id'] for r in RealCatalog().matching(expected)})
        self.assertEqual(current['messages'][-1]['recommendation_filters'],expected)
        path=self.base+'/conversations/'+current['conversation_id']
        self.assertEqual(self.client.get(path).json(),current)
        self.assertEqual(self.apply(action['proposal_id']).json(),result)

    def test_non_commute_working_rooms_and_suburb_survive_budget_only_edit(self):
        c=self.seeded(commute=False);c['rental_brief']['suburb']='Burwood'
        with self.client.app.state.repository.transaction() as db:
            self.client.app.state.repository.put(db,'assistant_conversation',c['conversation_id'],c)
        proposed,action=self.propose(c,{'budget':{'maximum':1000}})
        self.assertEqual(proposed['rental_brief']['min_bathrooms'],2)
        response=self.apply(action['proposal_id']);self.assertEqual(response.status_code,200,response.text)
        current=response.json()['conversation']
        self.assertEqual(current['last_search_filters']['suburb'],'Burwood')
        self.assertEqual(current['last_search_filters']['min_bathrooms'],2)
        self.assertNotIn('usyd_mode',current['last_search_filters'])
        self.assertTrue(all(r['suburb']=='Burwood' and r['bedrooms']>=2 and r['bathrooms']>=2 for r in current['messages'][-1]['listings']))

    def test_explicit_room_change_overrides_only_that_working_value(self):
        proposed,action=self.propose(self.seeded(),{'housing_preferences':{'min_bedrooms':1}})
        response=self.apply(action['proposal_id']);self.assertEqual(response.status_code,200,response.text)
        profile=response.json()['case']['draft']['profile']
        self.assertEqual(profile['housing_preferences']['min_bedrooms'],1)
        self.assertEqual(profile['housing_preferences']['min_bathrooms'],2)
        self.assertEqual(profile['budget']['maximum'],900)
        self.assertEqual(profile['student_commute']['maximum_minutes'],50)

    def test_incomplete_working_brief_does_not_invent_missing_fields(self):
        c=self.conversation();c['rental_brief']={'min_bedrooms':2,'suburb':'Burwood'}
        with self.client.app.state.repository.transaction() as db:
            self.client.app.state.repository.put(db,'assistant_conversation',c['conversation_id'],c)
        _,action=self.propose(c,{'budget':{'maximum':1000}})
        response=self.apply(action['proposal_id']);self.assertEqual(response.status_code,200,response.text)
        profile=response.json()['case']['draft']['profile']
        self.assertEqual(profile['housing_preferences']['min_bedrooms'],2)
        self.assertNotIn('min_bathrooms',profile['housing_preferences'])
        self.assertNotIn('student_commute',profile)
        self.assertNotIn('scope',profile['budget'])
        self.assertNotIn('occupants',profile)

    def test_filter_only_search_also_retains_its_explicit_room_and_commute_constraints(self):
        c=self.seeded();c['rental_brief']={};c['dialogue_mode']='search'
        with self.client.app.state.repository.transaction() as db:
            self.client.app.state.repository.put(db,'assistant_conversation',c['conversation_id'],c)
        _,action=self.propose(c,{'budget':{'maximum':1000}})
        response=self.apply(action['proposal_id']);self.assertEqual(response.status_code,200,response.text)
        filters=response.json()['conversation']['last_search_filters']
        self.assertEqual(filters['min_bedrooms'],2)
        self.assertEqual(filters['min_bathrooms'],2)
        self.assertEqual(filters['usyd_max_minutes'],50)
        self.assertEqual(filters['usyd_max_transfers'],2)
        self.assertEqual(filters['max_weekly_rent'],1000)
