"""Rental discovery uses approximate duration, never a class-time deadline."""
from copy import deepcopy
import tempfile, unittest
from unittest.mock import patch
from server.app.adapters.services import Services
from server.app.adapters.real_agent2 import RealProfilesAdapter
from server.app.adapters.favorites import FavoritesAdapter
from server.app.assistant.workspace import AssistantWorkspace
from server.app.assistant.service import message
from server.app.settings import Settings
from server.app.real_data.preferences import preference_context
from server.app.commute.matching import matching_for_case
from server.app.commute.usyd import DESTINATION


class TimelessCommuteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ctx=Services(Settings(runtime_dir=self.temp.name))
        self.catalog=self.ctx.settings.catalog
        self.adapter=RealProfilesAdapter(self.ctx)
        self.case=self.adapter.create_case({});self.cid=self.case['case_id']
        self.filters={'usyd_mode':'public_transport','usyd_max_minutes':30}
        self.legacy={'usyd_arrival_time':'03:17','usyd_travel_day':'weekend','usyd_travel_date':'2000-01-01'}
        self.row=self.catalog.matching(self.filters)[0]
        profile=deepcopy(self.case['draft']['profile'])
        profile['student_commute']={'mode':'public_transport','maximum_minutes':30,
            'arrival_time':'03:17','travel_day':'weekend','travel_date':'2000-01-01'}
        self.case=self.adapter.draft(self.cid,{'expected_revision':self.case['draft']['revision'],'profile':profile})
        self.case=self.adapter.confirm(self.cid,{'draft_revision':self.case['draft']['revision'],
            'fingerprint':self.case['draft']['fingerprint'],'review_token':self.case['agent1']['review_token']})

    def test_old_clock_and_date_never_change_catalog_or_case_matches(self):
        expected={r['listing_id'] for r in self.catalog.matching(self.filters)}
        self.assertTrue(expected)
        self.assertEqual({r['listing_id'] for r in self.catalog.matching({**self.filters,**self.legacy})},expected)
        self.assertEqual({r['listing_id'] for r in matching_for_case(self.ctx,self.cid,{**self.filters,**self.legacy})},expected)

    def test_confirmed_legacy_profile_maps_only_duration_mode_and_transfer_limit(self):
        context=preference_context(self.case['confirmations'][-1]['profile'],self.catalog)
        self.assertEqual(context['filters'],{**self.filters,'sort':'rent_asc'})
        self.assertNotIn('03:17',str(context))

    def test_selecting_from_chat_and_favorites_never_queries_a_specific_departure(self):
        workspace=AssistantWorkspace(self.ctx)
        c=workspace.assistant.create(self.cid,{})
        c['messages']=[message('assistant','历史房源','agent2',listings=[self.row])]
        with self.ctx.repo.transaction() as db:workspace.assistant.save(db,c)
        body={'request_id':'choose','listing_id':self.row['listing_id'],'confirmed':True,
            'expected_profile_fingerprint':self.case['draft']['fingerprint'],'allow_external_data':True}
        with patch.object(self.ctx.transit_provider,'trips',side_effect=AssertionError('No scheduled lookup')):
            selected=FavoritesAdapter(self.ctx).select(self.cid,body)
            self.assertEqual(selected['listing_id'],self.row['listing_id'])
            result=workspace.select(self.cid,c['conversation_id'],{**body,'expected_revision':c['revision']})
            self.assertEqual(result['case']['selection']['listing_id'],self.row['listing_id'])
        # Read compatibility does not rewrite the user's historical confirmation.
        self.assertEqual(self.adapter.read_case(self.cid)['confirmations'],self.case['confirmations'])

    def test_legacy_chat_brief_produces_all_reference_matches_without_network(self):
        from server.app.assistant.commute import prepare
        brief={'suburb':None,'budget_amount':1500,'budget_period':'week','budget_scope':'whole_property',
            'min_bedrooms':1,'min_bathrooms':1,'min_car_spaces':0,'occupants':1,'rental_mode':'whole_property',
            'commute_mode':'public_transport','commute_max_minutes':30,'arrival_time':'03:17',
            'travel_day':'weekend','travel_date':'2000-01-01'}
        with patch.object(self.ctx.transit_provider,'trips',side_effect=AssertionError('No scheduled lookup')):
            result,_=prepare(self.ctx,{'messages':[]},brief,{},'find a home',True)
        self.assertTrue(result['listings'])
        criteria=result['commute_recommendation']['criteria']
        for key in ('arrival_time','travel_day','travel_date'):self.assertNotIn(key,criteria)

    def test_no_fabricated_average_or_relaxed_duration_limit(self):
        rows=matching_for_case(self.ctx,self.cid,{**self.filters,**self.legacy})
        from server.app.commute.snapshot import observation
        from server.app.commute.estimates import estimate_for
        for row in rows:
            route=observation(row,'public_transport')
            if route:self.assertLessEqual(route['duration_minutes'],30)
            else:self.assertLessEqual(estimate_for(row,'public_transport')['upper_minutes'],30)

    def test_new_requirements_and_summaries_drop_clock(self):
        from server.app.assistant.dialogue import merge_brief,brief_profile_patch,profile_brief
        from server.app.assistant.tools import preference_summary
        brief=merge_brief({'rental_brief':{'arrival_time':'03:17','commute_mode':'public_transport',
            'commute_max_minutes':30}}, {'intent':'search','filters':self.legacy})
        self.assertNotIn('arrival_time',brief)
        self.assertNotIn('arrival_time',profile_brief(self.case['confirmations'][-1]['profile']))
        self.assertNotIn('03:17',' '.join(preference_summary(self.case['confirmations'][-1]['profile'])))

    def test_historical_over_limit_card_explains_actual_duration_without_class_time(self):
        from server.app.common import ApiError
        from server.app.commute.snapshot import observation
        row=next(r for r in self.catalog.matching({'suburb':'Rhodes','max_weekly_rent':900,'min_bedrooms':2})
            if observation(r,'public_transport') and observation(r,'public_transport')['duration_minutes']>30)
        workspace=AssistantWorkspace(self.ctx);c=workspace.assistant.create(self.cid,{})
        c['messages']=[message('assistant','历史预算房源','agent2',listings=[row])]
        with self.ctx.repo.transaction() as db:workspace.assistant.save(db,c)
        with self.assertRaises(ApiError) as error:
            workspace.select(self.cid,c['conversation_id'],{'request_id':'outside','listing_id':row['listing_id'],
                'confirmed':True,'expected_revision':c['revision'],'expected_profile_fingerprint':self.case['draft']['fingerprint']})
        self.assertEqual(error.exception.code,'listing_outside_requirements')
        self.assertIn(f"{observation(row,'public_transport')['duration_minutes']:g}",error.exception.message)
        self.assertIn('30',error.exception.message)
        self.assertNotIn('到校时刻',error.exception.message)
        self.assertIsNone(self.adapter.read_case(self.cid)['selection'])

    def test_favorite_with_over_limit_range_reports_the_range(self):
        from server.app.common import ApiError
        from server.app.commute.snapshot import observation
        from server.app.commute.estimates import estimate_for
        row=next(r for r in self.catalog.matching({'suburb':'Rhodes'}) if not observation(r,'public_transport')
            and estimate_for(r,'public_transport') and estimate_for(r,'public_transport')['upper_minutes']>30)
        value=estimate_for(row,'public_transport')
        with self.assertRaises(ApiError) as error:
            FavoritesAdapter(self.ctx).select(self.cid,{'request_id':'range','listing_id':row['listing_id'],
                'confirmed':True,'expected_profile_fingerprint':self.case['draft']['fingerprint']})
        self.assertIn(f"{value['lower_minutes']:g}–{value['upper_minutes']:g}",error.exception.message)
        self.assertNotIn('到校时刻',error.exception.message)
        self.assertIsNone(self.adapter.read_case(self.cid)['selection'])
