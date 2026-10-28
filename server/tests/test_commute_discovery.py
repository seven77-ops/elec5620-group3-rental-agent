"""Full inventory discovery, bounded time-specific queries and explicit variety."""
from copy import deepcopy
from datetime import datetime,timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from server.app.common import now
from server.app.commute.usyd import DESTINATION
from server.tests import test_commute_data as data_harness
from server.tests import test_assistant_commute as chat_harness

Catalog=data_harness.Catalog
row=data_harness.row


def annotated(i):
    item=row(i,'Area'+str(i%7),600+i)
    item['usyd_commute']={'origin':dict(DESTINATION),'modes':{'public_transport':{
        'status':'planned','duration_minutes':10+i/10,'transfers':0,'transit_modes':['bus'],
        'queried_at':now(),'reference_arrival_at':'2026-10-28T09:00:00+11:00',
        'source_url':'https://opendata.transport.nsw.gov.au/dataset/trip-planner-apis'}}}
    return item


class DiscoveryTests(unittest.TestCase):
    def test_all_eligible_houses_and_all_suburbs_are_returned(self):
        from server.app.commute.cached_plan import reference_answer
        catalog=Catalog([annotated(i) for i in range(1,31)])
        result=reference_answer(catalog,{'commute_mode':'public_transport','commute_max_minutes':30},DESTINATION)
        self.assertEqual(len(result['listings']),30)
        self.assertEqual(len(result['commute_recommendation']['areas']),7)
        self.assertEqual(result['commute_recommendation']['matching_count'],30)

    def test_coarse_ranges_join_eligible_list_only_when_upper_bound_satisfies_all_conditions(self):
        from server.app.commute.cached_plan import reference_answer
        coarse=annotated(1);coarse['usyd_commute']={'origin':None,'modes':{},'estimates':{'public_transport':{
            'status':'coarse_estimate','lower_minutes':15,'upper_minutes':29,'typical_minutes':20,
            'queried_at':now(),'reference_arrival_at':'2026-10-28T09:00:00+11:00',
            'source_urls':['https://opendata.transport.nsw.gov.au/dataset/trip-planner-apis']}}}
        catalog=Catalog([coarse]);brief={'commute_mode':'public_transport','commute_max_minutes':30}
        result=reference_answer(catalog,brief,DESTINATION)
        self.assertEqual([r['listing_id'] for r in result['listings']],['domain:1'])
        self.assertEqual(result['listings'][0]['usyd_commute']['estimates'],coarse['usyd_commute']['estimates'])
        for change in ({'commute_max_minutes':25},{'max_transfers':0}):
            self.assertEqual(reference_answer(catalog,{**brief,**change},DESTINATION)['listings'],[])
        self.assertEqual(len(reference_answer(catalog,{**brief,'travel_date':'2099-01-01'},DESTINATION)['listings']),1)

    def test_refresh_changes_first_page_but_preserves_every_match_and_criteria(self):
        from server.app.assistant.commute import prepare
        rows=[annotated(i) for i in range(1,31)]
        brief={'budget_amount':900,'budget_period':'week','budget_scope':'whole_property',
               'min_bedrooms':1,'commute_mode':'public_transport','commute_max_minutes':30}
        def answer(*args):
            return {'intent':'recommend_areas','content':'已筛选','listings':deepcopy(rows),'actions':[],
                    'commute_recommendation':{'criteria':deepcopy(args[1]),'areas':[],'routes':[]}}
        with patch('server.app.assistant.commute.plan_routes',side_effect=answer):
            first,_=prepare(SimpleNamespace(),{'messages':[]},deepcopy(brief),{},'找房',True)
            conversation={'messages':[first]}
            second,_=prepare(SimpleNamespace(),conversation,deepcopy(brief),{},'换一批',True,refresh=True)
        a={r['listing_id'] for r in first['listings'][:12]}
        b={r['listing_id'] for r in second['listings'][:12]}
        self.assertFalse(a&b)
        self.assertEqual({r['listing_id'] for r in first['listings']},{r['listing_id'] for r in second['listings']})
        self.assertEqual(first['commute_recommendation']['criteria'],second['commute_recommendation']['criteria'])
        self.assertEqual(len(second['commute_recommendation']['areas']),7)


class ScheduledRefreshTests(unittest.TestCase):
    setUp=data_harness.PlannerTests.setUp

    def test_scheduled_refresh_checks_new_houses_and_keeps_previous_matching_routes(self):
        self.catalog.rows=[row(i,'Area'+str(i%7),600+i) for i in range(1,31)]
        first=self.planner.prepare(self.brief,DESTINATION,allow_external=True)
        report=first['commute_recommendation'];before={r['listing_id'] for r in report['routes']}
        second=self.planner.prepare(self.brief,DESTINATION,allow_external=True,previous_reports=[report])
        after={r['listing_id'] for r in second['commute_recommendation']['routes']}
        self.assertEqual(len(after-before),12)
        self.assertTrue(before<=after)
        self.assertEqual(len(second['listings']),24)
        changed=self.planner.prepare({**self.brief,'commute_max_minutes':20},DESTINATION,allow_external=True,previous_reports=[report])
        self.assertEqual(changed['listings'],[])

    def test_repeated_refresh_does_not_renew_original_route_expiry(self):
        from datetime import timezone
        self.catalog.rows=[row(i,'Area'+str(i%7),600+i) for i in range(1,31)]
        initial=datetime.now(timezone.utc)
        class Clock(datetime):
            current=initial
            @classmethod
            def now(cls,tz=None):return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)
        with patch('server.app.commute.history.datetime',Clock), patch('server.app.commute.planner.now',side_effect=lambda:Clock.current.isoformat()):
            first=self.planner.prepare(self.brief,DESTINATION,allow_external=True)['commute_recommendation']
            original={r['listing_id'] for r in first['routes']}
            Clock.current=initial+timedelta(minutes=20)
            second=self.planner.prepare(self.brief,DESTINATION,allow_external=True,previous_reports=[first])['commute_recommendation']
            self.assertTrue(original<={r['listing_id'] for r in second['routes']})
            Clock.current=initial+timedelta(minutes=40)
            third=self.planner.prepare(self.brief,DESTINATION,allow_external=False,previous_reports=[second])
        self.assertFalse(original & {r['listing_id'] for r in third['listings']})
        reused=next(r for r in second['routes'] if r['listing_id'] in original)
        self.assertEqual(reused['queried_at'],initial.isoformat())

    def test_stale_or_other_catalog_reports_cannot_skip_or_authorize_houses(self):
        self.catalog.rows=[row(i,'Area'+str(i%7),600+i) for i in range(1,31)]
        report=self.planner.prepare(self.brief,DESTINATION,allow_external=True)['commute_recommendation']
        for changes in ({'catalog_fingerprint':'different'}, {'queried_at':'2000-01-01T00:00:00Z'},
                        {'destination':{**DESTINATION,'id':'camden'}}):
            result=self.planner.prepare(self.brief,DESTINATION,allow_external=True,previous_reports=[{**report,**changes}])
            self.assertEqual(len(result['commute_recommendation']['routes']),12)


class RefreshIntentTests(unittest.TestCase):
    setUp=chat_harness.AssistantCommuteTests.setUp
    conversation=chat_harness.AssistantCommuteTests.conversation
    send=chat_harness.AssistantCommuteTests.send
    recommend=chat_harness.AssistantCommuteTests.recommend
    ready_brief=chat_harness.AssistantCommuteTests.ready_brief

    def test_natural_language_refresh_preserves_constraints_and_rotates_results(self):
        brief=self.ready_brief();brief.pop('arrival_time');brief.pop('travel_day')
        first=self.recommend(self.conversation(),brief,allow_external_data=True).json()
        self.provider.result={'intent':'recommend_areas','refresh_recommendations':True}
        response=self.send(first,'refresh','再给我换一下其他推荐',allow_external_data=True)
        self.assertEqual(response.status_code,200,response.text)
        second=response.json()
        self.assertEqual(first['rental_brief'],second['rental_brief'])
        a=first['messages'][-1]['listings'];b=second['messages'][-1]['listings']
        self.assertGreater(len(a),12)
        self.assertNotEqual([r['listing_id'] for r in a[:12]],[r['listing_id'] for r in b[:12]])
        self.assertEqual({r['listing_id'] for r in a},{r['listing_id'] for r in b})

    def test_rephrased_repeat_with_unchanged_requirements_also_rotates_the_first_page(self):
        brief=self.ready_brief();brief.pop('arrival_time');brief.pop('travel_day')
        first=self.recommend(self.conversation(),brief,allow_external_data=True).json()
        response=self.recommend(first,{},'another-way','按这些条件再帮我推荐房源',allow_external_data=True)
        self.assertEqual(response.status_code,200,response.text)
        second=response.json()
        self.assertEqual(first['rental_brief'],second['rental_brief'])
        self.assertNotEqual([r['listing_id'] for r in first['messages'][-1]['listings'][:12]],
                            [r['listing_id'] for r in second['messages'][-1]['listings'][:12]])

    def test_complete_inventory_is_not_resent_to_model_for_a_short_followup(self):
        brief=self.ready_brief();brief.pop('arrival_time');brief.pop('travel_day')
        first=self.recommend(self.conversation(),brief,allow_external_data=True).json()
        self.assertGreater(len(first['messages'][-1]['listings']),12)
        response=self.recommend(first,{},'short-followup','再推荐一下',allow_external_data=True)
        self.assertEqual(response.status_code,200,response.text)
        self.assertLessEqual(len(self.provider.inputs[-1]['displayed_listings']),12)
