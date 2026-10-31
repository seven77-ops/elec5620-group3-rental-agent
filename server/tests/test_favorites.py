"""Favorites are a durable shortlist, independent of the one follow-up selection."""
import copy
import tempfile
import unittest
from fastapi.testclient import TestClient
from server.app.main import create_app


class FavoritesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = TestClient(create_app(runtime_dir=self.temp.name))
        self.case = self.client.post('/api/v1/cases', json={}).json()
        self.base = '/api/v1/cases/' + self.case['case_id']
        self.rows = self.client.get('/api/v1/listings?page_size=3').json()['items']

    def favorite(self, row, saved=True, key=None):
        return self.client.post(self.base+'/favorites', json={
            'request_id':key or ('fav-' + row['listing_id'].replace(':','-') + str(saved)),
            'listing_id':row['listing_id'], 'saved':saved})

    def confirm(self):
        self.case = self.client.post(self.base+'/profile-confirmations', json={
            'draft_revision':self.case['draft']['revision'],
            'fingerprint':self.case['draft']['fingerprint'],
            'review_token':self.case['agent1']['review_token']}).json()

    def choose(self, row, key='choose', **changes):
        return self.client.post(self.base+'/followup-selection', json={
            'request_id':key,'expected_profile_fingerprint':self.case['draft']['fingerprint'],
            'listing_id':row['listing_id'],'confirmed':True,**changes})

    def test_multi_favorites_persist_without_confirming_or_selecting(self):
        before = self.client.get(self.base).json()
        self.assertEqual(self.client.get(self.base+'/favorites').json()['items'], [])
        first = self.favorite(self.rows[0])
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.favorite(self.rows[0]).json(), first.json())
        self.assertEqual(self.favorite(self.rows[0], key='same-ad').status_code, 200)
        self.assertEqual(len(self.favorite(self.rows[1]).json()['items']), 2)
        fresh = TestClient(create_app(runtime_dir=self.temp.name))
        items = fresh.get(self.base+'/favorites').json()['items']
        self.assertEqual({i['listing']['listing_id'] for i in items}, {r['listing_id'] for r in self.rows[:2]})
        self.assertEqual(fresh.get(self.base).json(), before)
        self.assertEqual(self.favorite(self.rows[0], False).status_code, 200)
        self.assertEqual(len(self.client.get(self.base+'/favorites').json()['items']), 1)
        # Replaying an earlier add must not re-add an intentionally removed favorite.
        replay = self.favorite(self.rows[0])
        self.assertEqual(len(replay.json()['items']), 1)
        self.assertEqual(len(self.client.get(self.base+'/favorites').json()['items']), 1)

    def test_selection_is_explicit_and_independent_and_replacement_preserves_favorites(self):
        self.favorite(self.rows[0]); self.favorite(self.rows[1])
        self.assertEqual(self.choose(self.rows[0]).status_code,409)
        self.confirm()
        self.assertEqual(self.choose(self.rows[0], confirmed=False).status_code,422)
        first = self.choose(self.rows[0])
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(first.json()['listing_id'],self.rows[0]['listing_id'])
        self.assertEqual(self.choose(self.rows[0]).json(),first.json())
        self.favorite(self.rows[0],False)
        self.assertEqual(self.client.get(self.base).json()['selection'],first.json())
        initial = self.client.get(self.base+'/candidate-followup').json()
        body={'request_id':'note','expected_version':0,'selection_signature':initial['selection_signature'],
              'confirmed':True,'facts':{**initial['facts'],'source_note':'本人看房','viewing_note':'周六看房'}}
        self.assertEqual(self.client.post(self.base+'/candidate-followup',json=body).status_code,200)
        second=self.choose(self.rows[1],key='choose-second')
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(len(self.client.get(self.base+'/favorites').json()['items']),1)
        self.assertEqual(self.client.get(self.base+'/candidate-followup').json()['version'],0)
        self.assertEqual(self.client.post(self.base+'/candidate-followup',json=body).status_code,409)
        self.assertFalse(second.json()['contract_ready'])

    def test_invalid_references_case_isolation_and_stale_requirements(self):
        self.favorite(self.rows[0])
        other=self.client.post('/api/v1/cases',json={}).json()
        self.assertEqual(self.client.get('/api/v1/cases/'+other['case_id']+'/favorites').json()['items'],[])
        missing={**self.rows[0],'listing_id':'does-not-exist'}
        self.assertEqual(self.favorite(missing).status_code,404)
        self.assertEqual(self.favorite(self.rows[0],saved='true',key='invalid').status_code,422)
        self.confirm()
        before=copy.deepcopy(self.client.get(self.base).json())
        self.assertEqual(self.choose(self.rows[0],expected_profile_fingerprint='old').status_code,409)
        self.assertEqual(self.client.get(self.base).json(),before)
        profile=copy.deepcopy(self.case['draft']['profile'])
        profile['housing_preferences']={'suburb':'Rhodes'}
        r=self.client.post(self.base+'/profile-drafts',json={
            'expected_revision':self.case['draft']['revision'],'profile':profile})
        self.assertEqual(r.status_code,200,r.text)
        self.case=r.json(); self.confirm()
        before=self.client.get(self.base).json()
        self.assertEqual(self.choose(self.rows[0],key='outside').status_code,409)
        self.assertEqual(self.client.get(self.base).json(),before)
