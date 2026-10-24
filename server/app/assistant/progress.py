"""Preserve explicit UI transitions and answers to the current intake question."""
import re
from copy import deepcopy
from jsonschema import Draft202012Validator, FormatChecker
from ..ai.provider import ProviderError
from ..common import ApiError
from . import commute
from .dialogue import BRIEF_SCHEMA
from .intents import validate_intent

SCHOOL_REPLY=re.compile(r'(?:usyd|unsw|uts|wsu|悉大|悉尼大学|悉尼科技大学|新南威尔士大学|新南|麦考瑞大学|西悉尼大学|University of Sydney|University of Technology(?: Sydney)?|University of New South Wales|Macquarie University)(?:\s+(?:Camperdown|Darlington|Kensington|Parramatta)(?:\s+campus|校区)?)?',re.I)


def pending_question(conversation):
    brief=conversation.get('rental_brief',{})
    if conversation.get('dialogue_mode')!='recommend_areas':return None
    fields=commute.question_fields(brief)
    if not fields and not brief.get('destination_id') and conversation.get('commute_destination_options'):
        fields=['destination_id']
    if not fields:return None
    return {'task':'commute','fields':fields,'question':commute.next_question(brief),
            'destination_options':[{'id':o['id'],'label':o['label']} for o in conversation.get('commute_destination_options',[])]}


def region_continuation(conversation,text):
    shown={a['suburb'] for m in conversation['messages'][-20:] for a in m.get('area_advice',{}).get('areas',[])}
    # Exact product-generated action text, sent explicitly by the user. A named
    # area in an unrelated message or a negated request cannot trigger this.
    for suburb in shown:
        pattern=r'(?:保持我的预算和房型要求[，,]\s*)?按\s*'+re.escape(suburb)+r'\s*区域继续推荐房源[，,]\s*并核对到学校或公司的通勤[。.!！]?'
        if re.fullmatch(pattern,text.strip(),flags=re.I):return suburb
    return None


def explicit_transition(conversation,text):
    suburb=region_continuation(conversation,text)
    if suburb:
        return {'intent':'recommend_areas','brief_patch':{'suburb':suburb,'recommend_areas':True}}
    pending=pending_question(conversation)
    if pending and 'destination_query' in pending['fields'] and SCHOOL_REPLY.fullmatch(text.strip()):
        return {'intent':'recommend_areas','brief_patch':{'destination_query':text.strip()}}
    return None


def partial_region(text,value,catalog):
    """A literal English prefix is not a confirmed full suburb name."""
    if not isinstance(value,dict):return None,value
    patch=value.get('brief_patch',{})
    if not isinstance(patch,dict):return None,value
    filters=value.get('filters',{})
    targets=[patch.get('suburb'),filters.get('suburb') if isinstance(filters,dict) else None,
             *(value.get('areas',[]) if isinstance(value.get('areas',[]),list) else [])]
    for target in targets:
        if not isinstance(target,str) or re.search(r'(?<![a-z])'+re.escape(target)+r'(?![a-z])',text,re.I):continue
        for token in re.findall(r'[A-Za-z]{3,}',text):
            if token.casefold() in {s.casefold() for s in catalog.suburbs}:continue
            if target.casefold().startswith(token.casefold()) and any(s.casefold().startswith(token.casefold()) for s in catalog.suburbs):
                cleaned=deepcopy(value)
                if 'brief_patch' in cleaned:cleaned['brief_patch'].pop('suburb',None)
                cleaned.pop('areas',None)
                if cleaned.get('intent')=='search' and isinstance(filters,dict):
                    kept={k:v for k,v in filters.items() if k in ('min_bedrooms','min_bathrooms','min_car_spaces')}
                    if 'max_weekly_rent' in filters:kept.update(budget_amount=filters['max_weekly_rent'],budget_period='week')
                    cleaned={'intent':'collect_preferences','brief_patch':kept}
                return token,cleaned
    return None,value


def repair_route(ctx,conversation,text,intent,catalog):
    explicit=explicit_transition(conversation,text)
    if explicit:return explicit,[]
    pending=pending_question(conversation)
    if not pending:return area_followup(ctx,conversation,text,intent,catalog)
    repairable={'area_advice','collect_preferences','recommend_areas','search','clarify','other'}
    if intent['intent'] not in repairable:return intent,[]
    if 'destination_query' in pending['fields'] and SCHOOL_REPLY.fullmatch(text.strip()):
        return {'intent':'recommend_areas','brief_patch':{'destination_query':text.strip()}},[]
    if intent['intent'] in ('collect_preferences','recommend_areas','search'):return intent,[]
    # Retry only a misrouted read response, with a small, task-bound extraction.
    # No contacts, draft profile, lease material or unrelated transcript is sent.
    schema={'type':'object','required':['is_reply','brief_patch'],'additionalProperties':False,
            'properties':{'is_reply':{'type':'boolean'},'brief_patch':BRIEF_SCHEMA}}
    try:
        recovered,call=ctx.ai_provider.call({'task':'assistant_commute_reply','message':text,
            'pending_question':pending,'rental_brief':conversation.get('rental_brief',{}),
            'suburbs':catalog.suburbs,'response_schema':schema})
        if list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(recovered)):
            return intent,[call]
        if not recovered['is_reply']:return intent,[call]
        value=validate_intent({'intent':'recommend_areas','brief_patch':recovered['brief_patch']},catalog,[])
        # A claimed reply with no explicit new value asks a focused question;
        # it cannot accidentally redisplay an old area comparison.
        return value,[call]
    except ProviderError as error:
        return intent,[error.call]
    except ApiError:
        return intent,[call]


def area_followup(ctx,conversation,text,intent,catalog):
    """Disambiguate continuing a shown area versus asking for more area facts."""
    if intent['intent']!='area_advice':return intent,[]
    latest=next((m for m in reversed(conversation['messages']) if m['role']=='assistant'),{})
    offered=[a['suburb'] for a in latest.get('area_advice',{}).get('areas',[])]
    if not offered:return intent,[]
    schema={'type':'object','required':['continue_housing','brief_patch'],'additionalProperties':False,
            'properties':{'continue_housing':{'type':'boolean'},'brief_patch':BRIEF_SCHEMA}}
    try:
        result,call=ctx.ai_provider.call({'task':'assistant_area_followup','message':text,
            'offered_suburbs':offered,'rental_brief':conversation.get('rental_brief',{}),'response_schema':schema})
        if list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(result)):return intent,[call]
        if not result['continue_housing']:return intent,[call]
        patch=result['brief_patch']
        if patch.get('suburb') not in offered:return intent,[call]
        value=validate_intent({'intent':'recommend_areas','brief_patch':{**intent.get('brief_patch',{}),**patch}},catalog,[])
        return value,[call]
    except ProviderError as error:return intent,[error.call]
    except ApiError:return intent,[call]
