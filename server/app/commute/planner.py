"""Bounded inventory comparison using actual TfNSW elapsed journey durations.

This service only returns a preview. It never writes case/profile/selection state.
The caller must invoke it outside its database transaction.
"""
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
import math
import re
from threading import Lock
from time import monotonic
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from ..common import ApiError, now, require
from ..real_data.providers import TFNSW_DOC
from .locations import LocationResolver, valid_point

SYDNEY=ZoneInfo('Australia/Sydney')
QUERY_LIMIT=12


def number(value,low=0,high=1000000000000):
    return type(value) in (int,float) and math.isfinite(value) and low<=value<=high


def timing_matches(journey,requested):
    """Only aware, elapsed-consistent journeys arriving by the selected local time."""
    try:
        departure=datetime.fromisoformat(journey['departure_at'].replace('Z','+00:00'))
        arrival=datetime.fromisoformat(journey['arrival_at'].replace('Z','+00:00'))
        if departure.utcoffset() is None or arrival.utcoffset() is None: return False
        elapsed=(arrival.astimezone(timezone.utc)-departure.astimezone(timezone.utc)).total_seconds()/60
        return (0<=elapsed<=10080 and abs(elapsed-journey['duration_minutes'])<=0.011
                and arrival.astimezone(SYDNEY).date()==requested.date() and arrival<=requested)
    except (KeyError,ValueError,TypeError,AttributeError,OverflowError):
        return False


def directions_url(row,destination):
    """An ordinary outbound URL: constructing it makes no Google API request."""
    return 'https://www.google.com/maps/dir/?'+urlencode({'api':'1',
        'origin':f"{row['address']} NSW {row.get('postcode','')}".strip(),
        'destination':f"{destination['latitude']},{destination['longitude']}", 'travelmode':'transit'})


def arrival_for(brief):
    clock=brief.get('arrival_time')
    require(isinstance(clock,str) and re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',clock),
            422,'invalid_commute_time','请提供有效的到达时间 HH:mm。')
    day=brief.get('travel_day','weekday')
    require(day in ('weekday','weekend'),422,'invalid_commute_day','请选择工作日或周末。')
    current=datetime.now(SYDNEY)
    try:
        chosen=date.fromisoformat(brief['travel_date']) if brief.get('travel_date') else current.date()
        arrival=datetime.combine(chosen,time.fromisoformat(clock),SYDNEY)
    except (ValueError,TypeError):
        raise ApiError(422,'invalid_commute_date','出行日期须为 YYYY-MM-DD。') from None
    matches=lambda dt: (dt.weekday()<5)==(day=='weekday')
    if brief.get('travel_date'):
        require(matches(arrival),422,'commute_day_mismatch','所选日期与工作日／周末条件不一致。')
    else:
        while arrival<=current or not matches(arrival): arrival+=timedelta(days=1)
    require(current<arrival<=current+timedelta(days=30),422,'invalid_commute_date','请选择未来30天内的到达时间。')
    return arrival


def bounded_candidates(rows,destination=None,resolver=None):
    groups=defaultdict(deque)
    for row in sorted(rows,key=lambda r:(r['weekly_rent'],r['listing_id'])): groups[row['suburb']].append(row)
    # Cheapest representative from each suburb first; subsequent rounds fill remaining capacity.
    keys=sorted(groups,key=lambda s:(groups[s][0]['weekly_rent'],s))
    chosen=[]
    cached=getattr(resolver,'cached_listing',None)
    if callable(cached) and destination:
        located=[(row,cached(row)) for row in rows]
        located=[(row,point) for row,point in located if valid_point(point)]
        # Coarse admission heuristic only: distance never becomes route duration.
        def distance(item):
            row,point=item
            return ((point['latitude']-destination['latitude'])**2+
                ((point['longitude']-destination['longitude'])*math.cos(math.radians(destination['latitude'])))**2,
                row['weekly_rent'],row['listing_id'])
        for row,point in sorted(located,key=distance):
            if row['suburb'] in {r['suburb'] for r in chosen}: continue
            chosen.append(row)
            if len(chosen)==QUERY_LIMIT//2: break
        for row in chosen:
            groups[row['suburb']]=deque(r for r in groups[row['suburb']] if r['listing_id']!=row['listing_id'])
    while len(chosen)<QUERY_LIMIT and any(groups.values()):
        for key in keys:
            if groups[key]: chosen.append(groups[key].popleft())
            if len(chosen)==QUERY_LIMIT: break
    return chosen


class CommutePlanner:
    def __init__(self,ctx,resolver=None):
        self.ctx=ctx
        self.resolver=resolver or LocationResolver()

    def prepare(self,brief,destination,allow_external=False):
        require(isinstance(brief,dict),422,'invalid_commute_brief','通勤条件无效。')
        require(valid_point(destination) and all(isinstance(destination.get(k),str) and destination[k]
                for k in ('id','label','precision','source_url')),422,'invalid_destination','请选择服务器返回的目的地。')
        require(type(brief.get('commute_max_minutes')) is int and 1<=brief['commute_max_minutes']<=240,
                422,'invalid_commute_limit','通勤上限须为1至240分钟。')
        require(brief.get('commute_priority','balanced') in ('balanced','rent','commute'),
                422,'invalid_commute_priority','通勤排序偏好无效。')
        if 'max_transfers' in brief:
            require(type(brief['max_transfers']) is int and 0<=brief['max_transfers']<=5,
                    422,'invalid_transfers','换乘上限须为0至5次。')
        arrival=arrival_for(brief)
        catalog=self.ctx.settings.catalog
        require(catalog is not None,503,'real_catalog_unavailable','真实房源库未加载。')
        filters={k:brief[k] for k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces') if brief.get(k) is not None}
        limitations=[f'仅对当前广告库按区域轮流选出的最多{QUERY_LIMIT}条房源核对通勤，未穷尽全市。',
                      '房源地址点／目的地设施点不是已核实的单元门口或步行入口；楼内及园区内步行未核实。',
                      '广告计价对象、账单、可租状态、入住时间和安静程度尚未核实；不作每人分摊或可负担性保证。',
                      '路线按计划时刻计算，总时长包含候车和换乘；不含 Opal 票价。',
                      '如有已核验地址缓存，最多一半名额按实际坐标直线接近程度粗筛，其余按广告周租和区域轮流选取；直线距离不代表通勤时间。']
        if (brief.get('budget_period')=='week' and brief.get('budget_scope')=='whole_property'
                and number(brief.get('budget_amount'),0.01)):
            filters['max_weekly_rent']=brief['budget_amount']
        else:
            limitations.append('预算周期或计价对象无法与广告周租直接比较，未用预算筛除房源，也未按人数乘除租金。')
        rows=catalog.matching(filters)
        selected=bounded_candidates(rows,destination,self.resolver)
        report={'status':'unavailable','destination':deepcopy(destination),'criteria':deepcopy(brief),
                'queried_at':now(),'date':arrival.date().isoformat(),'arrival_time':brief['arrival_time'],
                'total_matching':len(rows),'evaluated_count':0,'query_limit':QUERY_LIMIT,
                'areas':[],'routes':[],'limitations':limitations}
        reason=None
        mode=brief.get('commute_mode','public_transport')
        if allow_external is not True: reason='本轮未同意向位置／交通服务发送查询。'
        elif mode!='public_transport': reason='当前实际路线仅支持公共交通；此出行方式尚不支持。'
        elif not self.ctx.data_provider.public_config().get('tfnsw',{}).get('configured'):
            reason='后端未配置 TFNSW_API_KEY；无法核验真实通勤时长。'
        if reason: limitations.append(reason)
        if not rows: limitations.append('当前广告库没有符合已给定房型及可直接比较周租条件的房源。')
        # Actual Repository opens its own short transactions; no database operation occurs here.
        connection=getattr(self.ctx.repo,'connection',None)
        if selected and not reason:
            require(not getattr(connection,'in_transaction',False),409,'commute_transaction_open',
                    '请在数据库事务外查询外部通勤数据。')
        deadline=monotonic()+24
        attempted=set()
        attempt_lock=Lock()
        def unavailable(row,why,status='unavailable',precision=None):
            return {'listing_id':row['listing_id'],'status':status,'duration_minutes':None,'walking_minutes':None,
                    'transfers':None,'departure_at':None,'arrival_at':None,'source_url':TFNSW_DOC,
                    'route_url':directions_url(row,destination),'origin_precision':precision or 'unknown','reason':why}
        def evaluate(row):
            if reason: return unavailable(row,reason,'unsupported' if mode!='public_transport' else 'unavailable')
            if monotonic()>=deadline: return unavailable(row,'本轮查询时间预算已用尽，未查询此房源。')
            with attempt_lock: attempted.add(row['listing_id'])
            try:
                origin=self.resolver.listing(row)
                if not origin: return unavailable(row,'未找到唯一匹配的官方完整地址点，未使用区域中心坐标。')
                if monotonic()>=deadline: return unavailable(row,'本轮查询时间预算已用尽，未查询路线。',precision=origin['precision'])
                response=self.ctx.data_provider.trips({'origin':{k:origin[k] for k in ('latitude','longitude')},
                    'destination':{k:destination[k] for k in ('latitude','longitude')},
                    'arrival_at':arrival.isoformat(),'allow_external':True})
                journeys=response.get('journeys',[])
                usable=[]
                for journey in journeys:
                    if not number(journey.get('duration_minutes'),0,10080): continue
                    if brief.get('max_transfers') is not None and (type(journey.get('transfers')) is not int
                            or journey['transfers']>brief['max_transfers']): continue
                    # The provider validates elapsed timing; the planner additionally
                    # enforces this user's actual Sydney arrival date and deadline.
                    if not timing_matches(journey,arrival): continue
                    usable.append(journey)
                if not usable:
                    return unavailable(row,'供应商没有返回时刻与总时长可核验、在所选日期按时到达且满足换乘限制的路线。',precision=origin['precision'])
                chosen=min(usable,key=lambda r:r['duration_minutes'])
                over=chosen['duration_minutes']>brief['commute_max_minutes']
                return {'listing_id':row['listing_id'],'status':'over_limit' if over else 'ok',
                        **{k:chosen.get(k) for k in ('duration_minutes','walking_minutes','transfers','departure_at','arrival_at')},
                        'source_url':TFNSW_DOC,'route_url':directions_url(row,destination),'origin_precision':origin['precision'],
                        'reason':'已核验的计划通勤超过给定上限。' if over else '已核验公共交通计划时刻，含候车与换乘。'}
            except ApiError as error:
                return unavailable(row,'位置／交通查询失败：'+error.message)
        if reason:
            routes=[evaluate(row) for row in selected]
        else:
            # Three workers, five-second location timeout and existing twelve-second TfNSW timeout.
            # No new task starts external I/O after 24s: last in-flight request ends by ~36s.
            with ThreadPoolExecutor(max_workers=3) as pool: routes=list(pool.map(evaluate,selected))
            report['evaluated_count']=len(attempted)
        report['routes']=routes
        route_by_id={r['listing_id']:r for r in routes}
        verified=[r for r in routes if r['duration_minutes'] is not None]
        report['status']='ready' if routes and len(verified)==len(routes) else 'partial' if verified else 'unavailable'
        if len(selected)<len(rows): limitations.append(f'符合库存条件共{len(rows)}条，本轮仅选取{len(selected)}条；未评估房源不能视为满足通勤上限。')
        hard=brief.get('commute_hard_limit',False) is True
        eligible=[]
        for row in selected:
            route=route_by_id[row['listing_id']]
            if hard and route['status']!='ok': continue
            # Explicit maximum transfers is a constraint, never accepted when unknown.
            maximum=brief.get('max_transfers')
            if maximum is not None and (type(route.get('transfers')) is not int
                    or not 0<=route['transfers']<=maximum): continue
            eligible.append({**deepcopy(row),'commute_minutes':route['duration_minutes'],'commute_status':route['status']})
        eligible_ids={row['listing_id'] for row in eligible}
        # Inspection-only catalogue facts. The caller must not register these as
        # recommendation/selection authority or attach save actions to them.
        report['pending_listings']=[{**deepcopy(row),
            'commute_minutes':route_by_id[row['listing_id']]['duration_minutes'],
            'commute_status':route_by_id[row['listing_id']]['status']}
            for row in selected if row['listing_id'] not in eligible_ids]
        priority=brief.get('commute_priority','balanced')
        from ..areas.evidence import AreaKnowledge
        knowledge=AreaKnowledge()
        topic_matches={suburb:len({t for e in knowledge.evidence(suburb,brief.get('lifestyle_priorities',[]),datetime.now(SYDNEY).date())
                                  for t in e['supports_topics']}) for suburb in {r['suburb'] for r in eligible}}
        def rank(row):
            minutes=route_by_id[row['listing_id']]['duration_minutes']
            lifestyle=-topic_matches[row['suburb']]
            if priority=='rent': return (row['weekly_rent'],minutes if minutes is not None else math.inf,lifestyle,row['listing_id'])
            if priority=='commute': return (minutes if minutes is not None else math.inf,row['weekly_rent'],lifestyle,row['listing_id'])
            # Explicit equal weighting of relative rent and relative verified elapsed time.
            known=[r['duration_minutes'] for r in verified]
            rent_floor=min(r['weekly_rent'] for r in selected) if selected else 1
            time_floor=max(min(known),1) if known else 1
            score=(row['weekly_rent']/max(rent_floor,1)+(minutes/time_floor if minutes is not None else math.inf))/2
            return (score,row['weekly_rent'],lifestyle,row['listing_id'])
        eligible.sort(key=rank)
        groups=defaultdict(list)
        for row in rows: groups[row['suburb']].append(row)
        eligible_suburbs={row['suburb']:i for i,row in reversed(list(enumerate(eligible)))}
        for suburb,group in groups.items():
            facts=[route_by_id[r['listing_id']] for r in group if r['listing_id'] in route_by_id]
            known=[r for r in facts if r['duration_minutes'] is not None]
            ok=[r for r in facts if r['status']=='ok']
            report['areas'].append({'suburb':suburb,'count':len(group),
                'min_weekly_rent':min(r['weekly_rent'] for r in group),'max_weekly_rent':max(r['weekly_rent'] for r in group),
                'fastest_minutes':min((r['duration_minutes'] for r in known),default=None),'verified_route_count':len(known),
                'reasons':[f'当前广告库有{len(group)}条符合库存筛选条件。',f'本轮{len(ok)}条路线已核验且不超过通勤上限。'],
                'tradeoffs':[('仅房型／广告周租候选；本轮尚无满足通勤上限的已核验房源。' if not ok else f'本区{len(ok)}条已核验路线满足通勤上限。'),
                             f'本区已核验{len(known)}条路线；其余通勤未确认。',
                             '广告周租的计价对象与可租状态仍需确认。']})
        report['areas'].sort(key=lambda area:(eligible_suburbs.get(area['suburb'],math.inf),area['min_weekly_rent'],area['suburb']))
        if len(report['areas'])>5: limitations.append('区域卡片仅展示前5个区域，完整匹配数量见库存统计。')
        report['areas']=report['areas'][:5]
        content=(f"当前广告库匹配{len(rows)}条房源，本轮选择{len(selected)}条，核验到{len(verified)}条路线。"
                 + (' 硬性通勤上限下，未知或超时路线未列为满足条件的房源。' if hard else '')
                 + (' '+reason if reason else '')
                 + ' 这是条件预览，尚未更新正式需求或房源选择。')
        return {'intent':'recommend_areas','agent':'agent2','content':content,'listings':eligible,'actions':[],
                'commute_recommendation':report}
