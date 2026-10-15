import copy
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'rental_agent' / 'engine.py'


def profile():
    return {
        'schema_version': '1.0', 'search_id': 'test', 'profile_version': 1,
        'budget': {'currency': 'AUD', 'period': 'week', 'scope': 'per_person',
                   'includes_bills': True, 'preferred': 450, 'maximum': 550, 'hard_limit': True},
        'occupants': 1, 'rental_mode': 'private_room',
        'destination_id': 'demo-usyd', 'arrival_time': '09:00', 'timezone': 'Australia/Sydney',
        'commute': {'modes': ['public_transport', 'walk'], 'preferred_minutes': 25,
                    'maximum_minutes': 40, 'hard_limit': True},
        'move_in_window': {'from': '2027-02-01', 'to': '2027-02-07'}, 'lease_months': 12,
        'hard_requirements': ['private_bedroom'],
        'soft_preferences': {'furnished': 0.6, 'private_bathroom': 0.4},
        'weights': {'commute': 0.35, 'cost': 0.30, 'housing': 0.20, 'amenities': 0.15},
    }


def listing(identifier='A', **changes):
    item = {
        'listing_id': identifier, 'source': 'synthetic-fixture', 'source_listing_id': identifier,
        'data_kind': 'synthetic', 'listing_status': 'active', 'source_permission': True,
        'last_checked_at': '2026-09-17T08:00:00+10:00',
        'rental_mode': 'private_room', 'address': '虚构地址，仅用于测试',
        'suburb': 'DEMO', 'postcode': '2000', 'location_precision': 'building',
        'rent_amount': 520, 'rent_period': 'week', 'rent_scope': 'per_person', 'currency': 'AUD',
        'bills_included': True, 'bills_weekly': None, 'mandatory_fees_weekly': 0,
        'private_bedroom': True, 'private_bathroom': True, 'furnished': True,
        'available_from': '2027-02-01', 'latest_start_date': '2027-02-07',
        'minimum_lease_months': 6,
        'commute': {'duration_minutes': 22, 'destination_id': 'demo-usyd',
                    'arrival_time': '09:00', 'timezone': 'Australia/Sydney',
                    'mode': 'public_transport', 'queried_at': '2026-09-17T08:00:00+10:00',
                    'data_kind': 'synthetic', 'walking_minutes': 5, 'transfers': 0},
        'supermarket_distance_m': 540, 'conflicts': [],
    }
    item.update(changes)
    item['evidence'] = {
        k: {'source_ref': f'fixture:{identifier}#{k}',
            'observed_at': '2026-09-17T08:00:00+10:00', 'data_kind': 'synthetic'}
        for k in item if k != 'evidence'
    }
    return item


def dataset(*items):
    return {'schema_version': '1.0', 'data_mode': 'synthetic_demo',
            'as_of': '2026-09-17T09:00:00+10:00', 'listings': list(items)}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ENGINE.exists(), '评估核心尚未实现')
        from rental_agent.engine import evaluate
        self.evaluate = evaluate

    def test_spec_scores_and_determinism(self):
        b = listing('B', rent_amount=460, supermarket_distance_m=780)
        b['commute']['duration_minutes'] = 36
        data = dataset(listing(), b)
        before = copy.deepcopy(data)
        result = self.evaluate(profile(), data)
        self.assertEqual([r['score'] for r in result['recommendations']], [88.6, 77.4])
        self.assertEqual(result, self.evaluate(profile(), data))
        self.assertEqual(data, before)

    def test_hard_failures(self):
        for change in [dict(rent_amount=551), dict(rental_mode='whole_property'),
                       dict(private_bedroom=False), dict(available_from='2027-03-01', latest_start_date='2027-03-07'),
                       dict(minimum_lease_months=13), dict(listing_status='unavailable')]:
            with self.subTest(change=change):
                result = self.evaluate(profile(), dataset(listing(**change)))
                self.assertEqual(len(result['excluded']), 1)
                self.assertEqual(result['recommendations'], [])

    def test_commute_over_limit(self):
        item = listing()
        item['commute']['duration_minutes'] = 41
        self.assertEqual(len(self.evaluate(profile(), dataset(item))['excluded']), 1)

    def test_unknown_hard_facts_are_pending(self):
        for change in [dict(bills_included=None), dict(latest_start_date=None),
                       dict(private_bedroom=None), dict(commute=None),
                       dict(mandatory_fees_weekly=None), dict(rent_scope='whole_property')]:
            with self.subTest(change=change):
                result = self.evaluate(profile(), dataset(listing(**change)))
                self.assertEqual(len(result['pending_confirmation']), 1)
                self.assertIsNone(result['pending_confirmation'][0]['score'])

    def test_unknown_amenities_score_interval(self):
        row = self.evaluate(profile(), dataset(listing(supermarket_distance_m=None)))['pending_confirmation'][0]
        self.assertEqual(row['score_range'], [76.6, 91.6])
        self.assertEqual(row['evidence_coverage'], 0.85)

    def test_zero_weight_unknown_does_not_block(self):
        p = profile()
        p['weights']['amenities'] = 0
        self.assertEqual(len(self.evaluate(p, dataset(listing(supermarket_distance_m=None)))['recommendations']), 1)

    def test_empty_soft_preferences_remove_housing_dimension(self):
        p = profile()
        p['soft_preferences'] = {}
        row = self.evaluate(p, dataset(listing(furnished=None)))['recommendations'][0]
        self.assertEqual(row['score'], 85.75)

    def test_cost_and_time_monotonicity(self):
        base = self.evaluate(profile(), dataset(listing()))['recommendations'][0]['score']
        self.assertLess(self.evaluate(profile(), dataset(listing(rent_amount=530)))['recommendations'][0]['score'], base)
        item = listing()
        item['commute']['duration_minutes'] = 30
        self.assertLess(self.evaluate(profile(), dataset(item))['recommendations'][0]['score'], base)

    def test_soft_limits_allow_but_penalise(self):
        p = profile()
        p['budget']['hard_limit'] = False
        p['commute']['hard_limit'] = False
        item = listing(rent_amount=600)
        item['commute']['duration_minutes'] = 45
        row = self.evaluate(p, dataset(item))['recommendations'][0]
        self.assertEqual(row['score_breakdown']['cost'], 40)
        self.assertEqual(row['score_breakdown']['commute'], 20)

    def test_equal_thresholds(self):
        p = profile()
        p['budget']['preferred'] = 550
        p['commute']['preferred_minutes'] = 40
        row = self.evaluate(p, dataset(listing(rent_amount=550)))['recommendations'][0]
        self.assertEqual(row['score_breakdown']['cost'], 100)

    def test_rent_period_normalisation(self):
        for period, amount in [('fortnight', 1040), ('month', 520 * 52 / 12)]:
            with self.subTest(period=period):
                row = self.evaluate(profile(), dataset(listing(rent_period=period, rent_amount=amount)))['recommendations'][0]
                self.assertAlmostEqual(row['weekly_cost'], 520)

    def test_bills_and_fees_added(self):
        row = self.evaluate(profile(), dataset(listing(rent_amount=480, bills_included=False,
                            bills_weekly=20, mandatory_fees_weekly=20)))['recommendations'][0]
        self.assertEqual(row['weekly_cost'], 520)

    def test_evidence_missing_blocks_fact(self):
        item = listing()
        del item['evidence']['rent_amount']
        self.assertEqual(len(self.evaluate(profile(), dataset(item))['pending_confirmation']), 1)

    def test_stale_conflict_precision_permission_are_pending(self):
        for changes in [dict(last_checked_at='2026-09-15T09:00:00+10:00'),
                        dict(conflicts=['rent_amount']), dict(location_precision='suburb'),
                        dict(source_permission=False), dict(last_checked_at='2026-09-18T09:00:00+10:00')]:
            with self.subTest(changes=changes):
                self.assertEqual(len(self.evaluate(profile(), dataset(listing(**changes)))['pending_confirmation']), 1)

    def test_wrong_destination_or_stale_route_pending(self):
        for key, value in [('destination_id', 'other'), ('arrival_time', '10:00'),
                           ('mode', 'drive'), ('queried_at', '2026-09-15T09:00:00+10:00')]:
            item = listing()
            item['commute'][key] = value
            self.assertEqual(len(self.evaluate(profile(), dataset(item))['pending_confirmation']), 1)

    def test_dedup_same_source_but_not_same_address(self):
        a, b = listing('A'), listing('B')
        self.assertEqual(len(self.evaluate(profile(), dataset(a, b))['recommendations']), 2)
        b['source_listing_id'] = 'A'
        result = self.evaluate(profile(), dataset(a, b))
        self.assertEqual(len(result['recommendations']), 1)
        self.assertEqual(len(result['duplicates']), 1)

    def test_conflicting_duplicates_quarantined(self):
        a, b = listing('A'), listing('B', source_listing_id='A', rent_amount=400)
        result = self.evaluate(profile(), dataset(a, b))
        self.assertEqual(result['recommendations'], [])
        self.assertEqual(len(result['pending_confirmation']), 2)

    def test_stable_top5_and_unrelated_listing(self):
        result = self.evaluate(profile(), dataset(*[listing(str(i)) for i in reversed(range(8))]))
        self.assertEqual([r['listing_id'] for r in result['recommendations']], ['0', '1', '2', '3', '4'])
        self.assertEqual(len(result['eligible']), 8)
        self.assertEqual({r['score'] for r in result['eligible']}, {88.6})

    def test_profile_invalid_values_rejected(self):
        from rental_agent.validation import ValidationError
        for group, key, value in [('weights', 'cost', -1), ('weights', 'cost', float('nan')),
                                   ('budget', 'maximum', 100), ('budget', 'maximum', True),
                                   ('budget', 'currency', 'USD')]:
            p = profile()
            p[group][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValidationError):
                self.evaluate(p, dataset(listing()))

    def test_profile_enum_wrong_types_rejected(self):
        from rental_agent.validation import ValidationError
        for field in ['rental_mode', 'scope']:
            for value in [[], {}]:
                p = profile()
                if field == 'scope':
                    p['budget'][field] = value
                else:
                    p[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    self.evaluate(p, dataset(listing()))

    def test_extreme_numeric_values_rejected(self):
        from rental_agent.validation import ValidationError
        for field in ['weights', 'soft_preferences', 'budget']:
            p = profile()
            if field == 'budget':
                p[field]['maximum'] = 10 ** 1000
            else:
                p[field] = {k: 1e308 for k in p[field]}
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.evaluate(p, dataset(listing(supermarket_distance_m=None)))

    def test_duplicate_uses_fresh_evidence(self):
        a, b = listing('A'), listing('B', source_listing_id='A')
        a['evidence']['rent_amount']['observed_at'] = '2026-09-14T08:00:00+10:00'
        result = self.evaluate(profile(), dataset(a, b))
        self.assertEqual(len(result['recommendations']), 1)
        self.assertEqual(result['recommendations'][0]['evidence_refs']['rent_amount']['source_ref'], 'fixture:B#rent_amount')

    def test_invalid_listing_values_rejected(self):
        from rental_agent.validation import ValidationError
        for changes in [dict(rent_amount=-1), dict(rent_amount=float('inf')), dict(furnished='yes'),
                        dict(last_checked_at='invalid'), dict(rent_period='year'),
                        dict(available_from='2027-02-30'), dict(supermarket_distance_m=-1)]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.evaluate(profile(), dataset(listing(**changes)))

    def test_real_or_mixed_data_rejected(self):
        from rental_agent.validation import ValidationError
        for changes in [dict(data_kind='real'), dict(commute={**listing()['commute'], 'data_kind': 'real'})]:
            with self.assertRaises(ValidationError):
                self.evaluate(profile(), dataset(listing(**changes)))

    def test_empty_candidates_and_no_matches(self):
        result = self.evaluate(profile(), dataset())
        self.assertEqual(result['recommendations'], [])
        self.assertTrue(result['clarification_requests'])

    def test_zero_weights_and_missing_required_preferences_rejected(self):
        from rental_agent.validation import ValidationError
        p = profile()
        p['weights'] = dict.fromkeys(p['weights'], 0)
        with self.assertRaises(ValidationError):
            self.evaluate(p, dataset(listing()))
        for field in ['budget', 'move_in_window', 'destination_id']:
            p = profile()
            del p[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.evaluate(p, dataset(listing()))

    def test_override_asof_marks_stale_not_current(self):
        result = self.evaluate(profile(), dataset(listing()), as_of='2026-09-20T09:00:00+10:00')
        self.assertEqual(result['recommendations'], [])
        self.assertEqual(len(result['pending_confirmation']), 1)

    def test_listing_order_does_not_change_ranks(self):
        a, b = listing('A'), listing('B')
        left = self.evaluate(profile(), dataset(a, b))
        right = self.evaluate(profile(), dataset(b, a))
        self.assertEqual(left['eligible'], right['eligible'])

    def test_dataset_shape_and_duplicate_internal_ids_rejected(self):
        from rental_agent.validation import ValidationError
        for data in [[], dataset(listing(), listing()), dataset(*[listing(str(i)) for i in range(31)])]:
            with self.subTest(data_type=type(data)), self.assertRaises(ValidationError):
                self.evaluate(profile(), data)

    def test_demo_fixtures_and_profile_ranking_change(self):
        path = ROOT / 'data/demo/listings.json'
        self.assertTrue(path.exists(), '模拟数据尚未提供')
        data = json.loads(path.read_text())
        self.assertEqual(len(data['listings']), 30)
        reports = []
        for name in ['commute', 'budget', 'housing']:
            p = json.loads((ROOT / f'data/demo/profiles/{name}.json').read_text())
            reports.append(self.evaluate(p, data))
        self.assertEqual(len(reports[0]['recommendations']), 5)
        self.assertNotEqual([r['listing_id'] for r in reports[0]['recommendations']],
                            [r['listing_id'] for r in reports[1]['recommendations']])
        self.assertTrue(reports[0]['pending_confirmation'])
        self.assertTrue(reports[0]['excluded'])
        self.assertTrue(reports[0]['duplicates'])


if __name__ == '__main__':
    unittest.main()
