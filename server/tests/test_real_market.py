import copy
import unittest


class RealMarketTests(unittest.TestCase):
    def market(self):
        from server.app.real_data.market import MarketData
        return MarketData()

    def test_real_source_values_and_rent_difference(self):
        result = self.market().lookup('2050', 1, 'whole_property', 760)
        self.assertEqual(result['status'], 'available')
        monthly, quarterly = result['benchmarks']
        self.assertEqual((monthly['period'], monthly['sample_size'], monthly['median']), ('2026-09', 40, 805))
        self.assertEqual((monthly['q25'], monthly['q75']), (703.75, 859.25))
        self.assertEqual(monthly['difference_aud'], -45)
        self.assertAlmostEqual(monthly['difference_percent'], -5.5901, places=3)
        self.assertFalse(monthly['official_statistic'])
        self.assertEqual(quarterly['median'], 775)
        self.assertTrue(quarterly['official_statistic'])
        self.assertIn('nsw.gov.au', monthly['source_url'])

    def test_room_scope_never_compared_to_whole_property(self):
        for scope in ('per_room', 'per_person'):
            result = self.market().lookup('2050', 1, scope, 445)
            self.assertEqual(result['status'], 'scope_mismatch')
            self.assertEqual(result['benchmarks'], [])

    def test_unsupported_cohort_and_optional_rent(self):
        self.assertEqual(self.market().lookup('9999', 1, 'whole_property')['status'], 'unavailable')
        self.assertEqual(self.market().lookup('2050', 3, 'whole_property')['status'], 'unavailable')
        result = self.market().lookup('2042', 2, 'whole_property')
        self.assertEqual(result['benchmarks'][0]['median'], 810)
        self.assertIsNone(result['benchmarks'][0]['difference_aud'])

    def test_invalid_values_and_independent_results(self):
        from server.app.common import ApiError
        for rent in (True, -1, float('nan'), float('inf'), '760', 10 ** 400):
            with self.subTest(rent=rent), self.assertRaises(ApiError):
                self.market().lookup('2050', 1, 'whole_property', rent)
        for beds in (True, '1', 1.5):
            with self.assertRaises(ApiError):
                self.market().lookup('2050', beds, 'whole_property')
        market = self.market()
        first = market.lookup('2050', 1, 'whole_property')
        original = copy.deepcopy(first)
        first['benchmarks'][0]['median'] = 0
        self.assertEqual(market.lookup('2050', 1, 'whole_property'), original)
