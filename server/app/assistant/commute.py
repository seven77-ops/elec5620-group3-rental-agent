"""Explicit commute intake and a source-bound, case-owned shared preview."""
from copy import deepcopy
from datetime import datetime,timezone
import re
import json
from ..common import ApiError,require,now
from ..commute.usyd import DESTINATION,MODES,student_brief

COMMUTE_PROPERTIES={
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
        data=json.loads(path.read_text(encoding='utf-8'))
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
    if 'budget_amount' not in brief:return '不熟悉区域也没关系。每周最高预算大概多少，是整套、每间还是每人的预算？需要几间卧室？'
    if brief.get('budget_period')!='week':return '这笔预算是每周还是每月？房源按周报价，请确认每周最高金额。'
    if brief.get('budget_scope') not in ('whole_property','per_room','per_person'):return '这个每周预算是整套、每个房间，还是每人承担的金额？'
    if 'min_bedrooms' not in brief:return '至少需要几间卧室？浴室和车位有要求的话也可以一起告诉我。'
    if 'commute_max_minutes' not in brief:return '到悉大主校区，单程最多接受多少分钟？'
    if not brief.get('commute_mode'):return '通勤选公共交通、火车、地铁、公交车、开车、骑行还是步行？'
    return None


def prepare(ctx,conversation,brief,patch,text,allow_external,refresh=False):
    for key in ('arrival_time','travel_day','travel_date'):brief.pop(key,None)
    query=patch.get('destination_query','')
    if query and (re.search(r'camden|cumberland|westmead|unsw|new south wales|technology|macquarie|公司|上班|新南|科技大学|麦考',query,re.I)):
        brief.update(student_brief(brief))
        return {'intent':'outside_scope','agent':'assistant','content':'当前找房只面向悉尼大学 Camperdown / Darlington 主校区学生，暂不覆盖其他校区、其他学校或公司通勤。你的预算和房型需求已保留。','listings':[],'actions':[]},[]
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
        answer['content']='需求已记下。本次没有启用外部交通查询；已保留到悉大主校区的条件，不会猜测实时通勤。'
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
        reasons.append('已改为悉大主校区专用找房，请重新生成到主校区的通勤推荐。')
    if activity and (activity['conversation_id']!=saved['conversation_id'] or activity['brief']!=saved['brief']):
        reasons.append('已有新的区域或通勤需求，请在最新对话重新生成推荐。')
    if not conversation or conversation.get('rental_brief')!=saved['brief']:reasons.append('聊天需求已更新，请重新生成推荐。')
    if signature(case)!=saved['case_signature']:reasons.append('已保存的案例资料已更新，请重新核对推荐。')
    if saved['catalog_fingerprint']!=ctx.settings.catalog.fingerprint:reasons.append('房源数据已更新，请重新生成推荐。')
    evidence_fingerprint=saved.get('message',{}).get('commute_recommendation',{}).get('area_knowledge_fingerprint')
    if evidence_fingerprint:
        from ..areas.evidence import AreaKnowledge, needs_review
        if evidence_fingerprint!=AreaKnowledge().fingerprint:reasons.append('区域资料已更新，请重新生成推荐。')
        if needs_review(saved['message']['commute_recommendation']):reasons.append('区域资料已到重新核对时间，请重新生成推荐。')
    # Approximate rental discovery has no thirty-minute arrival/session deadline.
    # Source-route freshness is checked by snapshot.observation during matching.
    result.update(stale=bool(reasons),stale_reasons=reasons)
    return result
