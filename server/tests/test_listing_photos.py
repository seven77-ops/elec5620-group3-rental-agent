import copy
import json
from pathlib import Path
import tempfile
import unittest

from server.app.real_data.catalog import RealCatalog


class ListingPhotosTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'listings.json'
        rows = json.loads(Path('agent2/data/real/listings.json').read_text(encoding='utf-8'))[:2]
        self.path.write_text(json.dumps(rows))
        self.rows = rows
        self.photo_path = self.path.with_name('photos.json')
        self.entry = {'listing_id': rows[0]['record_id'], 'source_url': rows[0]['source_url'],
                      'captured_at': '2026-10-22T03:00:00+00:00',
                      'image_urls': ['https://rimh2.domainstatic.com.au/observed-property-photo']}

    def write(self, entries=None):
        self.photo_path.write_text(json.dumps({'schema_version': 1, 'listings': entries if entries is not None else [self.entry]}))

    def test_absent_media_does_not_block_real_catalogue(self):
        c = RealCatalog(self.path)
        self.assertEqual(c.get(self.rows[0]['record_id'])['photos'], [])
        self.assertEqual(c.metadata()['photo_listing_count'], 0)

    def test_enrichment_preserves_base_fingerprint_and_filters_and_isolation(self):
        before = RealCatalog(self.path)
        before_ids = [r['listing_id'] for r in before.matching({'min_bedrooms': 1})]
        self.write()
        after = RealCatalog(self.path)
        self.assertEqual(after.fingerprint, before.fingerprint)
        self.assertEqual([r['listing_id'] for r in after.matching({'min_bedrooms': 1})], before_ids)
        item = after.get(self.entry['listing_id'])
        self.assertEqual(item['photos'], [{'url': self.entry['image_urls'][0], 'source_url': self.entry['source_url'], 'captured_at': self.entry['captured_at']}])
        self.assertEqual(after.metadata()['photo_listing_count'], 1)
        self.assertEqual(after.metadata()['photo_count'], 1)
        item['photos'][0]['url'] = 'changed'
        self.assertEqual(after.get(self.entry['listing_id'])['photos'][0]['url'], self.entry['image_urls'][0])
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8')), self.rows)

    def test_invalid_media_cannot_be_loaded(self):
        for change in (
            {'listing_id': 'domain:999'}, {'source_url': self.rows[1]['source_url']},
            {'captured_at': 'yesterday'}, {'captured_at': '2026-10-22T03:00:00'},
            {'image_urls': ['http://rimh2.domainstatic.com.au/a']},
            {'image_urls': ['https://rimh2.domainstatic.com.au.evil.test/a']},
            {'image_urls': ['https://user@rimh2.domainstatic.com.au/a']},
            {'image_urls': ['https://rimh2.domainstatic.com.au:443/a']},
            {'image_urls': ['https://rimh2.domainstatic.com.au/a?token=bad']},
            {'image_urls': ['https://rimh2.domainstatic.com.au/a#fragment']},
            {'image_urls': ['javascript:alert(1)']},
            {'image_urls': self.entry['image_urls'] * 13},
        ):
            with self.subTest(change=change):
                self.write([{**copy.deepcopy(self.entry), **change}])
                with self.assertRaises(ValueError):
                    RealCatalog(self.path)
        self.write([self.entry, self.entry])
        with self.assertRaises(ValueError):
            RealCatalog(self.path)

    def test_explicit_missing_sidecar_never_uses_default_media(self):
        self.write()
        c = RealCatalog(self.path, photos_path=Path(self.temp.name) / 'absent.json')
        self.assertEqual(c.get(self.entry['listing_id'])['photos'], [])

    def test_same_property_reference_preserves_actual_photo_source(self):
        self.entry.update(photo_source_url='https://www.property.com.au/nsw/example-2000/street/1-pid-123/',
                          photo_source_kind='same_property_reference',
                          image_urls=['https://i2.au.reastatic.net/800x600/observed-photo/main.jpg'])
        self.write()
        photo = RealCatalog(self.path).get(self.entry['listing_id'])['photos'][0]
        self.assertEqual(photo['source_url'], self.entry['source_url'])
        self.assertEqual(photo['photo_source_url'], self.entry['photo_source_url'])
        self.assertEqual(photo['photo_source_kind'], 'same_property_reference')

    def test_relisted_property_retains_observed_source_page(self):
        self.entry.update(photo_source_url='https://www.domain.com.au/observed-property-12345678',
                          photo_source_kind='same_property_advertisement')
        self.write()
        photo = RealCatalog(self.path).get(self.entry['listing_id'])['photos'][0]
        self.assertEqual(photo['photo_source_url'], self.entry['photo_source_url'])

    def test_reference_photos_require_allowlisted_page_and_matching_cdn(self):
        valid = {**self.entry, 'photo_source_url':'https://www.realestate.com.au/property-apartment-nsw-example-123456',
                 'photo_source_kind':'same_property_advertisement',
                 'image_urls':['https://i2.au.reastatic.net/800x600/photo/image.jpg']}
        for change in (
            {'photo_source_url':'https://www.property.com.au.evil.test/nsw/example'},
            {'photo_source_url':'javascript:alert(1)'},
            {'photo_source_url':'https://user@www.realestate.com.au/property-example'},
            {'photo_source_url':'https://www.realestate.com.au:444/property-example'},
            {'photo_source_url':'https://www.realestate.com.au/property-example#fragment'},
            {'photo_source_url':self.entry['source_url']},
            {'image_urls':['https://i2.au.reastatic.net.evil.test/photo.jpg']},
            {'photo_source_kind':'verified_current_photo'},
        ):
            with self.subTest(change=change):
                self.write([{**valid, **change}])
                with self.assertRaises(ValueError):
                    RealCatalog(self.path)
        self.write([{**self.entry, 'image_urls':valid['image_urls']}])
        with self.assertRaises(ValueError):
            RealCatalog(self.path)


if __name__ == '__main__':
    unittest.main()
