"""Read-only selection preview and a single atomic needs + follow-up confirmation."""
from copy import copy, deepcopy
from hashlib import sha256
from ..common import require, shape, request_id, opaque_ref
from ..repository import canonical
from ..real_data.profile import supplied_profile
from ..adapters.real_agent2 import RealProfilesAdapter, require_matching_listing
from .dialogue import profile_brief
from .recommendation_options import FIELD_MAP, criteria_for, filters_for
from .requirements import save_profile, missing, finish_sync
from .service import AssistantService, BorrowedRepository, signature, message
from .tools import preference_summary


class FollowupStart:
    def __init__(self, ctx): self.ctx = ctx

    def _preview(self, db, case_id, body):
        opaque_ref(body['listing_id'])
        require(not ('conversation_id' in body and 'filters' in body), 422, 'invalid_input', 'Choose one source for rental requirements.')
        if 'conversation_id' in body: opaque_ref(body['conversation_id'])
        case = self.ctx.get(db, 'case', case_id)
        catalog = self.ctx.settings.catalog
        row = catalog.get(body['listing_id'])
        source = {k: deepcopy(body[k]) for k in ('conversation_id', 'filters') if k in body}
        c = None
        if source.get('conversation_id'):
            c = AssistantService(self.ctx).get(db, case_id, source['conversation_id'])
        elif 'filters' not in source:
            activity = self.ctx.repo.get(db, 'assistant_commute_activity', case_id)
            if activity:
                c = AssistantService(self.ctx).get(db, case_id, activity['conversation_id'])
                source['conversation_id'] = c['conversation_id']
        base = profile_brief(supplied_profile(case['draft']['profile'], case.get('requirements_contract') != 'supplied-only-v1'))
        brief = deepcopy(c.get('rental_brief', {})) if c else base
        if c and c.get('dialogue_mode') == 'search':
            brief = criteria_for(c.get('last_search_filters', {}), brief)
        if 'filters' in source:
            filters = catalog.filters(source['filters'])
            for key in FIELD_MAP: brief.pop(key, None)
            brief = criteria_for(filters, brief)
            if 'max_weekly_rent' in filters: brief['budget_scope'] = 'whole_property'
        token = sha256(canonical({'case': signature(case), 'conversation': c,
            'source': source, 'listing': row, 'catalog': catalog.fingerprint}).encode()).hexdigest()
        # Only supplied values appear in the summary; no template defaults.
        temp = {}
        if brief.get('budget_amount') is not None:
            temp['budget'] = {'maximum': brief['budget_amount']}
            if brief.get('budget_scope') in ('whole_property', 'per_person', 'per_room'): temp['budget']['scope'] = brief['budget_scope']
        for key in ('occupants', 'rental_mode'):
            if key in brief: temp[key] = brief[key]
        temp['housing_preferences'] = {k: brief[k] for k in ('suburb', 'min_bedrooms', 'min_bathrooms', 'min_car_spaces') if k in brief}
        if brief.get('commute_mode') and brief.get('commute_max_minutes'):
            temp['student_commute'] = {'mode': brief['commute_mode'], 'maximum_minutes': brief['commute_max_minutes']}
        summary = preference_summary(temp)
        if brief.get('budget_amount') is not None and brief.get('budget_period') != 'week':
            summary[0] = f"Budget: AUD {brief['budget_amount']:g}," + ('per month.' if brief.get('budget_period') == 'month' else 'Period not supplied.')
        return {'source': source, 'listing': row, 'brief': brief, 'missing_fields': missing(brief),
                'summary': summary, 'context_token': token}, c, case

    def preview(self, case_id: str, body: dict):
        shape(body, ('listing_id',), ('conversation_id', 'filters'))
        with self.ctx.repo.transaction() as db: return self._preview(db, case_id, body)[0]

    def start(self, case_id: str, body: dict):
        shape(body, ('request_id', 'listing_id', 'context_token', 'confirmed', 'supplement'), ('conversation_id', 'filters'))
        require(body['confirmed'] is True, 422, 'confirmation_required', 'Confirm selecting this property and starting follow-up.')
        key = case_id + ':' + request_id(body['request_id'])
        with self.ctx.repo.transaction() as db, self.ctx.preferences.store.join(db):
            self.ctx.get(db, 'case', case_id)
            old = self.ctx.receipt(db, 'followup_start_receipt', key, body)
            if old: return old['result']
            preview, c, case = self._preview(db, case_id, body)
            require(body['context_token'] == preview['context_token'], 409, 'selection_context_changed', 'The listing or requirements changed. Reload the latest requirements before confirming.')
            require(isinstance(body['supplement'], dict) and set(body['supplement']) <= set(preview['missing_fields']), 422, 'invalid_input', 'Complete only the highlighted missing fields.')
            brief = {**preview['brief'], **body['supplement']}
            case = save_profile(self.ctx, db, case, brief)
            joined = copy(self.ctx); joined.repo = BorrowedRepository(self.ctx.repo, db)
            adapter = RealProfilesAdapter(joined)
            operation = 'start-' + sha256(body['request_id'].encode()).hexdigest()
            run = adapter.evaluation(case_id, {'request_id': operation, 'confirmation_version': case['confirmations'][-1]['version']})
            require_matching_listing(self.ctx.settings.catalog, body['listing_id'], run['report']['filters'], run['report']['pending_confirmation'])
            adapter.select(case_id, {'request_id': operation, 'run_id': run['run_id'], 'listing_id': body['listing_id'], 'confirmed': True})
            case = self.ctx.get(db, 'case', case_id)
            if c:
                require(len(c['messages']) < 200, 409, 'message_limit', 'This conversation is full. Start a new conversation to continue.')
                finish_sync(self.ctx, db, c, case, brief)
                c['messages'].append(message('assistant', 'Selected ' + preview['listing']['address'] + '. Prepare an inspection or generate a lease draft.', 'agent2', intent='select'))
                c['revision'] += 1
                AssistantService(self.ctx).save(db, c)
            result = {'case': case, 'conversation': c}
            self.ctx.save_receipt(db, 'followup_start_receipt', key, body, result)
            return result
