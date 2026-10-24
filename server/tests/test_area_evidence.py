"""Evidence selection must not manufacture housing suitability or current facts."""
from copy import deepcopy
from datetime import date
import unittest

from server.app.areas.evidence import AreaKnowledge


class Catalog:
    suburbs = ['Burwood', 'Rhodes', 'Carlton']
    rows = [
        {'listing_id':'b1','suburb':'Burwood','bedrooms':2,'bathrooms':1,'car_spaces':0,'weekly_rent':750},
        {'listing_id':'b2','suburb':'Burwood','bedrooms':1,'bathrooms':1,'car_spaces':0,'weekly_rent':600},
        {'listing_id':'r1','suburb':'Rhodes','bedrooms':2,'bathrooms':2,'car_spaces':1,'weekly_rent':900},
        {'listing_id':'c1','suburb':'Carlton','bedrooms':2,'bathrooms':1,'car_spaces':1,'weekly_rent':650},
    ]

    def matching(self, filters):
        return [r for r in deepcopy(self.rows) if
                (not filters.get('suburb') or r['suburb']==filters['suburb']) and
                r['weekly_rent']<=filters.get('max_weekly_rent',float('inf')) and
                all(r[field]>=filters.get('min_'+field,0) for field in ('bedrooms','bathrooms','car_spaces'))]


class AreaEvidenceTests(unittest.TestCase):
    def advice(self, brief=None, areas=None, **kw):
        return AreaKnowledge().advice(Catalog(), brief or {}, areas, today=date(2026,10,24), **kw)

    def test_sources_are_traceable_and_initial_coverage_is_honest(self):
        report=self.advice({'lifestyle_priorities':['parks','food']}, ['Burwood','Rhodes','Carlton'])
        self.assertGreaterEqual(len({r['suburb'] for r in AreaKnowledge().records}),12)
        self.assertEqual(report['coverage'],{'covered_suburbs':2,'catalog_suburbs':3})
        b,r,c=report['areas']
        self.assertEqual([a['suburb'] for a in report['areas']],['Burwood','Rhodes','Carlton'])
        self.assertIn('food',b['matched_topics']); self.assertIn('parks',r['matched_topics'])
        self.assertFalse(c['evidence']); self.assertIn('parks',c['missing_topics'])
        for area in (b,r):
            for record in area['evidence']:
                self.assertTrue(record['source']['url'].startswith('https://'))
                self.assertTrue(record['source']['checked_at'])
                self.assertIn('published_at',record['source'])
                self.assertIn('data_period',record['source'])
                self.assertTrue(record['scope_label']); self.assertTrue(record['limitation'])
                self.assertNotIn('auo.org.au',record['source']['url'])

    def test_inventory_counts_honor_housing_and_comparable_budget(self):
        brief={'budget_amount':800,'budget_period':'week','budget_scope':'whole_property','min_bedrooms':2}
        report=self.advice(brief,['Burwood','Rhodes'])
        self.assertEqual([a['matching_count'] for a in report['areas']],[1,0])
        self.assertTrue(report['budget_applied'])
        self.assertIn('整套每周上限 AUD 800',report['criteria_summary'])
        self.assertIn('至少2卧',report['criteria_summary'])
        self.assertIsNone(report['areas'][1]['min_weekly_rent'])
        brief['budget_scope']='per_person'
        report=self.advice(brief,['Burwood','Rhodes'])
        self.assertFalse(report['budget_applied'])
        self.assertEqual(report['areas'][1]['matching_count'],1)
        self.assertTrue(any('计价' in n for n in report['limitations']))

    def test_quietness_safety_and_resident_opinions_are_never_guarantees(self):
        report=self.advice({'lifestyle_priorities':['quiet','safety']},['Rhodes'])
        area=report['areas'][0]
        self.assertEqual(set(area['missing_topics']),{'quiet','safety'})
        self.assertFalse(area['matched_topics'])
        opinions=[e for e in area['evidence'] if e['kind']=='resident_opinion']
        self.assertTrue(opinions)
        self.assertTrue(all(e['freshness']=='background' for e in opinions))
        self.assertIn('具体房源', ' '.join(report['limitations']))

    def test_old_or_lga_evidence_cannot_be_counted_as_suburb_match(self):
        knowledge=AreaKnowledge()
        report=knowledge.advice(Catalog(),{'lifestyle_priorities':['food']},['Burwood'],today=date(2030,1,1))
        area=report['areas'][0]
        self.assertFalse(area['matched_topics'])
        self.assertTrue(all(e['freshness'] in ('needs_review','background') for e in area['evidence']))
        record=next(e for e in knowledge.records if e['kind']=='official')
        record['suburb']='Burwood'; record['topics']=['food'];record['geographic_scope']='lga'
        record['scope_label']='辖区资料，不能直接套用到每个 suburb'
        knowledge.records=[record]
        area=knowledge.advice(Catalog(),{'lifestyle_priorities':['food']},['Burwood'],today=date(2026,10,24))['areas'][0]
        self.assertFalse(area['matched_topics'])

    def test_topic_ranking_does_not_recommend_zero_inventory_area(self):
        report=self.advice({'lifestyle_priorities':['food'],'budget_amount':700,'budget_period':'week',
                            'budget_scope':'whole_property','min_bedrooms':2})
        self.assertEqual([a['suburb'] for a in report['areas']],['Carlton'])

    def test_unknown_area_never_borrows_neighboring_evidence(self):
        report=self.advice({'lifestyle_priorities':['parks']},['Carlton'])
        self.assertEqual(report['areas'][0]['evidence'],[])
        self.assertEqual(report['areas'][0]['missing_topics'],['parks'])
