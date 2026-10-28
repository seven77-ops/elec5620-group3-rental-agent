"""Public utility observations are durable, scoped and used without inventing prices."""
import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from contextlib import closing
from pathlib import Path

from server.app.living.utility_catalog import UtilityPlanCatalog
from server.app.living.utility_advice import advise


def internet(identifier, ongoing, intro=None, expires=None):
    return {'id':identifier,'provider_id':'tpg','category':'internet','name':identifier,
        'source_url':'https://www.tpg.com.au/nbn','observed_at':'2026-10-28T10:00:00+11:00',
        'valid_from':None,'valid_to':None,'currency':'AUD','conditions':['按地址确认接入'],
        'pricing':{'monthly_aud':ongoing,'intro_monthly_aud':intro,'intro_months':6 if intro else 0,
                   'offer_ends_on':expires,'download_mbps':50,'upload_mbps':17,'technology':['FTTP','HFC'],
                   'data_allowance':'unlimited','hardware_notes':'路由器费用另计'}}


class UtilityPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.seed=self.root/'seed.json';self.db=self.root/'utility_catalog.sqlite3'
        self.value={'schema_version':1,'checked_on':'2026-10-28','plans':[
            internet('cheap-ongoing',75,65),internet('cheap-promo',95,55,'2026-11-02')]}
        self.seed.write_text(json.dumps(self.value))
        self.catalog=UtilityPlanCatalog(self.db,seed_path=self.seed)

    def test_seed_is_in_sqlite_and_is_idempotent_with_immutable_snapshots(self):
        self.assertTrue(self.db.is_file())
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM utility_plans').fetchone()[0],2)
        UtilityPlanCatalog(self.db,seed_path=self.seed)
        changed=deepcopy(self.value);changed['plans'][0]['pricing']['monthly_aud']=77
        self.seed.write_text(json.dumps(changed));new=UtilityPlanCatalog(self.db,seed_path=self.seed)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM utility_snapshots').fetchone()[0],2)
        self.assertEqual(next(p for p in new.search(on='2026-10-28') if p['id']=='cheap-ongoing')['pricing']['monthly_aud'],77)

    def test_budget_uses_ongoing_price_not_temporary_promotion(self):
        result=advise(self.catalog,'网络每月80以内，50Mbps',category='internet',on='2026-10-28')
        self.assertEqual([p['id'] for p in result['plans']],['cheap-ongoing'])
        self.assertIn('恢复原价',result['content'])
        p=result['plans'][0];self.assertEqual(p['first_year_base_cost_aud'],840)
        self.assertIn('路由器',result['content'])
        self.assertEqual(result['availability'],'address_unconfirmed')

    def test_internet_budget_shorthand_is_treated_as_monthly_with_explicit_copy(self):
        result=advise(self.catalog,'推荐宽带，预算80以内',category='internet',on='2026-10-28')
        self.assertEqual(result['criteria']['max_monthly_aud'],80)
        self.assertIn('月预算',result['content'])

    def test_explicit_nbn_request_never_substitutes_a_5g_plan(self):
        wireless=internet('wireless',60,30);wireless['pricing']['technology']=['5G']
        self.value['plans'].append(wireless);self.seed.write_text(json.dumps(self.value))
        c=UtilityPlanCatalog(self.db,seed_path=self.seed)
        result=advise(c,'推荐NBN网络，每月80以内',category='internet',on='2026-10-28')
        self.assertTrue(result['plans'])
        self.assertTrue(all('5G' not in p['pricing']['technology'] for p in result['plans']))

    def test_expired_promotion_reverts_to_standard_price_and_stale_data_is_excluded(self):
        rows=self.catalog.search(on='2026-11-03')
        p=next(p for p in rows if p['id']=='cheap-promo')
        self.assertFalse(p['promotion_active']);self.assertEqual(p['effective_monthly_aud'],95)
        self.assertEqual(p['first_year_base_cost_aud'],1140)
        self.assertEqual(self.catalog.search(on='2026-12-01'),[])
        archived=self.catalog.search(on='2026-12-01',include_unavailable=True)
        self.assertTrue(all(p['status']=='stale' for p in archived))

    def test_official_timestamp_expiry_uses_sydney_instant_not_only_calendar_day(self):
        self.value['plans'][0]['valid_to']='2026-10-28T00:00:00Z'
        self.seed.write_text(json.dumps(self.value));c=UtilityPlanCatalog(self.db,seed_path=self.seed)
        rows=c.search(on='2026-10-28T12:00:00+11:00')
        self.assertNotIn('cheap-ongoing',[p['id'] for p in rows])

    def test_invalid_or_unsafe_seed_cannot_replace_current_snapshot(self):
        for bad in ('http://www.tpg.com.au/nbn','https://localhost/private','https://user:secret@www.tpg.com.au/'):
            changed=deepcopy(self.value);changed['plans'][0]['source_url']=bad
            self.seed.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):UtilityPlanCatalog(self.db,seed_path=self.seed)
        self.assertEqual(len(self.catalog.search(on='2026-10-28')),2)

    def test_production_covers_all_nine_suppliers_and_preserves_official_tariffs(self):
        real=UtilityPlanCatalog(self.root/'real.sqlite3')
        rows=real.search(on='2026-10-28')
        self.assertGreater(len(rows),40)
        self.assertEqual({p['provider_id'] for p in rows},{'agl','origin','energyaustralia','telstra','optus','tpg','aussie-broadband','superloop','sydney-water'})
        energies=[p for p in rows if p['category'] in ('electricity','gas')]
        self.assertTrue(all(p['pricing']['unit'] in ('kWh','MJ') for p in energies))
        self.assertTrue(all(p['pricing']['raw_tariff_periods'] for p in energies))
        self.assertTrue(any(p['pricing']['model'].startswith('TIME_OF_USE') for p in energies))
        self.assertTrue(any(len(t.get('singleRate',{}).get('rates',[]))>1 for p in energies for t in p['pricing']['raw_tariff_periods']))
        for p in energies:
            for raw,display in zip(p['pricing']['raw_tariff_periods'],p['pricing']['tariff_periods']):
                if raw.get('dailySupplyCharge') is not None:
                    self.assertAlmostEqual(display['daily_supply_aud'],float(raw['dailySupplyCharge'])*1.1,places=6)

    def test_water_is_not_switchable_and_does_not_pass_fixed_charges_to_tenant(self):
        real=UtilityPlanCatalog(self.root/'real.sqlite3')
        answer=advise(real,'水费怎么计价',category='water',on='2026-10-28')
        self.assertIn('不能自由更换',answer['content']);self.assertIn('独立水表',answer['content'])
        self.assertIn('房东',answer['content']);self.assertIn('3.41',answer['content'])
        self.assertTrue(answer['plans'][0]['pricing']['tenancy_source_url'].startswith('https://www.nsw.gov.au/'))


class UtilityChatTests(unittest.TestCase):
    def test_chat_reads_database_returns_price_cards_and_does_not_save_supplier(self):
        from server.tests.test_assistant_api import IntentProvider
        from server.app.main import create_app
        from fastapi.testclient import TestClient
        with tempfile.TemporaryDirectory() as tmp:
            provider=IntentProvider();provider.result={'intent':'living_services','topic':'utilities','service_action':'recommend','provider_category':'internet'}
            client=TestClient(create_app(runtime_dir=tmp,ai_provider=provider))
            cid=client.post('/api/v1/cases',json={}).json()['case_id'];base=f'/api/v1/cases/{cid}'
            convo=client.post(base+'/assistant/conversations',json={}).json()
            response=client.post(base+'/assistant/conversations/'+convo['conversation_id']+'/messages',json={
                'request_id':'internet','expected_revision':0,'message':'推荐每月80以内的网络套餐','allow_external_ai':True})
            self.assertEqual(response.status_code,200,response.text);answer=response.json()['messages'][-1]
            self.assertIn('套餐',answer['content']);self.assertNotIn('目录没有实时费率',answer['content'])
            cards=answer['providers'];self.assertTrue(cards)
            self.assertTrue(all(p['category']=='internet' and p['pricing']['monthly_aud']<=80 for c in cards for p in c['plans']))
            self.assertEqual(client.get(base+'/living-services').json()['version'],0)
            directory=client.get('/api/v1/living-providers').json()
            self.assertTrue(next(p for p in directory['providers'] if p['id']=='agl')['plans'])
