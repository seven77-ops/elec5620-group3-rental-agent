"""Conversation-only requirements: explicit values, focused questions, no profile writes."""
from copy import deepcopy
from .commute import COMMUTE_PROPERTIES
from ..areas.evidence import PRIORITIES_SCHEMA

COUNT = {'type':'integer','minimum':0,'maximum':100}
BRIEF_SCHEMA = {'type':'object','additionalProperties':False,'properties':{
    'suburb':{'type':['string','null']},
    'lifestyle_priorities':PRIORITIES_SCHEMA,
    'budget_amount':{'type':'number','exclusiveMinimum':0,'maximum':1000000000000},
    'budget_period':{'enum':['week','month','unknown']},
    'budget_scope':{'enum':['per_person','per_room','whole_property','unknown']},
    'occupants':{'type':'integer','minimum':1,'maximum':100},
    'min_bedrooms':COUNT,'min_bathrooms':COUNT,'min_car_spaces':COUNT,
    'rental_mode':{'enum':['private_room','shared_room','whole_property','student_accommodation']},**COMMUTE_PROPERTIES}}


def merge_brief(conversation,intent):
    brief={**deepcopy(conversation.get('rental_brief',{})),**deepcopy(intent.get('brief_patch',{}))}
    if brief and intent['intent']=='search':
        for key,value in intent.get('filters',{}).items():
            if key in BRIEF_SCHEMA['properties']: brief[key]=value
            elif key=='usyd_mode':brief['commute_mode']=value
            elif key=='usyd_max_minutes':brief['commute_max_minutes']=value;brief['commute_hard_limit']=True
            elif key in ('usyd_arrival_time','usyd_travel_day','usyd_travel_date','usyd_max_transfers'):brief[key[5:]]=value
            elif key=='max_weekly_rent':
                brief['budget_amount']=value
                brief['budget_period']='week'
    return {k:v for k,v in brief.items() if k not in ("arrival_time","travel_day","travel_date")}


def brief_summary(brief):
    parts=[]
    from ..areas.evidence import TOPICS
    if brief.get('lifestyle_priorities'):
        parts.append('生活偏好：'+'、'.join(TOPICS[t] for t in brief['lifestyle_priorities']))
    if 'suburb' in brief: parts.append(brief['suburb'] or '区域不限')
    if 'occupants' in brief: parts.append(f"{brief['occupants']}人")
    for field,label in (('min_bedrooms','卧'),('min_bathrooms','卫'),('min_car_spaces','车位')):
        if field in brief: parts.append(f"至少{brief[field]}{label}" if brief[field] else label+'不限')
    if 'budget_amount' in brief:
        period={'week':'/周','month':'/月'}.get(brief.get('budget_period'),'（周期待确认）')
        scope={'per_person':'每人','per_room':'每间','whole_property':'整套'}.get(brief.get('budget_scope'),'计价对象待确认')
        parts.append(f"预算上限 {brief['budget_amount']:g} 澳元{period}，{scope}")
    return '、'.join(parts)


def next_question(brief):
    """Ask the next small group only; template profile defaults are never answers."""
    if 'budget_amount' not in brief and 'suburb' not in brief:
        return '可以，我们一步一步来。你想住哪个区域？每周最高预算大概多少？'
    if 'budget_amount' not in brief: return '每周最高预算大概多少？这个金额是整套还是每人承担的预算？'
    period=brief.get('budget_period','unknown'); scope=brief.get('budget_scope','unknown')
    if period=='month': return '你给的是月预算。目前房源按周报价，你希望每周最高控制在多少澳元？'
    if period=='unknown' and scope=='unknown': return f"这 {brief['budget_amount']:g} 澳元是整套每周，还是每人每周？如果是月预算，也请告诉我。"
    if period=='unknown': return f"这 {brief['budget_amount']:g} 澳元是每周还是每月的上限？"
    if scope=='unknown': return '这个每周预算是整套、每个房间，还是每人承担的金额？'
    if 'suburb' not in brief: return '想住哪个区域？也可以说“不限区域”。'
    missing=[label for key,label in (('min_bedrooms','卧室'),('min_bathrooms','浴室'),('min_car_spaces','车位')) if key not in brief]
    if missing: return '对'+'、'.join(missing)+'数量有什么要求？没有要求的可以说“不限”。'
    if 'occupants' not in brief: return '一共几个人入住？'
    return None


def brief_filters(brief):
    result={k:brief[k] for k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces') if k in brief and brief[k] is not None}
    result['max_weekly_rent']=brief['budget_amount']
    if brief.get('commute_mode') and brief.get('commute_max_minutes'):
        result.update(usyd_mode=brief['commute_mode'],usyd_max_minutes=brief['commute_max_minutes'])
        for key in ('max_transfers',):
            if brief.get(key) is not None:result['usyd_'+key]=brief[key]
    return result


def brief_profile_patch(brief):
    patch={'budget':{'currency':'AUD','period':'week','maximum':brief['budget_amount'],'scope':brief['budget_scope']},
        'housing_preferences':{k:brief[k] for k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces') if k in brief},
        'occupants':brief['occupants']}
    if 'rental_mode' in brief: patch['rental_mode']=brief['rental_mode']
    if brief.get('commute_mode') and brief.get('commute_max_minutes'):
        patch['student_commute']={'mode':brief['commute_mode'],'maximum_minutes':brief['commute_max_minutes']}
        for key in ('max_transfers',):
            if brief.get(key) is not None:patch['student_commute'][key]=brief[key]
    return patch


def profile_brief(profile):
    housing=profile.get('housing_preferences',{})
    budget=profile.get('budget',{})
    result={key:housing[key] for key in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces') if key in housing}
    for source,target in (('maximum','budget_amount'),('period','budget_period'),('scope','budget_scope')):
        if source in budget: result[target]=budget[source]
    student=profile.get('student_commute',{})
    if student:
        result.update(commute_mode=student['mode'],commute_max_minutes=student['maximum_minutes'],commute_hard_limit=True)
        for key in ('max_transfers',):
            if student.get(key) is not None:result[key]=student[key]
    result.update({key:profile[key] for key in ('occupants','rental_mode') if key in profile})
    return result
