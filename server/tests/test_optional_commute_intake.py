"""Optional commute intake uses explicit choices and never saves without confirmation."""
from copy import deepcopy
import unittest
from server.tests import test_assistant_api as harness

BASIC={'suburb':None,'budget_amount':900,'budget_period':'week','budget_scope':'whole_property',
       'occupants':1,'min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':0,'rental_mode':'whole_property'}


class OptionalCommuteIntakeTests(unittest.TestCase):
    setUp=harness.AssistantTests.setUp
    conversation=harness.AssistantTests.conversation
    send=harness.AssistantTests.send
    apply=harness.AssistantTests.apply

    def start(self,**patch):
        self.provider.result={'intent':'collect_preferences','brief_patch':{**BASIC,**patch}}
        r=self.send(self.conversation(),'basic','Any suburb, whole property, AUD 900 per week, one person, two bedrooms and bathrooms, no parking.')
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def turn(self,c,text,patch=None):
        self.provider.result={'intent':'collect_preferences','brief_patch':patch or {}}
        r=self.send(c,'turn-'+str(c['revision']),text)
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def seed_saved_commute(self):
        root='/api/v1/cases/'+self.case['case_id']
        profile={**self.case['draft']['profile'],'student_commute':{'mode':'train','maximum_minutes':40,'max_transfers':1}}
        r=self.client.post(root+'/profile-drafts',json={'expected_revision':self.case['draft']['revision'],'profile':profile})
        self.assertEqual(r.status_code,200,r.text)
        self.case=r.json()
        return deepcopy(self.case)

    def test_any_suburb_offers_one_optional_choice_before_cards(self):
        c=self.start();answer=c['messages'][-1]
        self.assertIs(answer.get('commute_preference_question'),True)
        self.assertEqual(answer['listings'],[])
        self.assertEqual(answer['actions'],[])
        self.assertNotIn('commute_question',answer)
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),self.case)

    def test_concrete_suburb_proceeds_without_mandatory_commute(self):
        c=self.start(suburb='Burwood');answer=c['messages'][-1]
        self.assertTrue(answer['listings'])
        self.assertNotIn('commute_preference_question',answer)
        self.assertNotIn('commute_question',answer)
        self.assertTrue(all(r['suburb']=='Burwood' for r in answer['listings']))

    def test_include_button_is_deterministic_then_asks_only_missing_slots(self):
        c=self.start();before=len(self.provider.inputs);self.provider.fail=True
        c=self.turn(c,'Yes, I would like to filter by commute.')
        self.assertEqual(len(self.provider.inputs),before)
        self.assertEqual(c['rental_brief']['commute_preference'],'include')
        self.assertEqual(c['messages'][-1]['commute_question']['fields'],['commute_max_minutes'])
        self.provider.fail=False
        c=self.turn(c,'At most 35 minutes',{'commute_max_minutes':35})
        self.assertEqual(c['messages'][-1]['commute_question']['fields'],['commute_mode'])
        c=self.turn(c,'train',{'commute_mode':'train'})
        self.assertEqual(c['rental_brief']['commute_max_minutes'],35)
        self.assertNotIn('commute_preference_question',c['messages'][-1])

    def test_skip_persists_through_reload_followup_and_confirmation(self):
        c=self.start();before=len(self.provider.inputs);self.provider.fail=True
        c=self.turn(c,'No commute filter, please.')
        self.assertEqual(len(self.provider.inputs),before)
        self.assertEqual(c['rental_brief']['commute_preference'],'skip')
        self.assertTrue(c['messages'][-1]['listings'])
        c=self.client.get(self.base+'/conversations/'+c['conversation_id']).json()
        self.provider.fail=False
        c=self.turn(c,'Increase the budget to 950.',{'budget_amount':950})
        self.assertEqual(c['rental_brief']['commute_preference'],'skip')
        self.assertNotIn('commute_preference_question',c['messages'][-1])
        action=next(a for a in c['messages'][-1]['actions'] if a['type']=='apply_preferences')
        saved=self.apply(action['proposal_id']);self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(saved.json()['conversation']['rental_brief']['commute_preference'],'skip')
        self.assertNotIn('student_commute',saved.json()['case']['draft']['profile'])

    def test_skip_removes_old_active_and_saved_filters_only_on_confirmation(self):
        original=self.seed_saved_commute();c=self.start()
        self.assertEqual(c['rental_brief']['commute_max_minutes'],40)
        # An already stated requirement is retained, so no optional-choice turn is needed.
        self.assertNotIn('commute_preference_question',c['messages'][-1])
        c=self.turn(c,'No commute filter, please.')
        brief=c['rental_brief']
        for key in ('commute_mode','commute_max_minutes','max_transfers','recommend_areas','destination_id'):
            self.assertNotIn(key,brief)
        self.assertFalse(any(k.startswith('usyd_') for k in c['last_search_filters']))
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),original)
        action=next(a for a in c['messages'][-1]['actions'] if a['type']=='apply_preferences')
        self.assertEqual(self.apply(action['proposal_id'],confirmed=False).status_code,422)
        saved=self.apply(action['proposal_id']);self.assertEqual(saved.status_code,200,saved.text)
        self.assertNotIn('student_commute',saved.json()['case']['draft']['profile'])

    def test_natural_known_suburb_optout_overrides_commute_misroute(self):
        self.provider.result={'intent':'recommend_areas','brief_patch':{**BASIC,'suburb':'Burwood'}}
        r=self.send(self.conversation(),'known','I only want Burwood. I already know the commute and do not need a commute filter.')
        self.assertEqual(r.status_code,200,r.text);c=r.json()
        self.assertEqual(c['rental_brief']['commute_preference'],'skip')
        self.assertTrue(c['messages'][-1]['listings'])
        self.assertNotIn('commute_question',c['messages'][-1])

    def test_skip_prevents_saved_commute_from_reappearing_in_one_off_search(self):
        original=self.seed_saved_commute();c=self.start()
        c=self.turn(c,'No commute filter, please.')
        self.provider.result={'intent':'search','filters':{'max_weekly_rent':950}}
        r=self.send(c,'search-after-skip','Show listings up to 950 per week.')
        self.assertEqual(r.status_code,200,r.text);c=r.json()
        self.assertEqual(c['rental_brief']['commute_preference'],'skip')
        self.assertFalse(any(k.startswith('usyd_') for k in c['last_search_filters']))
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),original)

    def test_legacy_search_constraints_are_retained_until_explicit_skip(self):
        c=self.conversation();repo=self.client.app.state.repository
        with repo.transaction() as db:
            stored=repo.get(db,'assistant_conversation',c['conversation_id'])
            stored['last_search_filters']={'usyd_mode':'train','usyd_max_minutes':40,'usyd_max_transfers':0}
            repo.put(db,'assistant_conversation',c['conversation_id'],stored)
        self.provider.result={'intent':'collect_preferences','brief_patch':BASIC}
        r=self.send(c,'restore-old-commute','Keep the existing commute requirements and use this budget.')
        self.assertEqual(r.status_code,200,r.text);c=r.json()
        self.assertEqual(c['rental_brief']['commute_max_minutes'],40)
        self.assertEqual(c['rental_brief']['max_transfers'],0)
        c=self.turn(c,'No commute filter, please.')
        self.assertFalse(any(k.startswith('usyd_') for k in c['last_search_filters']))
        self.assertNotIn('max_transfers',c['rental_brief'])

    def test_requirements_save_omission_retains_saved_commute_in_active_filters(self):
        original=self.seed_saved_commute();c=self.start()
        body={'request_id':'keep-commute','expected_revision':c['revision'],
              'expected_profile_fingerprint':original['draft']['fingerprint'],'confirmed':True,'brief':BASIC}
        r=self.client.post(self.base+'/conversations/'+c['conversation_id']+'/requirements',json=body)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['case']['draft']['profile']['student_commute']['maximum_minutes'],40)
        self.assertEqual(r.json()['conversation']['rental_brief'].get('commute_max_minutes'),40)
        self.assertEqual(r.json()['conversation']['last_search_filters']['usyd_max_minutes'],40)

    def test_skip_normalization_does_not_bypass_request_validation(self):
        c=self.start();root='/api/v1/cases/'+self.case['case_id']
        body={'request_id':'invalid-skip','expected_revision':c['revision'],
              'expected_profile_fingerprint':self.case['draft']['fingerprint'],'confirmed':True,
              'brief':{**BASIC,'commute_preference':'skip','commute_max_minutes':'invalid'}}
        r=self.client.post(self.base+'/conversations/'+c['conversation_id']+'/requirements',json=body)
        self.assertEqual(r.status_code,422,r.text)
        self.assertEqual(self.client.get(root).json(),self.case)

    def test_requirements_save_normalizes_skip_with_old_saved_and_form_constraints(self):
        original=self.seed_saved_commute();c=self.start()
        path=self.base+'/conversations/'+c['conversation_id']+'/requirements'
        body={'request_id':'save-skip','expected_revision':c['revision'],
              'expected_profile_fingerprint':original['draft']['fingerprint'],'confirmed':True,
              'brief':{**BASIC,'commute_preference':'skip','commute_mode':'train','commute_max_minutes':40,'max_transfers':0}}
        denied=self.client.post(path,json={**body,'confirmed':False})
        self.assertEqual(denied.status_code,422,denied.text)
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),original)
        saved=self.client.post(path,json=body);self.assertEqual(saved.status_code,200,saved.text)
        self.assertNotIn('student_commute',saved.json()['case']['draft']['profile'])
        actual=saved.json()['conversation']
        self.assertEqual(actual['rental_brief']['commute_preference'],'skip')
        self.assertNotIn('commute_mode',actual['rental_brief'])
        self.assertFalse(any(k.startswith('usyd_') for k in actual['last_search_filters']))
        self.assertEqual(self.client.post(path,json=body).json(),saved.json())

    def test_prepare_skip_normalizes_stale_fields_without_saving_profile(self):
        original=self.seed_saved_commute();c=self.start()
        path=self.base+'/conversations/'+c['conversation_id']+'/proposals'
        body={'request_id':'prepare-skip','expected_revision':c['revision'],
              'expected_profile_fingerprint':original['draft']['fingerprint'],
              'brief':{**BASIC,'commute_preference':'skip','commute_mode':'train','commute_max_minutes':40}}
        prepared=self.client.post(path,json=body);self.assertEqual(prepared.status_code,200,prepared.text)
        self.assertNotIn('commute_mode',prepared.json()['conversation']['rental_brief'])
        self.assertEqual(self.client.get('/api/v1/cases/'+self.case['case_id']).json(),original)
        saved=self.apply(prepared.json()['proposal_id']);self.assertEqual(saved.status_code,200,saved.text)
        self.assertNotIn('student_commute',saved.json()['case']['draft']['profile'])

    def test_skip_is_authoritative_over_stale_form_fields(self):
        from server.app.assistant.dialogue import brief_filters,brief_profile_patch
        from server.app.assistant.recommendation_options import filters_for,criteria_for
        brief={**BASIC,'commute_preference':'skip','commute_mode':'train','commute_max_minutes':40,'max_transfers':0}
        self.assertFalse(any(k.startswith('usyd_') for k in brief_filters(brief)))
        self.assertFalse(any(k.startswith('usyd_') for k in filters_for(brief)))
        self.assertNotIn('student_commute',brief_profile_patch(brief))
        self.assertNotIn('commute_mode',criteria_for(filters_for(brief),brief))

    def test_explicit_negative_commute_filter_phrases_are_optouts(self):
        from server.app.assistant.commute_choice import stated_choice
        for text in ("I do not want to filter by commute.","I don't need to filter by commute.",'通勤不用筛选'):
            with self.subTest(text=text):self.assertEqual(stated_choice(text),'skip')
        self.assertIsNone(stated_choice('Do not remove my existing commute filter.'))

    def test_explicit_one_off_search_does_not_require_optional_choice(self):
        self.provider.result={'intent':'search','filters':{'max_weekly_rent':900,'min_bedrooms':2}}
        r=self.send(self.conversation(),'preview','Just search for two-bedroom homes up to 900 per week without saving.')
        self.assertEqual(r.status_code,200,r.text)
        self.assertTrue(r.json()['messages'][-1]['listings'])
        self.assertNotIn('commute_preference_question',r.json()['messages'][-1])

    def test_explicit_commute_requirement_needs_no_optional_choice(self):
        c=self.start(commute_max_minutes=30)
        self.assertEqual(c['messages'][-1]['commute_question']['fields'],['commute_mode'])
        self.assertNotIn('commute_preference_question',c['messages'][-1])
