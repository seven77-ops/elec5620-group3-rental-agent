"""Independent case shortlists and an explicit, atomic follow-up selection."""
from copy import copy, deepcopy
from hashlib import sha256
from ..common import ApiError, now, opaque_ref, request_id, require, shape


class FavoritesAdapter:
    def __init__(self, ctx):
        self.ctx = ctx

    def public(self, saved):
        items = []
        for item in saved.get('items', []):
            try:
                listing = self.ctx.settings.catalog.get(item['listing']['listing_id'])
                available = True
            except ApiError as exc:
                if exc.code != 'listing_not_found':
                    raise
                listing, available = item['listing'], False
            items.append({**item, 'listing':listing, 'in_catalog':available})
        return {**saved, 'items':items}

    def read(self, case_id: str):
        with self.ctx.repo.transaction() as db:
            self.ctx.get(db, 'case', case_id)
            saved = self.ctx.repo.get(db, 'favorites', case_id) or {'case_id':case_id, 'items':[]}
            return self.public(saved)

    def save(self, case_id: str, body: dict):
        shape(body, ('request_id', 'listing_id', 'saved'))
        key = case_id + ':' + request_id(body['request_id'])
        opaque_ref(body['listing_id'])
        require(type(body['saved']) is bool, 422, 'invalid_input', 'Choose whether to save or remove the favourite.')
        with self.ctx.repo.transaction() as db:
            self.ctx.get(db, 'case', case_id)
            old = self.ctx.receipt(db, 'favorite_receipt', key, body)
            if old:
                saved = self.ctx.repo.get(db, 'favorites', case_id) or {'case_id':case_id, 'items':[]}
                return self.public(saved)
            saved = self.ctx.repo.get(db, 'favorites', case_id) or {'case_id':case_id, 'items':[]}
            items = saved['items']
            if body['saved']:
                listing = self.ctx.settings.catalog.get(body['listing_id'])
                if not any(i['listing']['listing_id'] == body['listing_id'] for i in items):
                    items.insert(0, {'listing':deepcopy(listing), 'saved_at':now()})
            else:
                saved['items'] = [i for i in items if i['listing']['listing_id'] != body['listing_id']]
            self.ctx.repo.put(db, 'favorites', case_id, saved)
            result = self.public(saved)
            # Receipts record the mutation, not a growing copy of the whole shortlist.
            self.ctx.save_receipt(db, 'favorite_receipt', key, body,
                                  {'listing_id':body['listing_id'], 'saved':body['saved']})
            return result

    def select(self, case_id: str, body: dict):
        shape(body, ('request_id', 'expected_profile_fingerprint', 'listing_id', 'confirmed'), ('allow_external_data',))
        key = case_id + ':' + request_id(body['request_id'])
        opaque_ref(body['listing_id'])
        require(body['confirmed'] is True, 422, 'selection_confirmation_required', 'Explicitly confirm selecting this listing.')
        if 'allow_external_data' in body:
            require(type(body['allow_external_data']) is bool,422,'invalid_input','Invalid external route lookup option.')
        from .real_agent2 import RealProfilesAdapter, require_matching_listing
        from ..assistant.service import BorrowedRepository
        with self.ctx.repo.transaction() as db, self.ctx.preferences.store.join(db):
            case = self.ctx.get(db, 'case', case_id)
            old = self.ctx.receipt(db, 'followup_selection_receipt', key, body)
            if old:
                return old['result']
            require(body['expected_profile_fingerprint'] == case['draft']['fingerprint'],
                    409, 'stale_profile', 'Rental requirements changed. Reload before selecting a listing.')
            confirmed = self.ctx.current(case)
            self.ctx.settings.catalog.get(body['listing_id'])
            joined = copy(self.ctx)
            joined.repo = BorrowedRepository(self.ctx.repo, db)
            adapter = RealProfilesAdapter(joined)
            operation = 'followup-' + sha256(body['request_id'].encode()).hexdigest()
            run = adapter.evaluation(case_id, {'request_id':operation, 'confirmation_version':confirmed['version']})
            require_matching_listing(self.ctx.settings.catalog,body['listing_id'],run['report']['filters'],
                                     run['report']['pending_confirmation'])
            selection = adapter.select(case_id, {'request_id':operation, 'run_id':run['run_id'],
                'listing_id':body['listing_id'], 'confirmed':True})
            self.ctx.save_receipt(db, 'followup_selection_receipt', key, body, selection)
            return selection
