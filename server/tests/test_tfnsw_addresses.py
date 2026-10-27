import unittest
from copy import deepcopy
from server.app.common import now

ROW={'listing_id':'domain:test','address':'25/124 Parramatta Road, Camperdown','suburb':'Camperdown','postcode':'2050'}
def location(number='124-126',street='Parramatta Rd',suburb='Camperdown',kind='singlehouse',coord=None):
    return {'id':'streetID:source:'+number+':'+street+':'+suburb,'name':number+' '+street+', '+suburb,
            'buildingNumber':number,'streetName':street,'parent':{'name':suburb,'type':'locality'},
            'postCode':'2050','type':kind,'matchQuality':246,'coord':coord or [-33.886384,151.17822]}

class TfnswAddressTests(unittest.TestCase):
    def test_house_range_endpoint_is_sourced_and_identity_bound(self):
        from server.app.commute.tfnsw_addresses import address_point,valid_cached_point
        point=address_point(ROW,{'locations':[location()]},queried_at=now())
        self.assertIsNotNone(point)
        self.assertIn('range',point['precision'])
        self.assertTrue(valid_cached_point(ROW,point))
        for changed in ({'address':'1/126 Other Street, Camperdown'},{'suburb':'Newtown'},{'postcode':'2000'}):
            self.assertFalse(valid_cached_point({**ROW,**changed},point))
        corrupt=deepcopy(point);corrupt['source_url']='https://fake.example'
        self.assertFalse(valid_cached_point(ROW,corrupt))

    def test_wrong_house_street_suburb_or_area_centroid_never_supplies_a_building(self):
        from server.app.commute.tfnsw_addresses import address_point
        for candidate in (location('122'),location(street='Other Rd'),location(suburb='Newtown'),
                          location(kind='street'),location(kind='locality'),location(coord=[151.17822,-33.886384])):
            self.assertIsNone(address_point(ROW,{'locations':[candidate]},queried_at=now()))

    def test_exact_house_wins_over_range_and_conflicting_exact_points_remain_unknown(self):
        from server.app.commute.tfnsw_addresses import address_point
        exact=location('124')
        point=address_point(ROW,{'locations':[location(),exact]},queried_at=now())
        self.assertEqual(point['matched_address']['buildingNumber'],'124')
        other=location('124',coord=[-33.89,151.2])
        self.assertIsNone(address_point(ROW,{'locations':[exact,other]},queried_at=now()))

    def test_source_metadata_tampering_cannot_admit_another_building(self):
        from server.app.commute.tfnsw_addresses import address_point,valid_cached_point
        p=address_point(ROW,{'locations':[location()]},queried_at=now())
        p['matched_address']['buildingNumber']='999'
        self.assertFalse(valid_cached_point(ROW,p))

    def test_exact_range_name_still_discloses_range_and_nonfinite_quality_is_rejected(self):
        from server.app.commute.tfnsw_addresses import address_point
        row={**ROW,'address':'25/124-126 Parramatta Road, Camperdown'}
        self.assertIn('range',address_point(row,{'locations':[location()]},queried_at=now())['precision'])
        for quality in (float('nan'),float('inf'),-float('inf')):
            candidate=location();candidate['matchQuality']=quality
            self.assertIsNone(address_point(ROW,{'locations':[candidate]},queried_at=now()))
