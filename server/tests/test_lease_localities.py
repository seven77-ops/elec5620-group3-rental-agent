"""Independent notice-address suggestions contain locality metadata only."""
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from server.app.main import create_app
from server.app.real_data.catalog import RealCatalog


class LeaseLocalityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = TestClient(create_app(runtime_dir=self.temp.name))

    def search(self, q='', **params):
        return self.client.get('/api/v1/lease-localities', params={'q': q, **params})

    def items(self, q, **params):
        response = self.search(q, **params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['source'], 'au_postcodes')
        return response.json()['items']

    def test_known_localities_and_leading_zero_postcodes(self):
        for suburb, state, postcode in (('Redfern', 'NSW', '2016'),
                ('West Footscray', 'VIC', '3012'), ('Darwin', 'NT', '0800')):
            rows = self.items(suburb)
            self.assertTrue(any((r['suburb'], r['state'], r['postcode']) ==
                (suburb, state, postcode) for r in rows), rows)
            for row in rows:
                self.assertEqual(set(row), {'id', 'suburb', 'state', 'postcode'})
                self.assertIsInstance(row['postcode'], str)
        self.assertTrue(any(r['suburb'] == 'Darwin' for r in self.items('0800')))
        self.assertEqual(self.items('rEdFeRn'), self.items('Redfern'))

    def test_ambiguity_exact_state_filter_and_unknown_manual_state(self):
        rows = self.items('Burwood')
        self.assertTrue(any(r['state'] == 'NSW' and r['postcode'] == '2134' for r in rows))
        self.assertTrue(any(r['state'] == 'VIC' and r['postcode'] == '3125' for r in rows))
        self.assertTrue(self.items('Burwood', state='VIC'))
        self.assertTrue(all(r['state'] == 'VIC' for r in self.items('Burwood', state=' vic ')))
        self.assertEqual(self.items('Burwood', state='My manual State'), [])
        self.assertEqual(self.items('Burwood', state='VI'), [])

    def test_limits_empty_and_deterministic_exact_then_prefix_order(self):
        for q in ('', ' ', 'r', 'zz-no-such-locality-xyz'):
            self.assertEqual(self.items(q), [])
        self.assertEqual(self.search('x' * 80).status_code, 200)
        self.assertEqual(self.search('x' * 81).status_code, 422)
        self.assertEqual(self.search('Burwood', state='x' * 41).status_code, 422)
        self.assertEqual(self.search('Burwood', state='x' * 40).status_code, 200)
        rows = self.items('Burwood')
        self.assertEqual(rows, self.items('Burwood'))
        self.assertEqual(rows[0]['suburb'], 'Burwood')
        rows = self.items('West')
        self.assertEqual(len(rows), 20)
        self.assertEqual(len({r['id'] for r in rows}), len(rows))
        self.assertTrue(all(r['suburb'].casefold().startswith('west') for r in rows))
        self.assertEqual(self.client.get('/api/v1/lease-localities').json(),
                         {'items': [], 'source': 'au_postcodes'})

    def test_endpoint_requires_neither_listing_catalog_nor_network(self):
        route = next((r for r in self.client.app.routes if r.path == '/api/v1/lease-localities'), None)
        self.assertIsNotNone(route, 'independent locality route must be registered')
        with patch.object(RealCatalog, 'matching', side_effect=AssertionError('catalog forbidden')), \
             patch('httpx.Client.send', side_effect=AssertionError('network forbidden')), \
             patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')), \
             patch('socket.create_connection', side_effect=AssertionError('network forbidden')):
            rows = route.endpoint(q='West Footscray', state='VIC')['items']
        self.assertEqual(rows[0]['postcode'], '3012')
        self.assertFalse(any('address' in r or 'source_url' in r for r in rows))


class PostcodeReferenceTests(unittest.TestCase):
    def test_reduction_preserves_only_metadata_and_reports_invalid_duplicates(self):
        from server.app.lease_drafts.data.reduce_postcodes import reduce_csv
        import json
        raw = (b'locality,state,postcode,address\nDARWIN,NT,0800,hidden street\n'
               b'darwin,NT,0800,another street\nEmpty,XX,1234,\n,NSW,2000,\n'
               b'Bad,NSW,200,\nBad,NSW,abcd,\n')
        reduced, report = reduce_csv(raw)
        self.assertEqual(json.loads(reduced), [['Darwin', 'NT', '0800']])
        self.assertEqual(report['source_rows'], 6)
        self.assertEqual(report['invalid_rows'], 4)
        self.assertEqual(report['duplicate_rows'], 1)
        self.assertEqual(report['reduced_rows'], 1)
        self.assertEqual(reduce_csv(raw), (reduced, report))

    def test_bundled_reference_hash_schema_and_deduplication(self):
        from pathlib import Path
        import hashlib
        import json
        from server.app.lease_drafts import localities
        data = Path(localities.__file__).with_name('data').joinpath('au-localities.json').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
            '9ab69574de59210e33501e5590f0bd396f28f4978fbcd1a0245ee96b588c3a6c')
        rows = json.loads(data)
        self.assertEqual(len(rows), 18535)
        self.assertEqual(len({tuple(r) for r in rows}), len(rows))
        for suburb, state, postcode in rows:
            self.assertTrue(suburb)
            self.assertIn(state, ('NSW', 'VIC', 'QLD', 'ACT', 'SA', 'WA', 'TAS', 'NT'))
            self.assertRegex(postcode, r'^[0-9]{4}$')
