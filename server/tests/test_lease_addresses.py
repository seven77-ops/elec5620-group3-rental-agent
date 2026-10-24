"""Read-only address suggestions use the existing NSW catalogue, never a remote geocoder."""
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from server.app.main import create_app
from server.app.real_data.catalog import RealCatalog


class LeaseAddressTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.client=TestClient(create_app(runtime_dir=self.temp.name))
        self.catalog=RealCatalog()

    def search(self,q):return self.client.get('/api/v1/lease-addresses',params={'q':q})

    def test_local_real_addresses_and_localities_keep_source_identity_without_external_io(self):
        with patch('httpx.Client.send',side_effect=AssertionError('external HTTP forbidden')):
            # TestClient itself uses httpx.Client.send; call the ASGI endpoint function instead.
            route=next((r for r in self.client.app.routes if r.path=='/api/v1/lease-addresses'),None)
            self.assertIsNotNone(route,'local address route must be registered')
            result=route.endpoint(q='Redfern')
        self.assertEqual(result['source'],'local_catalog');self.assertLessEqual(len(result['items']),10)
        locality=next(r for r in result['items'] if r['kind']=='locality')
        self.assertEqual((locality['address'],locality['suburb'],locality['state'],locality['postcode']),('','Redfern','NSW','2016'))
        rows=[r for r in result['items'] if r['kind']=='address'];self.assertTrue(rows)
        for item in rows:
            original=self.catalog.get(item['id'])
            self.assertEqual(item['source_url'],original['source_url'])
            self.assertEqual(item['postcode'],original['postcode'])
            self.assertNotIn(', Redfern',item['address'])
            self.assertTrue(original['address'].startswith(item['address']))
            self.assertEqual(item['full_address'],item['address']+', Redfern NSW '+item['postcode'])
        self.assertEqual(self.search('rEdFeRn').json(),result)
        self.assertTrue(self.search('2134').json()['items'])
        burwood=self.search('Burwood').json()['items']
        self.assertTrue(any(i['kind']=='locality' and i['postcode']=='2134' for i in burwood))
        self.assertTrue(self.search(rows[0]['address']).json()['items'])

    def test_query_limits_unknowns_and_no_guessing_from_unit_numbers(self):
        for query in ('',' ','r','not-a-real-nsw-place-xyz'):
            r=self.search(query);self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json(),{'items':[],'source':'local_catalog'})
        self.assertEqual(self.search('x'*121).status_code,422)
        r=self.search('2000');self.assertEqual(r.status_code,200,r.text)
        for item in r.json()['items']:
            if item['kind']=='address':self.assertEqual(item['postcode'],self.catalog.get(item['id'])['postcode'])
        self.assertEqual(self.client.get('/api/v1/lease-addresses').json(),{'items':[],'source':'local_catalog'})

    def test_mixed_freeform_query_suggests_known_locality_without_using_unit_number_as_postcode(self):
        r=self.search('Redfern, Unit 2001');self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(len(r.json()['items']),1)
        item=r.json()['items'][0]
        self.assertEqual((item['kind'],item['address'],item['suburb'],item['postcode']),('locality','','Redfern','2016'))
        self.assertEqual(self.search('NotRedfernStreet, Unit 2001').json()['items'],[])

    def test_source_without_street_is_only_offered_as_locality(self):
        from server.app.lease_drafts.addresses import street_address
        source=next(r for r in self.catalog.matching({}) if r['address']==r['suburb'])
        self.assertEqual(street_address(source),'')
        route=next(r for r in self.client.app.routes if r.path=='/api/v1/lease-addresses')
        # Restrict the real catalogue view to this real source observation: no street exists.
        with patch.object(route.endpoint.__self__.ctx.settings.catalog,'matching',return_value=[source]):
            result=self.search(source['suburb']).json()
        self.assertEqual(len(result['items']),1)
        self.assertEqual(result['items'][0]['kind'],'locality')
        self.assertEqual(result['items'][0]['address'],'')
