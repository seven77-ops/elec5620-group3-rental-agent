"""Resume ordinary preference intake from short, explicitly supplied answers."""
import re
from jsonschema import Draft202012Validator, FormatChecker
from ..ai.provider import ProviderError
from ..common import ApiError
from .dialogue import BRIEF_SCHEMA, next_question
from .intents import validate_intent
from .budget_evidence import stated_amount


def pending(conversation):
    if conversation.get('dialogue_mode')!='collect_preferences':return None
    brief=conversation.get('rental_brief',{})
    if not brief:return None
    if 'budget_amount' not in brief:fields=['budget_amount','budget_scope']
    elif brief.get('budget_period','unknown') in ('unknown','month'):
        fields=['budget_period'] if brief.get('budget_period','unknown')=='unknown' else ['budget_amount','budget_period']
        if brief.get('budget_scope','unknown')=='unknown':fields.append('budget_scope')
    elif brief.get('budget_scope','unknown')=='unknown':fields=['budget_scope']
    elif 'suburb' not in brief:fields=['suburb']
    else:
        fields=[f for f in ('min_bedrooms','min_bathrooms','min_car_spaces') if f not in brief]
        if not fields and 'occupants' not in brief:fields=['occupants']
    if not fields:return None
    return {'task':'rental_preferences','fields':fields,'question':next_question(brief)}


def explicit(conversation,text,question=None):
    question=question or pending(conversation)
    if not question:return None
    answer=text.strip().strip('。.!！').casefold()
    patch={}
    if 'budget_scope' in question['fields']:
        scopes={'整套':'whole_property','整租':'whole_property','一整套':'whole_property','按整套':'whole_property',
                'whole property':'whole_property','每人':'per_person','按人':'per_person','per person':'per_person',
                '每个房间':'per_room','每间':'per_room','按房间':'per_room','per room':'per_room'}
        if answer in scopes:patch['budget_scope']=scopes[answer]
    if 'budget_period' in question['fields']:
        if answer in ('每周','按周','周租','weekly','per week') and conversation.get('rental_brief',{}).get('budget_period')!='month':patch['budget_period']='week'
        elif answer in ('每月','按月','月租','monthly','per month'):patch['budget_period']='month'
    if question['fields']==['occupants']:
        match=re.fullmatch(r'(\d{1,3}|一|两|二|三|四|五|六|七|八|九|十)(?:个)?人(?:入住)?',answer)
        if match:
            digits={'一':1,'两':2,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
            count=digits.get(match[1]) or int(match[1])
            if 1<=count<=100:patch['occupants']=count
    if answer in ('不限','没有要求','都不限') and all(f.startswith('min_') for f in question['fields']):
        patch.update({f:0 for f in question['fields']})
    return {'intent':'recommend_areas' if question['task']=='commute' else 'collect_preferences','brief_patch':patch} if patch else None


def repair(ctx,conversation,text,intent,catalog,question):
    if intent['intent'] not in ('collect_preferences','clarify','other'):return intent,[]
    before=conversation.get('rental_brief',{})
    patch=intent.get('brief_patch',{})
    if any(k in patch and patch[k]!=before.get(k) for k in question['fields']):return intent,[]
    schema={'type':'object','required':['is_reply','brief_patch'],'additionalProperties':False,
            'properties':{'is_reply':{'type':'boolean'},'brief_patch':BRIEF_SCHEMA}}
    try:
        result,call=ctx.ai_provider.call({'task':'assistant_preferences_reply','message':text,
            'pending_question':question,'rental_brief':before,'suburbs':catalog.suburbs,'response_schema':schema})
        if list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(result)) or not result['is_reply']:
            return intent,[call]
        if not any(k in result['brief_patch'] and result['brief_patch'][k]!=before.get(k) for k in question['fields']):
            return intent,[call]
        value=validate_intent({'intent':'collect_preferences','brief_patch':{**patch,**result['brief_patch']}},catalog,[])
        return value,[call]
    except ProviderError as error:return intent,[error.call]
    except ApiError:return intent,[call]


def guard_monthly(conversation,text,intent):
    """A known monthly cap needs a stated weekly amount, not a unit-only reply."""
    if conversation.get('rental_brief',{}).get('budget_period')!='month':return intent
    if intent['intent']=='search' and 'max_weekly_rent' in intent.get('filters',{}):
        return intent if stated_amount(text,intent['filters']['max_weekly_rent']) else {'intent':'collect_preferences','brief_patch':{}}
    patch=intent.get('brief_patch',{})
    if patch.get('budget_period')!='week':return intent
    if stated_amount(text,patch.get('budget_amount')):return intent
    safe={k:v for k,v in patch.items() if k not in ('budget_period','budget_amount')}
    return {**intent,'brief_patch':safe}
