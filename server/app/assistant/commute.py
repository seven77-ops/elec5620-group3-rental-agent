"""Explicit commute intake and a source-bound, case-owned shared preview."""
from copy import deepcopy
from datetime import datetime,timezone
import re
import json
from ..common import ApiError,require,now

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
    'commute_mode':{'enum':['public_transport','walk','drive','bike']}}

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


def plan_routes(ctx,brief,destination,allow_external):
    from ..commute.planner import CommutePlanner
    from .areas import enrich_commute
    return enrich_commute(CommutePlanner(ctx,resolver=resolver_for(ctx)).prepare(brief,destination,allow_external=allow_external),ctx.settings.catalog)


def question_fields(brief):
    if 'budget_amount' not in brief:return ['budget_amount','budget_scope','min_bedrooms']
    if brief.get('budget_period')!='week':return ['budget_period']
    if brief.get('budget_scope') not in ('whole_property','per_room','per_person'):return ['budget_scope']
    if 'min_bedrooms' not in brief:return ['min_bedrooms']
    if not brief.get('destination_query'):return ['destination_query']
    if not brief.get('arrival_time') or 'commute_max_minutes' not in brief:
        return [k for k in ('arrival_time','commute_max_minutes') if not brief.get(k)]
    if not brief.get('commute_mode'):return ['commute_mode']
    return []


def next_question(brief):
    if 'budget_amount' not in brief:return '不熟悉区域也没关系。每周最高预算大概多少，是整套、每间还是每人的预算？需要几间卧室？'
    if brief.get('budget_period')!='week':return '这笔预算是每周还是每月？房源按周报价，请确认每周最高金额。'
    if brief.get('budget_scope') not in ('whole_property','per_room','per_person'):return '这个每周预算是整套、每个房间，还是每人承担的金额？'
    if 'min_bedrooms' not in brief:return '至少需要几间卧室？浴室和车位有要求的话也可以一起告诉我。'
    if not brief.get('destination_query'):return '你主要去哪个学校或公司？请告诉我校区、办公楼或街道地址，我会先核对具体位置。'+(' 生活上更看重公园、餐饮购物、图书馆还是安静？也可以一起告诉我。' if 'lifestyle_priorities' not in brief else '')
    if not brief.get('arrival_time') or 'commute_max_minutes' not in brief:
        prefix='已记下目的地关键词：'+brief['destination_query']+'，具体位置稍后核对。'
        if brief.get('arrival_time'):return prefix+' 单程最多能接受多少分钟？'
        if 'commute_max_minutes' in brief:return prefix+' 通常几点需要到达学校或公司？'
        return prefix+' 通常几点需要到达学校或公司？单程最多能接受多少分钟？'
    if not brief.get('commute_mode'):return '通勤主要乘公共交通、步行、开车还是骑车？当前自动路线查询支持公共交通。'
    return None


def prepare(ctx,conversation,brief,patch,text,allow_external):
    brief['recommend_areas']=True
    options=deepcopy(conversation.get('commute_destination_options',[]))
    if 'destination_id' in patch:
        identifier=patch['destination_id']
        require(identifier in text and any(o['id']==identifier for o in options),422,'invalid_destination','请使用当前对话提供的地点选项确认目的地。')
        # A chosen server option is authoritative even if the model repeats its
        # display label as a different query. It must not invalidate itself.
        brief['destination_query']=conversation.get('rental_brief',{}).get('destination_query',brief.get('destination_query'))
    elif patch.get('destination_query') and patch['destination_query']!=conversation.get('rental_brief',{}).get('destination_query'):
        options=[];brief.pop('destination_id',None)
    answer={'intent':'recommend_areas','agent':'agent1','content':'','listings':[],'actions':[]}
    question=next_question(brief)
    if question:
        answer['content']=question
        answer['commute_question']={'fields':question_fields(brief)}
        return answer,options
    if not allow_external:
        answer['content']='需求已记下。查询学校或公司位置及公共交通路线，需要勾选本次外部位置与交通查询同意后再发送；此时不会查询或猜测通勤时长。'
        return answer,options
    destination=next((o for o in options if o['id']==brief.get('destination_id')),None)
    if destination is None:
        if not options:
            try:options=resolver_for(ctx).search(normalized_query(brief['destination_query']),limit=5)
            except ApiError:
                answer['content']='暂时无法查询目的地位置。已保留你的需求，请稍后重试，或提供更具体的校区、办公楼或街道地址。'
                return answer,[]
        if not options:
            answer['content']='还没有找到可核对的目的地位置。请补充英文校区名、办公楼名或完整街道地址；我不会把区域中心点当成你的目的地。'
        else:
            answer['content']='请确认具体的通勤目的地。相近名称可能对应不同校区或建筑；选择下方地点后发送确认，我再计算路线。'
            answer['destination_options']=options
        return answer,options
    answer=plan_routes(ctx,deepcopy(brief),deepcopy(destination),allow_external)
    answer.setdefault('intent','recommend_areas')
    return answer,options


def brief_context(conversation):
    return {'destination_options':[{'id':o['id'],'label':o['label']} for o in conversation.get('commute_destination_options',[])],
            'public_transport_available':'requires_server_lookup','supported_mode':'public_transport'}


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
    try:
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(saved['created_at'].replace('Z','+00:00'))).total_seconds()
        if age>1800:reasons.append('路线查询已超过30分钟，请重新查询。')
    except (ValueError,TypeError):reasons.append('查询时间待重新核对。')
    result.update(stale=bool(reasons),stale_reasons=reasons)
    return result
