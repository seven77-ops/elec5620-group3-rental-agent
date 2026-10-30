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
        parts.append('Lifestyle priorities: '+', '.join(TOPICS[t] for t in brief['lifestyle_priorities']))
    if 'suburb' in brief: parts.append(brief['suburb'] or 'Any suburb')
    if 'occupants' in brief: parts.append(f"{brief['occupants']} occupants")
    for field,label in (('min_bedrooms','bedrooms'),('min_bathrooms','bathrooms'),('min_car_spaces','parking spaces')):
        if field in brief: parts.append(f"At least {brief[field]} {label}" if brief[field] else label+' unrestricted')
    if 'budget_amount' in brief:
        period={'week':'/week','month':'/month'}.get(brief.get('budget_period'),' (period unconfirmed)')
        scope={'per_person':'per person','per_room':'per room','whole_property':'whole property'}.get(brief.get('budget_scope'),'rent scope unconfirmed')
        parts.append(f"Budget limit {brief['budget_amount']:g} AUD{period}, {scope}")
    return ', '.join(parts)


def next_question(brief):
    """Ask the next small group only; template profile defaults are never answers."""
    if 'budget_amount' not in brief and 'suburb' not in brief:
        return 'Let us take it step by step. Which suburb would you like to live in, and what is your maximum weekly budget?'
    if 'budget_amount' not in brief: return 'What is your maximum weekly budget? Is that for the whole property or per person?'
    period=brief.get('budget_period','unknown'); scope=brief.get('budget_scope','unknown')
    if period=='month': return 'You gave a monthly budget. Listings use weekly rent. What is your maximum weekly budget in AUD?'
    if period=='unknown' and scope=='unknown': return f"Is AUD {brief['budget_amount']:g} per week for the whole property or per person? Please say if it is a monthly budget."
    if period=='unknown': return f"Is AUD {brief['budget_amount']:g} your weekly or monthly limit?"
    if scope=='unknown': return 'Is this weekly budget for the whole property, per room or per person?'
    if 'suburb' not in brief: return 'Which suburb would you prefer? You can also say any suburb.'
    missing=[label for key,label in (('min_bedrooms','bedrooms'),('min_bathrooms','bathrooms'),('min_car_spaces','parking spaces')) if key not in brief]
    if missing: return 'What are your requirements for '+', '.join(missing)+'? Say unrestricted for any that do not matter.'
    if 'occupants' not in brief: return 'How many people will live there?'
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
