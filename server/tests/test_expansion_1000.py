"""The 300-house expansion keeps source, photo and commute evidence together."""
import hashlib
import json
import unittest
from pathlib import Path

from server.app.real_data.catalog import RealCatalog, CORE_FIELDS
from server.app.commute.locations import validated_origin
from server.app.commute.snapshot import observation


class Expansion1000Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = RealCatalog()
        cls.raw = json.loads(cls.catalog.path.read_text(encoding='utf-8'))
        cls.manifest = json.loads(cls.catalog.path.with_name('expansion-1000-20261028.json').read_text(encoding='utf-8'))

    def test_exactly_300_new_unique_houses_preserve_previous_700(self):
        m = self.manifest
        self.assertEqual((len(self.raw), m['previous_count'], m['added_count'], m['new_count']), (1000, 700, 300, 1000))
        added = {r['record_id'] for r in self.raw[700:]}
        self.assertEqual(added, {r['record_id'] for r in m['records']})
        self.assertEqual(len(added), 300)
        self.assertEqual(len({r['source_url'] for r in self.raw}), 1000)
        previous = [self.catalog._rows[r['record_id']] for r in self.raw[:700]]
        fingerprint = hashlib.sha256(json.dumps(previous, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(fingerprint, m['previous_catalog_fingerprint'])
        self.assertEqual(self.catalog.fingerprint, m['new_catalog_fingerprint'])

    def test_new_houses_have_one_matched_photo_and_sourced_building_routes(self):
        self.assertEqual(self.catalog.metadata()['photo_listing_count'], 1000)
        self.assertEqual(self.catalog.metadata()['photo_count'], 1667)
        for raw in self.raw[700:]:
            with self.subTest(listing=raw['record_id']):
                row = self.catalog.get(raw['record_id'])
                for field in CORE_FIELDS:
                    self.assertIsInstance(raw[field], (int, float))
                self.assertEqual(row['listing_status'], 'advertised_unconfirmed')
                self.assertEqual(len(row['photos']), 1)
                self.assertEqual(row['photos'][0]['source_url'], row['source_url'])
                commute = row['usyd_commute']
                self.assertTrue(validated_origin(row, commute['origin']))
                for mode in ('walk', 'bike', 'drive'):
                    self.assertIsNotNone(observation(row, mode))
                public = commute['modes']['public_transport']
                self.assertIn(public['status'], ('planned', 'no_observed_option'))
                if public['status'] == 'planned':
                    self.assertIsNotNone(observation(row, 'public_transport'))

    def test_core_advertisement_facts_do_not_conflict_with_observed_details(self):
        for row in self.raw[700:]:
            detail = row['source_observation']['detail_facts']
            for field in CORE_FIELDS:
                if detail.get(field) is not None:
                    self.assertEqual(row[field], detail[field], (row['record_id'], field))

    def test_near_campus_and_requested_commuter_areas_are_both_represented(self):
        self.assertEqual(self.manifest['near_campus_count'], 215)
        self.assertEqual(self.manifest['commuter_suburbs_count'], 85)
        for suburb in ('Newtown', 'Glebe', 'Camperdown', 'Chippendale', 'Darlington',
                       'Burwood', 'Strathfield', 'Rhodes', 'Ashfield', 'Homebush'):
            self.assertGreater(self.manifest['suburb_counts'].get(suburb, 0), 0)
