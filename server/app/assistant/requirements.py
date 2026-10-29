"""Save supplied requirements without publishing a duplicate recommendation."""
from copy import copy, deepcopy
from jsonschema import Draft202012Validator
from ..common import ApiError, require, shape, request_id
from ..real_data.profile import supplied_profile
from ..adapters.real_agent2 import RealProfilesAdapter
from .dialogue import BRIEF_SCHEMA
from .recommendation_options import filters_for, metadata, scope_notes
from .service import AssistantService, BorrowedRepository, message, signature


def validate(brief, catalog):
    require(isinstance(brief, dict) and not list(Draft202012Validator(BRIEF_SCHEMA).iter_errors(brief)),
            422, 'invalid_input', '请核对本次租房条件。')
    require(brief.get('suburb') is None or brief['suburb'] in catalog.suburbs,
            422, 'invalid_input', '请选择当前房源库中的区域。')


def missing(brief):
    fields = []
    if brief.get('budget_amount') is not None:
        if brief.get('budget_period', 'unknown') == 'unknown': fields.append('budget_period')
        if brief.get('budget_scope', 'unknown') == 'unknown': fields.append('budget_scope')
    if brief.get('commute_max_minutes') and not brief.get('commute_mode'): fields.append('commute_mode')
    if brief.get('commute_mode') and not brief.get('commute_max_minutes'): fields.append('commute_max_minutes')
    return fields


def save_profile(ctx, db, case, brief):
    validate(brief, ctx.settings.catalog)
    require(not missing(brief), 422, 'incomplete_requirements', '请补充标出的必要信息。')
    base = supplied_profile(case['draft']['profile'], case.get('requirements_contract') != 'supplied-only-v1')
    profile = deepcopy(base)
    housing = {k: v for k, v in profile.get('housing_preferences', {}).items()
               if k not in ('suburb', 'min_bedrooms', 'min_bathrooms', 'min_car_spaces')}
    housing.update({k: brief[k] for k in ('suburb', 'min_bedrooms', 'min_bathrooms', 'min_car_spaces') if k in brief})
    if brief.get('budget_amount') is not None:
        # Persist the same budget comparability used by filters_for(brief).
        # Personal/room or non-weekly amounts are not whole-advertisement caps.
        housing['budget_match_mode'] = ('advertised_amount' if brief.get('budget_scope') == 'whole_property'
                                        and brief.get('budget_period') == 'week' else 'matching_scope')
    if housing: profile['housing_preferences'] = housing
    else: profile.pop('housing_preferences', None)
    if brief.get('budget_amount') is not None:
        profile['budget'] = {'currency': 'AUD', 'maximum': brief['budget_amount'],
                             'period': brief['budget_period'], 'scope': brief['budget_scope']}
    else: profile.pop('budget', None)
    for field in ('occupants', 'rental_mode'):
        if field in brief: profile[field] = brief[field]
    if brief.get('commute_mode') and brief.get('commute_max_minutes'):
        profile['student_commute'] = {'mode': brief['commute_mode'], 'maximum_minutes': brief['commute_max_minutes']}
        if brief.get('max_transfers') is not None: profile['student_commute']['max_transfers'] = brief['max_transfers']
    else: profile.pop('student_commute', None)
    try:
        current = ctx.current(case)
    except ApiError as exc:
        if exc.code != 'unconfirmed_profile': raise
        current = None
    if current and profile == base: return case
    joined = copy(ctx); joined.repo = BorrowedRepository(ctx.repo, db)
    adapter = RealProfilesAdapter(joined)
    case = adapter.draft(case['case_id'], {'expected_revision': case['draft']['revision'], 'profile': profile})
    return adapter.confirm(case['case_id'], {'draft_revision': case['draft']['revision'],
        'fingerprint': case['draft']['fingerprint'], 'review_token': case['agent1']['review_token']})


def finish_sync(ctx, db, conversation, case, brief):
    conversation['rental_brief'] = deepcopy(brief)
    conversation['last_search_filters'] = ctx.settings.catalog.filters(filters_for(brief))
    conversation['dialogue_mode'] = 'recommend_areas' if brief.get('commute_mode') else 'search'
    for item in conversation['messages']:
        for action in item['actions']:
            if action['type'] == 'apply_preferences': action['applied'] = True
    ctx.repo.put(db, 'assistant_commute_activity', case['case_id'], {
        'conversation_id': conversation['conversation_id'], 'brief': deepcopy(brief)})
    report = ctx.repo.get(db, 'assistant_commute_report', case['case_id'])
    if report and report['conversation_id'] == conversation['conversation_id'] and report['brief'] == brief:
        report['case_signature'] = signature(case)
        ctx.repo.put(db, 'assistant_commute_report', case['case_id'], report)


class RequirementsService:
    def __init__(self, ctx): self.ctx = ctx

    def save(self, case_id: str, conversation_id: str, body: dict):
        from .workspace import AssistantWorkspace
        shape(body, ('request_id', 'expected_revision', 'expected_profile_fingerprint', 'brief', 'confirmed'))
        require(body['confirmed'] is True, 422, 'confirmation_required', '请明确保存这些条件。')
        key = case_id + ':' + request_id(body['request_id'])
        identity = {'conversation_id': conversation_id, **body}
        assistant = AssistantService(self.ctx)
        with self.ctx.repo.transaction() as db, self.ctx.preferences.store.join(db):
            assistant.get(db, case_id, conversation_id)
            old = self.ctx.receipt(db, 'requirements_save_receipt', key, identity)
            if old: return old['result']
            c, case = AssistantWorkspace(self.ctx).context(db, case_id, conversation_id, body)
            validate(body['brief'], self.ctx.settings.catalog)
            before = self.ctx.settings.catalog.filters(c.get('last_search_filters', {}) if c.get('dialogue_mode') == 'search' else filters_for(c.get('rental_brief', {})))
            after = self.ctx.settings.catalog.filters(filters_for(body['brief']))
            case = save_profile(self.ctx, db, case, body['brief'])
            answer = None
            has_results = any(m.get('listings') or m.get('commute_recommendation') for m in c['messages'])
            if before != after or not has_results:
                from ..commute.cached_plan import reference_answer
                from ..commute.usyd import DESTINATION
                from .tools import search_answer
                answer = reference_answer(self.ctx.settings.catalog, body['brief'], DESTINATION) if after.get('usyd_max_minutes') else search_answer(self.ctx.settings.catalog, after)
                answer.pop('_search_filters', None)
                count = len(self.ctx.settings.catalog.matching(before))
                answer['content'] = ' '.join([f'找房条件已更新，符合条件的房源从 {count} 套变为 {len(answer["listings"])} 套。',
                                              *scope_notes(body['brief'])])
                from .recommendation_workspace import LABELS
                answer['recommendation_change'] = {'before_count': count, 'after_count': len(answer['listings']),
                    'changes': [{'field': k, 'label': LABELS.get(k, '找房条件'), 'before': c.get('rental_brief', {}).get(k), 'after': v}
                                for k, v in body['brief'].items() if c.get('rental_brief', {}).get(k) != v]}
                answer.update(metadata(self.ctx.settings.catalog, after, body['brief']))
                c['messages'].append(message('assistant', **answer))
            finish_sync(self.ctx, db, c, case, body['brief'])
            c['revision'] += 1
            if answer and answer.get('commute_recommendation'):
                from ..common import now
                self.ctx.repo.put(db, 'assistant_commute_report', case_id, {'conversation_id': conversation_id,
                    'conversation_revision': c['revision'], 'case_signature': signature(case),
                    'catalog_fingerprint': self.ctx.settings.catalog.fingerprint, 'brief': deepcopy(body['brief']),
                    'created_at': now(), 'message': c['messages'][-1]})
            assistant.save(db, c)
            result = {'case': case, 'conversation': c}
            self.ctx.save_receipt(db, 'requirements_save_receipt', key, identity, result)
            return result
