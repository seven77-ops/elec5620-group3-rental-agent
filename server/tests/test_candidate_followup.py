"""Real candidate progression without inventing verified Agent2 evidence."""
import copy
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from server.app.main import create_app


class CandidateFollowupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = TestClient(create_app(runtime_dir=self.temp.name))
        self.case = self.client.post('/api/v1/cases', json={}).json()
        self.cid = self.case['case_id']
        self.base = f'/api/v1/cases/{self.cid}'
        self.case = self.client.post(self.base+'/profile-confirmations', json={
            'draft_revision': self.case['draft']['revision'], 'fingerprint': self.case['draft']['fingerprint'],
            'review_token': self.case['agent1']['review_token']}).json()
        self.run = self.client.post(self.base+'/evaluations', json={
            'request_id':'run','confirmation_version':1}).json()
        self.rows = self.run['report']['pending_confirmation']
        self.selection = self.choose(self.rows[0], 'first')

    def choose(self, row, request):
        r = self.client.post(self.base+'/selections', json={'request_id':request,
            'run_id':self.run['run_id'], 'listing_id':row['listing_id'], 'confirmed':True})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def read(self):
        r = self.client.get(self.base+'/candidate-followup')
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def save(self, current=None, **facts):
        current = current or self.read()
        return self.client.post(self.base+'/candidate-followup', json={
            'request_id':'facts-'+str(current['version']), 'expected_version':current['version'],
            'selection_signature':current['selection_signature'], 'confirmed':True,
            'facts':{**current['facts'], 'source_note':'用户记录：中介邮件回复', **facts}})

    def consent(self):
        r = self.client.post(self.base+'/contract-consents',json={'confirmed':True})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()['consent_id']

    def upload(self, consent, request='upload', rent=620, currency='AUD', bond_currency=None):
        address = self.selection['listing_snapshot']['address']
        data = (f'Address: {address}\nLandlord: Example Owner\nTenant: Example Tenant\n'
            f'Rent: {currency} {rent} per week whole property\nBond: {bond_currency or currency} {rent*4}\n'
            'Start date: 2026-11-01\nEnd date: 2027-11-01\nSigned date: 2026-10-22\n')
        return self.client.post(self.base+'/contract-reviews',content=data.encode(),headers={
            'Content-Type':'application/octet-stream','X-Consent-Id':consent,
            'X-Request-Id':request,'X-Filename':'real-agreement.txt'})

    def test_followup_persistence_provenance_retry_and_history(self):
        initial = self.read()
        self.assertEqual(initial['version'],0)
        self.assertEqual(initial['facts']['availability'],'unknown')
        r = self.save(initial, availability='available', rent_amount=600,
                      rent_period='week',rent_scope='whole_property', stage='viewing')
        self.assertEqual(r.status_code,200,r.text)
        saved = r.json()
        self.assertEqual(saved['provenance'],'user_recorded')
        self.assertEqual(saved['version'],1)
        self.assertEqual(self.save(initial, availability='available',rent_amount=600,
            rent_period='week',rent_scope='whole_property',stage='viewing').json(),saved)
        self.assertEqual(self.save(initial,rent_amount=650).status_code,409)
        fresh = TestClient(create_app(runtime_dir=self.temp.name))
        self.assertEqual(fresh.get(self.base+'/candidate-followup').json(),saved)
        state = fresh.get(self.base).json()
        self.assertEqual(state['selection'],self.selection)
        self.assertTrue(state['selection']['requires_verification'])
        self.assertIsNone(state['selection']['listing_snapshot']['rent_scope'])
        exported = fresh.get(self.base+'/candidate-followup/questions')
        self.assertEqual(exported.status_code,200,exported.text)
        self.assertIn(self.selection['listing_snapshot']['address'],exported.text)
        self.assertIn('600',exported.text)
        with self.client.app.state.repository.transaction() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM objects WHERE kind='candidate_followup_version'").fetchone()[0],1)

    def test_invalid_and_stale_followup_cannot_write_into_another_candidate(self):
        current = self.read()
        for values in ({'rent_amount':True},{'rent_amount':-1},{'start_date':'2026-99-01'},
                       {'start_date':'2026-11-01','end_date':'2026-10-01'},
                       {'availability':'verified'},{'source_note':''}):
            self.assertEqual(self.save(current,**values).status_code,422,values)
        self.assertEqual(self.read()['version'],0)
        old = self.selection
        self.choose(self.rows[1],'second')
        self.assertEqual(self.save(current,rent_amount=600).status_code,409)
        newer = self.read()
        self.assertNotEqual(newer['selection_signature'],current['selection_signature'])
        self.assertEqual(newer['version'],0)
        self.choose(self.rows[0],'third')
        self.assertNotEqual(self.read()['selection_signature'],current['selection_signature'])
        other = self.client.post('/api/v1/cases',json={}).json()
        body={'request_id':'cross','expected_version':0,'confirmed':True,
              'selection_signature':current['selection_signature'],'facts':{**current['facts'],'source_note':'用户记录'}}
        self.assertEqual(self.client.post(f'/api/v1/cases/{other["case_id"]}/candidate-followup',json=body).status_code,409)
        self.assertNotEqual(old,self.client.get(self.base).json()['selection'])

    def test_real_contract_is_independently_consented_and_keeps_frozen_sources(self):
        self.assertFalse(self.client.get('/api/v1/demo-config').json()['capabilities']['synthetic_contract_only'])
        self.assertEqual(self.upload('missing').status_code,403)
        saved = self.save(rent_amount=600,rent_period='week',rent_scope='whole_property',
            start_date='2026-11-01',landlord='Example Owner').json()
        consent = self.consent()
        r = self.upload(consent)
        self.assertEqual(r.status_code,200,r.text)
        review = r.json()['review']; rid = review['review_id']
        self.assertIsNone(review['selection_evidence'])
        self.assertNotIn('intake',review)
        self.assertEqual(review['as_of'],datetime.now(ZoneInfo('Australia/Sydney')).date().isoformat())
        context = self.client.get(f'/api/v1/contract-reviews/{rid}/context').json()['real_context']
        self.assertEqual(context['selection'],self.selection)
        self.assertEqual(context['followup']['version'],saved['version'])
        checks = {x['key']:x for x in context['checks']}
        self.assertEqual(checks['recorded_rent']['status'],'different')
        # Contract 620/week vs the advert: the ad has no explicit charging basis, so the gap is
        # surfaced as a possible difference rather than judged equal or unequal.
        if checks['advertised_rent']['reference_value'] != 620:
            self.assertEqual(checks['advertised_rent']['status'],'possible_difference')
        else:
            self.assertEqual(checks['advertised_rent']['status'],'basis_unknown')
        self.assertEqual(checks['address']['status'],'match')
        self.assertEqual(checks['recorded_start_date']['status'],'match')
        self.assertEqual(self.upload(consent).json()['review'],review)
        self.assertEqual(self.upload(consent,rent=630).status_code,409)
        self.assertEqual(self.save(rent_amount=700).status_code,200)
        frozen = self.client.get(f'/api/v1/contract-reviews/{rid}/context').json()['real_context']
        self.assertEqual(frozen,context)
        corrected = self.client.post(f'/api/v1/contract-reviews/{rid}/corrections',json={
            'expected_version':1,'corrections':{'rent_amount':600}})
        self.assertEqual(corrected.status_code,200,corrected.text)
        checks = self.client.get(f'/api/v1/contract-reviews/{rid}/context').json()['real_context']['checks']
        self.assertEqual(next(x for x in checks if x['key']=='recorded_rent')['status'],'match')
        export = self.client.get(f'/api/v1/contract-reviews/{rid}/export').json()
        self.assertEqual(export['real_context']['selection'],self.selection)
        self.client.post(self.base+'/contract-consents',json={'confirmed':False,'consent_id':consent})
        self.assertEqual(self.upload(consent,'again').status_code,403)
        self.assertEqual(self.client.post(f'/api/v1/contract-reviews/{rid}/corrections',json={
            'expected_version':2,'corrections':{'rent_amount':630}}).status_code,403)

    def test_bond_comparison_needs_its_own_explicit_currency_basis(self):
        self.assertEqual(self.save(bond=2480).status_code,200)
        consent=self.consent()
        for index,(currency,bond_currency) in enumerate((('USD','USD'),('AUD','USD'),('AUD','AUD'))):
            r=self.upload(consent,request='currency-'+str(index),currency=currency,bond_currency=bond_currency)
            self.assertEqual(r.status_code,200,r.text)
            rid=r.json()['review']['review_id']
            checks=self.client.get(f'/api/v1/contract-reviews/{rid}/context').json()['real_context']['checks']
            bond=next(c for c in checks if c['key']=='recorded_bond')
            self.assertEqual(bond['status'],'match' if currency==bond_currency=='AUD' else 'basis_unknown')

    def test_consent_and_reviews_become_historical_when_candidate_changes(self):
        consent = self.consent()
        r = self.upload(consent)
        self.assertEqual(r.status_code,200,r.text)
        rid = r.json()['review']['review_id']
        self.choose(self.rows[1],'new-choice')
        self.assertEqual(self.upload(consent,'old-consent').status_code,409)
        context = self.client.get(f'/api/v1/contract-reviews/{rid}/context').json()
        self.assertFalse(context['consent_active'])
        self.assertEqual(context['real_context']['selection'],self.selection)
        self.assertEqual(self.client.get(f'/api/v1/contract-reviews/{rid}').status_code,200)
        self.assertEqual(self.client.post(f'/api/v1/contract-reviews/{rid}/corrections',json={
            'expected_version':1,'corrections':{'rent_amount':610}}).status_code,403)
