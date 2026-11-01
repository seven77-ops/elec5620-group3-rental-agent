"""One explicit confirmation saves supplied needs and starts follow-up atomically."""
from copy import deepcopy
import unittest
from server.tests import test_assistant_api as harness


class FollowupStartTests(unittest.TestCase):
    setUp = harness.AssistantTests.setUp
    conversation = harness.AssistantTests.conversation
    send = harness.AssistantTests.send

    def seed(self, **patch):
        brief = {'suburb': None, 'budget_amount': 1000, 'budget_period': 'week',
                 'budget_scope': 'whole_property', 'rental_mode': 'whole_property',
                 'occupants': 1, 'min_bedrooms': 1, 'min_bathrooms': 1,
                 'commute_mode': 'public_transport', 'commute_max_minutes': 30, **patch}
        self.provider.result = {'intent': 'recommend_areas', 'brief_patch': brief}
        c = self.send(self.conversation(), message='帮我推荐', allow_external_data=True).json()
        return c, c['messages'][-1]['listings'][0] if c['messages'][-1]['listings'] else self.client.get('/api/v1/listings').json()['items'][0]

    @property
    def root(self):
        return '/api/v1/cases/' + self.case['case_id']

    def preview(self, c, row):
        r = self.client.post(self.root + '/followup-preview', json={'listing_id': row['listing_id'], 'conversation_id': c['conversation_id']})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def start(self, preview, **patch):
        return self.client.post(self.root + '/followup-start', json={
            **preview['source'], 'listing_id': preview['listing']['listing_id'],
            'request_id': 'start-one', 'context_token': preview['context_token'],
            'confirmed': True, 'supplement': {}, **patch})

    def test_direct_selection_without_favorite_or_prior_sync_does_not_duplicate_results(self):
        c, row = self.seed()
        preview = self.preview(c, row)
        self.assertEqual(preview['missing_fields'], [])
        self.assertEqual(self.client.get(self.root).json(), self.case)
        calls = len(self.provider.inputs)
        result = self.start(preview)
        self.assertEqual(result.status_code, 200, result.text)
        saved = result.json()
        self.assertEqual(saved['case']['selection']['listing_id'], row['listing_id'])
        self.assertEqual(len(saved['case']['confirmations']), 1)
        self.assertEqual(self.client.get(self.root + '/favorites').json()['items'], [])
        self.assertEqual(sum(bool(m['listings']) for m in saved['conversation']['messages']), 1)
        self.assertEqual(self.start(preview).json(), saved)
        self.assertFalse(saved['case']['selection']['contract_ready'])
        self.assertEqual(len(self.provider.inputs), calls)

    def scope_selection(self, scope):
        c, _ = self.seed(budget_amount=300, budget_scope=scope)
        row = next(r for r in c['messages'][-1]['listings'] if r['weekly_rent'] > 300)
        selected = self.start(self.preview(c, row), request_id='select-' + scope)
        self.assertEqual(selected.status_code, 200, selected.text)
        self.assertEqual(selected.json()['case']['draft']['profile']['budget']['scope'], scope)
        context = self.client.get(self.root + '/recommendation-context').json()
        self.assertNotIn('max_weekly_rent', context['filters'])
        self.assertEqual(selected.json()['case']['selection']['listing_id'], row['listing_id'])
        return selected.json()

    def test_personal_budget_keeps_scope_and_whole_property_can_restore_price_filter(self):
        selected = self.scope_selection('per_person')
        self.provider.result = {'intent':'recommend_areas','brief_patch':{'budget_amount':900,'budget_scope':'whole_property'}}
        c = self.send(selected['conversation'], 'restore-budget', '整套预算900', allow_external_data=True).json()
        row = c['messages'][-1]['listings'][0]
        response = self.start(self.preview(c, row), request_id='restore-whole-budget')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get(self.root + '/recommendation-context').json()['filters']['max_weekly_rent'], 900)

    def test_room_budget_does_not_become_a_whole_advertisement_ceiling(self):
        self.scope_selection('per_room')

    def test_supplement_only_missing_fields_and_stale_confirmation_rolls_back(self):
        c, row = self.seed(budget_scope='unknown')
        preview = self.preview(c, row)
        self.assertEqual(preview['missing_fields'], ['budget_scope'])
        before = self.client.get(self.root).json()
        self.assertEqual(self.start(preview).status_code, 422)
        self.assertEqual(self.client.get(self.root).json(), before)
        result = self.start(preview, supplement={'budget_scope': 'whole_property'})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['case']['selection']['listing_id'], row['listing_id'])
        latest = self.preview(result.json()['conversation'], row)
        profile = deepcopy(result.json()['case']['draft']['profile'])
        profile['occupants'] = 2
        self.client.post(self.root + '/profile-drafts', json={'expected_revision': result.json()['case']['draft']['revision'], 'profile': profile})
        before = self.client.get(self.root).json()
        self.assertEqual(self.start(latest, request_id='stale').status_code, 409)
        self.assertEqual(self.client.get(self.root).json(), before)

    def test_save_unchanged_requirements_reuses_cards_and_changed_filters_update_once(self):
        c, row = self.seed()
        invalid = self.client.post(self.base + '/conversations/' + c['conversation_id'] + '/requirements', json={
            'request_id': 'invalid', 'expected_revision': c['revision'],
            'expected_profile_fingerprint': self.case['draft']['fingerprint'], 'brief': [], 'confirmed': True})
        self.assertEqual(invalid.status_code, 422, invalid.text)
        self.assertEqual(self.client.get(self.root).json(), self.case)
        def save(c, brief, key):
            r = self.client.post(self.base + '/conversations/' + c['conversation_id'] + '/requirements', json={
                'request_id': key, 'expected_revision': c['revision'],
                'expected_profile_fingerprint': self.client.get(self.root).json()['draft']['fingerprint'],
                'brief': brief, 'confirmed': True})
            self.assertEqual(r.status_code, 200, r.text)
            return r.json()['conversation']
        c = save(c, c['rental_brief'], 'save-same')
        self.assertEqual(sum(bool(m['listings']) for m in c['messages']), 1)
        c = save(c, {**c['rental_brief'], 'budget_amount': 900}, 'save-new')
        self.assertEqual(sum(bool(m['listings']) for m in c['messages']), 2)
        self.assertIn('recommendation_change', c['messages'][-1])
        self.assertFalse(any('Agent1 已确认' in m['content'] for m in c['messages']))

    def test_cancel_is_read_only_and_outside_listing_cannot_partially_save_needs(self):
        c, _ = self.seed()
        row = self.client.get('/api/v1/listings?sort=rent_desc').json()['items'][0]
        p = self.preview(c, row)
        before = self.client.get(self.root).json()
        self.assertEqual(self.start(p, confirmed=False).status_code, 422)
        self.assertEqual(self.start(p).status_code, 409)
        self.assertEqual(self.client.get(self.root).json(), before)

    def test_old_prepare_apply_reuses_identical_existing_recommendations(self):
        c, _ = self.seed(min_car_spaces=0)
        proposal = self.client.post(self.base + '/conversations/' + c['conversation_id'] + '/proposals', json={
            'request_id': 'legacy-prepare', 'expected_revision': c['revision'],
            'expected_profile_fingerprint': self.case['draft']['fingerprint'], 'brief': c['rental_brief']})
        self.assertEqual(proposal.status_code, 200, proposal.text)
        applied = self.client.post(self.base + '/proposals/' + proposal.json()['proposal_id'] + '/apply', json={'request_id': 'legacy-apply', 'confirmed': True})
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertEqual(sum(bool(m['listings']) for m in applied.json()['conversation']['messages']), 1)
