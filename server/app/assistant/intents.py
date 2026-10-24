"""Strict model boundary. Model output is intent data, never executable instructions."""
from copy import deepcopy
import math
from jsonschema import Draft202012Validator, FormatChecker
from ..common import ApiError, load, require
from ..adapters.business import validate_profile
from .dialogue import BRIEF_SCHEMA
from .living import INTENT_PROPERTIES, LIVING_INTENT_SCHEMA

INTENTS = {'area_advice','collect_preferences','recommend_areas','search','update_preferences','compare','explain','market','select','clarify','contract','aftercare','followup','draft_contract','living_services','workflow','other'}
CLARIFICATION_REASONS = ('budget_units','reference','unknown_fact','missing_preferences','conflicting_preferences')
PROFILE_SCHEMA = load('agent2/schemas/rental-profile.schema.json')
PATCH_SCHEMA = deepcopy(PROFILE_SCHEMA)
PATCH_SCHEMA['required'] = []
for key in ('schema_version','search_id','profile_version'):
    PATCH_SCHEMA['properties'].pop(key)
for value in PATCH_SCHEMA['properties'].values():
    if value.get('type') == 'object': value['required'] = []
PATCH_VALIDATOR = Draft202012Validator(PATCH_SCHEMA, format_checker=FormatChecker())


def model_require(ok):
    require(ok,502,'ai_invalid_response','模型返回的数据格式无效，请重试。')


def finite_tree(value):
    if type(value) is float: model_require(math.isfinite(value))
    elif isinstance(value,dict):
        for v in value.values(): finite_tree(v)
    elif isinstance(value,list):
        for v in value: finite_tree(v)


def validate_intent(value,catalog,known_ids):
    model_require(isinstance(value,dict) and 'intent' in value and
        not set(value)-{'intent','areas','filters','brief_patch','preference_patch','listing_ids','clarification','clarification_reason','market','steps',*INTENT_PROPERTIES})
    model_require(isinstance(value['intent'],str) and value['intent'] in INTENTS)
    finite_tree(value)
    if 'areas' in value:
        names=value['areas']
        model_require(isinstance(names,list) and 1<=len(names)<=4 and all(isinstance(s,str) and s in catalog.suburbs for s in names))
        model_require(len(names)==len(set(names)))
    if value['intent']=='workflow':
        model_require(not list(Draft202012Validator(workflow_schema()).iter_errors(value)))
        steps=value['steps']
        model_require(sum(step['kind']=='prepare_enquiry' for step in steps)<=1)
        for step in steps:
            if 'filters' in step:
                try: catalog.filters(step['filters'])
                except (ApiError,TypeError): model_require(False)
            model_require(set(step.get('listing_ids',[]))<=set(known_ids))
    if value['intent']=='living_services':
        model_require(not list(Draft202012Validator(LIVING_INTENT_SCHEMA).iter_errors(value)))
        model_require(value['service_action']!='report_repair' or bool(value.get('repair')))
    if 'filters' in value:
        try: catalog.filters(value['filters'])
        except (ApiError,TypeError): model_require(False)
    if 'preference_patch' in value:
        model_require(isinstance(value['preference_patch'],dict) and not list(PATCH_VALIDATOR.iter_errors(value['preference_patch'])))
    if 'brief_patch' in value:
        patch=value['brief_patch']
        model_require(isinstance(patch,dict) and not list(Draft202012Validator(BRIEF_SCHEMA).iter_errors(patch)))
        model_require(patch.get('suburb') is None or patch['suburb'] in catalog.suburbs)
    if 'listing_ids' in value:
        ids=value['listing_ids']
        model_require(isinstance(ids,list) and len(ids)<=5 and all(isinstance(i,str) for i in ids))
        model_require(len(ids)==len(set(ids)) and set(ids)<=set(known_ids))
    if 'clarification_reason' in value:
        model_require(isinstance(value['clarification_reason'],str) and value['clarification_reason'] in CLARIFICATION_REASONS)
    if 'clarification' in value:
        model_require(isinstance(value['clarification'],str) and 0<len(value['clarification'])<=300)
    if 'market' in value:
        m=value['market']
        model_require(isinstance(m,dict) and {'postcode','bedrooms','rent_scope'}<=set(m) and
            not set(m)-{'postcode','bedrooms','rent_scope','weekly_rent'})
        model_require(isinstance(m['postcode'],str) and len(m['postcode'])==4 and m['postcode'].isascii() and m['postcode'].isdigit())
        model_require(type(m['bedrooms']) is int and 0<=m['bedrooms']<=20 and isinstance(m['rent_scope'],str) and m['rent_scope'] in {'whole_property','per_room','per_person'})
        model_require(m.get('weekly_rent') is None or (type(m['weekly_rent']) in (int,float) and 0<=m['weekly_rent']<=100000))
    # Each operation accepts only data it can actually execute.
    allowed={'area_advice':{'areas','brief_patch'},'collect_preferences':{'brief_patch'},'recommend_areas':{'brief_patch'},'search':{'filters'},'update_preferences':{'preference_patch'},'compare':{'listing_ids'},
        'explain':{'listing_ids'},'select':{'listing_ids'},'market':{'market','listing_ids'},
        'clarify':{'clarification','clarification_reason'},'contract':set(),'aftercare':set(),'followup':set(),'draft_contract':set(),'living_services':set(INTENT_PROPERTIES),'workflow':{'steps'},'other':set()}
    model_require(set(value)-{'intent'}<=allowed[value['intent']])
    return value


def merge_profile(profile,patch):
    merged=deepcopy(profile)
    for key,value in patch.items():
        if isinstance(value,dict): merged[key]={**merged.get(key,{}),**value}
        else: merged[key]=deepcopy(value)
    validate_profile(merged)
    return merged


def response_schema():
    """Authoritative provider-facing JSON schema, including exact nesting and enums."""
    number={'type':'number','minimum':0,'maximum':1000000000000}
    count={'type':'integer','minimum':0,'maximum':100}
    ids={'type':'array','maxItems':5,'uniqueItems':True,'items':{'type':'string'}}
    filters={'type':'object','additionalProperties':False,'properties':{
        'suburb':{'type':['string','null']},'min_bedrooms':count,'min_bathrooms':count,
        'min_car_spaces':count,'max_weekly_rent':number,
        'sort':{'enum':['rent_asc','rent_desc','bedrooms_desc']}}}
    market={'type':'object','required':['postcode','bedrooms','rent_scope'],'additionalProperties':False,
        'properties':{'postcode':{'type':'string','pattern':'^[0-9]{4}$'},
            'bedrooms':{'type':'integer','minimum':0,'maximum':20},
            'rent_scope':{'enum':['whole_property','per_room','per_person']},
            'weekly_rent':{'type':['number','null'],'minimum':0,'maximum':100000}}}
    fields={'area_advice':{'areas':{'type':'array','minItems':1,'maxItems':4,'uniqueItems':True,'items':{'type':'string'}},'brief_patch':BRIEF_SCHEMA},
        'collect_preferences':{'brief_patch':BRIEF_SCHEMA},'recommend_areas':{'brief_patch':BRIEF_SCHEMA},'search':{'filters':filters},'update_preferences':{'preference_patch':PATCH_SCHEMA},
        'compare':{'listing_ids':ids},'explain':{'listing_ids':ids},'select':{'listing_ids':ids},
        'market':{'market':market,'listing_ids':ids},
        'clarify':{'clarification':{'type':'string','minLength':1,'maxLength':300},
            'clarification_reason':{'enum':list(CLARIFICATION_REASONS)}},
        'contract':{},'aftercare':{},'followup':{},'draft_contract':{},'other':{}}
    return {'oneOf':[{'type':'object','required':['intent'],'additionalProperties':False,
        'properties':{'intent':{'const':name},**properties}} for name,properties in fields.items()]+[LIVING_INTENT_SCHEMA,workflow_schema(filters)]}


def workflow_schema(filters=None):
    if filters is None:
        filters={'type':'object','additionalProperties':False,'properties':{
            'suburb':{'type':['string','null']},
            **{key:{'type':'integer','minimum':0,'maximum':100} for key in ('min_bedrooms','min_bathrooms','min_car_spaces')},
            'max_weekly_rent':{'type':'number','minimum':0,'maximum':1000000000000},
            'sort':{'enum':['rent_asc','rent_desc','bedrooms_desc']}}}
    ids={'type':'array','maxItems':5,'uniqueItems':True,'items':{'type':'string'}}
    steps=[{'type':'object','additionalProperties':False,'required':['kind'],
        'properties':{'kind':{'const':'search'},'filters':filters}}]
    for kind in ('compare','explain','prepare_enquiry'):
        steps.append({'type':'object','additionalProperties':False,'required':['kind'],
            'properties':{'kind':{'const':kind},'listing_ids':ids,
                'reference':{'enum':['selected','previous','cheapest']}},
            'not':{'required':['listing_ids','reference']}})
    return {'type':'object','required':['intent','steps'],'additionalProperties':False,
        'properties':{'intent':{'const':'workflow'},'steps':{'type':'array','minItems':1,'maxItems':3,'items':{'oneOf':steps},
            'contains':{'type':'object','required':['kind'],'properties':{'kind':{'const':'prepare_enquiry'}}},'minContains':0,'maxContains':1}}}
