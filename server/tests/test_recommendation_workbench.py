"""Working requirements, real counts, grounded reasons and timeless reports."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import tempfile
import unittest

from server.app.adapters.services import Services
from server.app.adapters.real_agent2 import RealProfilesAdapter
from server.app.assistant.service import AssistantService, signature, message
from server.app.settings import Settings
from server.app.common import ApiError


class RecommendationWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.ctx = Services(Settings(runtime_dir=self.temp.name))
        self.catalog = self.ctx.settings.catalog
        self.case = RealProfilesAdapter(self.ctx).create_case({})
        self.cid = self.case['case_id']
        self.assistant = AssistantService(self.ctx)
        self.c = self.assistant.create(self.cid,{})
        self.brief = {'budget_amount':900,'budget_period':'week','budget_scope':'whole_property',
            'min_bedrooms':2,'min_bathrooms':1,'suburb':'Burwood','commute_mode':'public_transport','commute_max_minutes':30}
        self.c.update(rental_brief=deepcopy(self.brief),dialogue_mode='recommend_areas')
        with self.ctx.repo.transaction() as db: self.assistant.save(db,self.c)

    def workbench(self):
        from server.app.assistant.recommendation_workspace import RecommendationWorkspace
        return RecommendationWorkspace(self.ctx)

    def request(self, patch, request='adjust-1', revision=0):
        return {'request_id':request,'expected_revision':revision,
            'expected_profile_fingerprint':self.case['draft']['fingerprint'],
            'catalog_fingerprint':self.catalog.fingerprint,'confirmed':True,'patch':patch}

    def test_single_condition_alternatives_are_real_counts_and_read_only(self):
        self.c['rental_brief'].update(budget_amount=1)
        with self.ctx.repo.transaction() as db: self.assistant.save(db,self.c)
        before = deepcopy(self.assistant.read(self.cid,self.c['conversation_id']))
        context = self.workbench().read(self.cid,self.c['conversation_id'])
        self.assertEqual(context['total'],0)
        self.assertTrue(context['alternatives'])
        for option in context['alternatives']:
            self.assertEqual(len(option['patch']),1)
            changed = deepcopy(context['filters'])
            mapping = {'budget_amount':'max_weekly_rent','commute_max_minutes':'usyd_max_minutes','suburb':'suburb'}
            for key,value in option['patch'].items():
                if value is None: changed.pop(mapping[key],None)
                else: changed[mapping[key]]=value
            self.assertEqual(option['count'],len(self.catalog.matching(changed)))
        self.assertEqual(self.assistant.read(self.cid,self.c['conversation_id']),before)

    def test_adjust_replays_preserves_other_conditions_and_does_not_save_profile(self):
        service = self.workbench(); body=self.request({'commute_max_minutes':60})
        updated=service.adjust(self.cid,self.c['conversation_id'],body)
        from server.app.commute.usyd import student_brief
        self.assertEqual(updated['rental_brief'],student_brief({**self.brief,'commute_max_minutes':60,'recommend_areas':True}))
        report=updated['messages'][-1]
        self.assertEqual(report['recommendation_change']['before_count'],len(self.catalog.matching(service.filters(self.brief))))
        self.assertEqual(report['recommendation_change']['after_count'],len(report['listings']))
        self.assertEqual(service.adjust(self.cid,self.c['conversation_id'],body),updated)
        with self.ctx.repo.transaction() as db: self.assertEqual(self.ctx.get(db,'case',self.cid),self.case)

    def test_conflicts_ownership_and_validation(self):
        service=self.workbench()
        for body,code in ((self.request({'arrival_time':'09:00'}),'invalid_input'),
                          (self.request({'commute_max_minutes':999}),'invalid_input'),
                          ({**self.request({'budget_amount':1000}),'confirmed':False},'confirmation_required'),
                          (self.request({'budget_amount':1000},revision=7),'conversation_conflict'),
                          ({**self.request({'budget_amount':1000}),'catalog_fingerprint':'old'},'stale_catalog')):
            with self.assertRaises(ApiError) as error: service.adjust(self.cid,self.c['conversation_id'],body)
            self.assertEqual(error.exception.code,code)
        other=RealProfilesAdapter(self.ctx).create_case({})['case_id']
        with self.assertRaises(ApiError) as error: service.read(other,self.c['conversation_id'])
        self.assertEqual(error.exception.code,'not_found')

    def test_catalog_preview_is_read_only_and_preserves_every_other_filter(self):
        filters={'max_weekly_rent':1,'suburb':'Burwood','min_bedrooms':2,'usyd_mode':'public_transport','usyd_max_minutes':30}
        result=self.workbench().preview(self.cid,{'filters':filters})
        self.assertEqual(result['total'],0)
        self.assertEqual(result['filters'],self.catalog.filters(filters))
        self.assertTrue(result['alternatives'])
        with self.ctx.repo.transaction() as db:self.assertEqual(self.ctx.get(db,'case',self.cid),self.case)

    def test_reference_report_does_not_expire_after_thirty_minutes(self):
        from server.app.assistant.commute import latest
        from server.app.commute.cached_plan import reference_answer
        from server.app.commute.usyd import DESTINATION
        answer = reference_answer(self.catalog,self.brief,DESTINATION)
        report = {'conversation_id':self.c['conversation_id'],'conversation_revision':0,
            'case_signature':signature(self.case),'catalog_fingerprint':self.catalog.fingerprint,
            'brief':self.brief,'created_at':(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(),
            'message':message('assistant',**answer)}
        with self.ctx.repo.transaction() as db: self.ctx.repo.put(db,'assistant_commute_report',self.cid,report)
        self.assertFalse(latest(self.ctx,self.cid)['stale'])
