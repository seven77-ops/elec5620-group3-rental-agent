"""Coarse commute values are ranges, not fabricated house coordinates or checked trips."""
import unittest
from copy import deepcopy
from server.app.common import now


def record(identifier,address,suburb='Camperdown',minutes=12):
    return {'listing_id':identifier,'address':address,'suburb':suburb,'origin':{'id':'point:'+identifier},
        'modes':{'walk':{'status':'routing_estimate','duration_minutes':minutes,'queried_at':now(),
                         'source_url':'https://routing.openstreetmap.de/routed-foot/'}}}


class EstimateTests(unittest.TestCase):
    def test_expansion_has_exactly_200_new_unique_sourced_houses_and_preserves_original_500(self):
        import json,hashlib
        from pathlib import Path
        from server.app.real_data.catalog import RealCatalog,catalog_fingerprint
        catalog=RealCatalog();root=catalog.path.parent
        manifest=json.loads((root/'expansion-20261027.json').read_text())
        raw=json.loads(catalog.path.read_text())
        self.assertEqual((len(raw[:700]),manifest['added_count']),(700,200))
        ids={r['record_id'] for r in manifest['records']}
        self.assertEqual(len(ids),200)
        self.assertEqual(ids,{r['record_id'] for r in raw[500:700]})
        original=[catalog._rows[r['record_id']] for r in raw[:500]]
        fingerprint=catalog_fingerprint(original)
        self.assertEqual(fingerprint,manifest['previous_catalog_fingerprint'])
        historical=[catalog._rows[r['record_id']] for r in raw[:700]]
        self.assertEqual(catalog_fingerprint(historical),manifest['new_catalog_fingerprint'])
        self.assertEqual(len({r['source_url'] for r in raw}),1000)
        for r in raw[500:700]:
            for key in ('bedrooms','bathrooms','car_spaces','weekly_rent'):
                self.assertIsInstance(r[key],(int,float))
            self.assertIn(r['suburb'],manifest['suburb_counts'])
            self.assertTrue(r['source_observation'].get('card_facts'))
            self.assertEqual(r['listing_status'],'advertised_unconfirmed')

    def test_unknown_house_uses_street_then_suburb_without_filling_origin(self):
        from server.app.commute.estimates import derive_estimates
        rows={'a':{'address':'1/10 Church Street, Camperdown','suburb':'Camperdown','postcode':'2050'},
              'b':{'address':'20 Church Street, Camperdown','suburb':'Camperdown','postcode':'2050'},
              'missing':{'address':'15 Church Street, Camperdown','suburb':'Camperdown','postcode':'2050'},
              'area':{'address':'Sydney','suburb':'Camperdown','postcode':'2050'}}
        records={'a':record('a',rows['a']['address'],minutes=12),'b':record('b',rows['b']['address'],minutes=17),
                 'missing':{'listing_id':'missing','origin':None,'modes':{}},'area':{'listing_id':'area','origin':None,'modes':{}}}
        before=deepcopy(records);estimates=derive_estimates(rows,records)
        self.assertEqual(records,before)
        street=estimates['missing']['walk'];self.assertEqual(street['level'],'street')
        self.assertLess(street['lower_minutes'],12);self.assertGreater(street['upper_minutes'],17)
        self.assertEqual(street['anchor_count'],2);self.assertEqual(set(street['source_listing_ids']),{'a','b'})
        self.assertEqual(estimates['area']['walk']['level'],'suburb')
        self.assertIsNone(records['missing']['origin'])

    def test_expired_observations_and_other_areas_are_not_anchors(self):
        from server.app.commute.estimates import derive_estimates
        rows={'a':{'address':'10 Church Street, Camperdown','suburb':'Camperdown','postcode':'2050'},
              'm':{'address':'50 Church Street, Redfern','suburb':'Redfern','postcode':'2016'}}
        records={'a':record('a',rows['a']['address']),'m':{'origin':None,'modes':{}}}
        self.assertNotIn('m',derive_estimates(rows,records))
        rows['m']['suburb']='Camperdown';rows['m']['postcode']='2050'
        records['a']['modes']['walk']['queried_at']='2000-01-01T00:00:00Z'
        self.assertNotIn('m',derive_estimates(rows,records))

    def test_interval_ceiling_and_time_constraints_cannot_be_satisfied_by_typical_time(self):
        from server.app.commute.estimates import estimate_matches
        item={'status':'coarse_estimate','queried_at':now(),'lower_minutes':10,'upper_minutes':30,
              'typical_minutes':18,'reference_arrival_at':'2026-10-28T09:00:00+11:00'}
        row={'usyd_commute':{'estimates':{'walk':item,'public_transport':item}}}
        self.assertFalse(estimate_matches(row,{'usyd_mode':'walk','usyd_max_minutes':20}))
        self.assertTrue(estimate_matches(row,{'usyd_mode':'walk','usyd_max_minutes':30}))
        transit={'usyd_mode':'public_transport','usyd_max_minutes':40,'usyd_arrival_time':'09:00','usyd_travel_day':'weekday'}
        self.assertTrue(estimate_matches(row,transit))
        for change in ({'usyd_arrival_time':'10:00'},{'usyd_travel_day':'weekend'},
                       {'usyd_max_transfers':0},{'usyd_travel_date':'2026-10-28'}):
            self.assertFalse(estimate_matches(row,{**transit,**change}))

    def test_chat_keeps_coarse_ranges_separate_from_checked_trips(self):
        from server.app.commute.estimates import attach_estimates
        row={'listing_id':'unknown','weekly_rent':700,'usyd_commute':{'origin':None,'estimates':{
            'walk':{'status':'coarse_estimate','queried_at':now(),'lower_minutes':15,'upper_minutes':30}}}}
        answer={'listings':[],'commute_recommendation':{'routes':[],'pending_listings':[row]}}
        attach_estimates(answer,[row],{'commute_mode':'walk','commute_max_minutes':20})
        self.assertEqual(answer['listings'],[])
        self.assertEqual(answer['commute_recommendation']['routes'],[])
        self.assertEqual(answer['commute_recommendation']['estimated_listings'],[row])
        self.assertEqual(answer['commute_recommendation']['pending_listings'],[])

    def test_live_location_recovery_is_not_repeated_as_an_unlocated_estimate(self):
        from server.app.commute.estimates import attach_estimates
        row={'listing_id':'recovered','weekly_rent':700,'usyd_commute':{'origin':None,'estimates':{
            'walk':{'status':'coarse_estimate','queried_at':now(),'lower_minutes':15,'upper_minutes':30}}}}
        answer={'listings':[row],'commute_recommendation':{'routes':[{'listing_id':'recovered',
            'status':'ok','duration_minutes':18}],'pending_listings':[]}}
        attach_estimates(answer,[row],{'commute_mode':'walk','commute_max_minutes':20})
        self.assertEqual(answer['commute_recommendation']['estimated_listings'],[])
