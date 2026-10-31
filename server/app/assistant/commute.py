"""Explicit commute intake and a source-bound, case-owned shared preview."""
from copy import deepcopy
from datetime import datetime,timezone
import re
import json
from ..common import ApiError,require,now
from ..commute.usyd import DESTINATION,MODES,student_brief

COMMUTE_PROPERTIES={
    'commute_preference':{'enum':['include','skip']},
    'recommend_areas':{'type':'boolean'},
    'destination_query':{'type':'string','minLength':2,'maxLength':180},
    'destination_id':{'type':'string','minLength':1,'maxLength':100},
    'arrival_time':{'type':'string','pattern':r'^([01][0-9]|2[0-3]):[0-5][0-9]$'},
    'commute_max_minutes':{'type':'integer','minimum':1,'maximum':240},
    'commute_hard_limit':{'type':'boolean'},
    'commute_priority':{'enum':['balanced','rent','commute']},
    'max_transfers':{'type':'integer','minimum':0,'maximum':5},
    'travel_day':{'enum':['weekday','weekend']},
    'travel_date':{'type':'string','format':'date'},
    'commute_mode':{'enum':list(MODES)}}

ALIASES={'悉尼大学':'University of Sydney','悉大':'University of Sydney',
    '新南威尔士大学':'University of New South Wales','新南':'University of New South Wales',
    '悉尼科技大学':'University of Technology','麦考瑞大学':'Macquarie University',
    '西悉尼大学':'Western Sydney University'}


def normalized_query(query):
    query=re.sub(r'\bUSYD\b','University of Sydney',query,flags=re.I)
    query=re.sub(r'\bUNSW\b','University of New South Wales',query,flags=re.I)
    for original,replacement in sorted(ALIASES.items(),key=lambda pair:-len(pair[0])):
        query=query.replace(original,' '+replacement+' ')
    query=re.sub(r'\bUTS\b|University of Technology Sydney','University of Technology',query,flags=re.I)
    return ' '.join(query.replace('校区',' ').split())


def location_points(catalog):
    path=catalog.path.with_name('locations.json')
    if not path.is_file():return {}
    try:
        data=json.loads(path.read_text())
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(data['queried_at'].replace('Z','+00:00'))).total_seconds()
        if data.get('catalog_fingerprint')!=catalog.fingerprint or not 0<=age<=90*86400:return {}
        return data['points'] if isinstance(data.get('points'),dict) else {}
    except (OSError,KeyError,ValueError,TypeError,AttributeError):return {}


def resolver_for(ctx):
    if not hasattr(ctx,'commute_resolver'):
        from ..commute.locations import LocationResolver
        ctx.commute_resolver=LocationResolver(points=location_points(ctx.settings.catalog))
    return ctx.commute_resolver


def plan_routes(ctx,brief,destination,allow_external,previous_reports=None):
    from ..commute.planner import CommutePlanner
    from .areas import enrich_commute
    return enrich_commute(CommutePlanner(ctx,resolver=resolver_for(ctx)).prepare(student_brief(brief),destination,allow_external=allow_external,
        previous_reports=previous_reports),ctx.settings.catalog)


def question_fields(brief):
    if 'budget_amount' not in brief:return ['budget_amount','budget_scope','min_bedrooms']
    if brief.get('budget_period')!='week':return ['budget_period']
    if brief.get('budget_scope') not in ('whole_property','per_room','per_person'):return ['budget_scope']
    if 'min_bedrooms' not in brief:return ['min_bedrooms']
    if 'commute_max_minutes' not in brief:return ['commute_max_minutes']
    if not brief.get('commute_mode'):return ['commute_mode']
    return []


def next_question(brief):
    if 'budget_amount' not in brief:return 'You do not need to know the suburbs yet. What is your maximum weekly budget, is it for the whole property, per room or per person, and how many bedrooms do you need?'
    if brief.get('budget_period')!='week':return 'Is this budget weekly or monthly? Listings use weekly rent, so confirm your maximum weekly amount.'
    if brief.get('budget_scope') not in ('whole_property','per_room','per_person'):return 'Is this weekly budget for the whole property, per room or per person?'
    if 'min_bedrooms' not in brief:return 'How many bedrooms do you need at minimum? Add bathroom and parking requirements if you have any.'
    if 'commute_max_minutes' not in brief:return 'What is your maximum one-way commute in minutes to the USYD main campus?'
    if not brief.get('commute_mode'):return 'Which commute mode do you prefer: public transport (any combination), driving, cycling or walking? You can also request routes that include train, metro or bus.'
    return None


def prepare(ctx,conversation,brief,patch,text,allow_external,refresh=False):
    for key in ('arrival_time','travel_day','travel_date'):brief.pop(key,None)
    query=patch.get('destination_query','')
    if query and (re.search(r'camden|cumberland|westmead|unsw|new south wales|technology|macquarie|公司|上班|新南|科技大学|麦考',query,re.I)):
        brief.update(student_brief(brief))
        return {'intent':'outside_scope','agent':'assistant','content':'Rental discovery currently covers University of Sydney Camperdown / Darlington students only. Other campuses, universities and workplace commutes are outside its scope. Your budget and property requirements are retained.','listings':[],'actions':[]},[]
    brief['recommend_areas']=True
    brief.update(student_brief(brief))
    options=[]
    answer={'intent':'recommend_areas','agent':'agent1','content':'','listings':[],'actions':[]}
    question=next_question(brief)
    if question:
        answer['content']=question
        answer['commute_question']={'fields':question_fields(brief)}
        return answer,options
    if not allow_external:
        answer['content']='Requirements noted. External transit lookup is not enabled. Your USYD main campus requirements are retained; live travel times have not been inferred.'
        return answer,options
    destination=deepcopy(DESTINATION)
    previous=[m['commute_recommendation'] for m in conversation.get('messages',[]) if m.get('commute_recommendation')]
    refresh=refresh or bool(previous and previous[-1].get('criteria')==brief)
    answer=plan_routes(ctx,deepcopy(brief),deepcopy(destination),allow_external)
    answer.setdefault('intent','recommend_areas')
    from .recommendation_order import arrange
    answer=arrange(answer,conversation,brief,refresh)
    return answer,options


def brief_context(conversation):
    return {'destination_options':[],
            'destination':deepcopy(DESTINATION),'audience':'USYD students at Camperdown/Darlington only',
            'public_transport_available':'requires_server_lookup','supported_modes':list(MODES)}


def latest(ctx,case_id):
    from .service import signature
    with ctx.repo.transaction() as db:
        case=ctx.get(db,'case',case_id)
        saved=ctx.repo.get(db,'assistant_commute_report',case_id)
        if not saved:return None
        conversation=ctx.repo.get(db,'assistant_conversation',saved['conversation_id'])
        activity=ctx.repo.get(db,'assistant_commute_activity',case_id)
    result=deepcopy(saved)
    reasons=[]
    if saved.get('message',{}).get('commute_recommendation',{}).get('destination',{}).get('id')!=DESTINATION['id']:
        reasons.append('Discovery now targets the USYD main campus. Generate commute recommendations again.')
    if activity and (activity['conversation_id']!=saved['conversation_id'] or activity['brief']!=saved['brief']):
        reasons.append('Suburb or commute requirements changed. Generate recommendations again in the latest conversation.')
    if not conversation or conversation.get('rental_brief')!=saved['brief']:reasons.append('Conversation requirements changed. Generate recommendations again.')
    if signature(case)!=saved['case_signature']:reasons.append('Saved case details changed. Review the recommendations again.')
    if saved['catalog_fingerprint']!=ctx.settings.catalog.fingerprint:reasons.append('Listing data changed. Generate recommendations again.')
    evidence_fingerprint=saved.get('message',{}).get('commute_recommendation',{}).get('area_knowledge_fingerprint')
    if evidence_fingerprint:
        from ..areas.evidence import AreaKnowledge, needs_review
        if evidence_fingerprint!=AreaKnowledge().fingerprint:reasons.append('Area information changed. Generate recommendations again.')
        if needs_review(saved['message']['commute_recommendation']):reasons.append('Area information is due for review. Generate recommendations again.')
    # Approximate rental discovery has no thirty-minute arrival/session deadline.
    # Source-route freshness is checked by snapshot.observation during matching.
    result.update(stale=bool(reasons),stale_reasons=reasons)
    return result
