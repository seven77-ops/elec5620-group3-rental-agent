"""Whole-inventory road estimates and transit shortlist from stored per-house routes."""
from collections import defaultdict
from copy import deepcopy
import math
from .snapshot import observation
from .usyd import DESTINATION,MODE_LABELS


def shortlist(rows,brief,limit=12):
    mode=brief.get('commute_mode','public_transport')
    def rank(row):
        route=observation(row,mode)
        record=row.get('usyd_commute') or {}
        # Measured route first, then actual coordinate distance. Price never admits
        # a distant suburb before a known nearby home just because it is cheaper.
        return (0 if route else 1,route['duration_minutes'] if route else record.get('straight_line_distance_m') or math.inf,
                row['weekly_rent'],row['listing_id'])
    return sorted(rows,key=rank)[:limit]


def road_answer(catalog,brief,destination):
    return reference_answer(catalog,brief,destination)


def reference_answer(catalog,brief,destination):
    """Use stored route facts for discovery without creating a user arrival deadline."""
    from .planner import directions_url
    from .matching import reference_matches
    from .estimates import estimate_for
    from ..real_data.providers import TFNSW_DOC
    from ..common import require
    require(catalog is not None,503,'real_catalog_unavailable','真实房源库未加载。')
    filters={k:brief[k] for k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces') if brief.get(k) is not None}
    if brief.get('budget_period')=='week' and brief.get('budget_scope')=='whole_property':filters['max_weekly_rent']=brief['budget_amount']
    rows=catalog.matching(filters);mode=brief.get('commute_mode','public_transport');maximum=brief['commute_max_minutes']
    transit=mode in ('public_transport','train','metro','bus')
    basis='scheduled_reference' if transit else 'routing_estimate'
    constraints={'usyd_mode':mode,'usyd_max_minutes':maximum,
                 **{'usyd_'+k:brief[k] for k in ('travel_day','travel_date','max_transfers') if k in brief}}
    source_label='已有班次通勤参考' if transit else '路网估算'
    routes=[];eligible=[];pending=[]
    for row in rows:
        item=observation(row,mode);record=row.get('usyd_commute') or {}
        estimate=estimate_for(row,mode) if not item else None
        # A range only passes a maximum when its UPPER bound passes it.
        minutes=item['duration_minutes'] if item else estimate['upper_minutes'] if estimate else None
        ok=minutes is not None and reference_matches(row,constraints)
        sources=estimate.get('source_urls',[]) if estimate else []
        route={'listing_id':row['listing_id'],'status':'ok' if ok else 'over_limit' if minutes is not None and minutes>maximum else 'unavailable',
               'duration_minutes':minutes,'walking_minutes':item.get('walking_minutes') if transit and item else minutes if mode=='walk' else None,
               'transfers':item.get('transfers') if transit and item else None if transit else 0,
               'departure_at':None,'arrival_at':None,'source_url':item['source_url'] if item else sources[0] if sources else TFNSW_DOC if transit else 'https://routing.openstreetmap.de/about.html',
               'route_url':directions_url(row,destination,mode),'origin_precision':(record.get('origin') or {}).get('precision','unknown'),
               'reason':('已有班次通勤参考；未按个人到校时间查询。' if transit else '路网规划估算；'+('不含实时拥堵、停车和下车后步行。' if mode=='drive' else '不含楼内及到具体教室的时间。')) if ok else '已有路线超过通勤上限。' if minutes is not None and minutes>maximum else '这套房源尚无满足当前条件的通勤参考，未列为符合条件。',
               'basis':'coarse_estimate' if estimate else basis,'mode':mode,'transit_modes':item.get('transit_modes',[]) if transit and item else [],
               'reference_arrival_at':(item or estimate or {}).get('reference_arrival_at'),
               'distance_m':item.get('distance_m') if item else None}
        routes.append(route)
        if estimate and ok:route['reason']='按街道、区域或邮区的路线范围筛选；以区间上限核对通勤条件。'
        card={**row,'commute_minutes':minutes,'commute_status':route['status']}
        (eligible if ok else pending).append(card)
    rent_floor=max(min((r['weekly_rent'] for r in eligible),default=1),1)
    time_floor=max(min((r['commute_minutes'] for r in eligible),default=1),1)
    def rank(r):
        if brief.get('commute_priority')=='rent':return (r['weekly_rent'],r['commute_minutes'],r['listing_id'])
        if brief.get('commute_priority')=='commute':return (r['commute_minutes'],r['weekly_rent'],r['listing_id'])
        return ((r['weekly_rent']/rent_floor+r['commute_minutes']/time_floor)/2,r['weekly_rent'],r['listing_id'])
    eligible.sort(key=rank)
    grouped=defaultdict(list)
    for row in eligible:grouped[row['suburb']].append(row)
    areas=[{'suburb':suburb,'count':len(group),'min_weekly_rent':min(r['weekly_rent'] for r in group),
            'max_weekly_rent':max(r['weekly_rent'] for r in group),'fastest_minutes':min(r['commute_minutes'] for r in group),
            'verified_route_count':len(group),'reasons':[f"{len(group)}套有{MODE_LABELS[mode]}{source_label}，且不超过{maximum}分钟。"],
            'tradeoffs':[source_label+'不保证当天实际耗时；请按具体课程位置复核。']} for suburb,group in grouped.items()]
    areas.sort(key=lambda a:(a['fastest_minutes'],a['min_weekly_rent']))
    known=sum(r['duration_minutes'] is not None for r in routes)
    snapshot=getattr(catalog,'commutes',None) or {}
    report={'status':'ready' if known==len(rows) and rows else 'partial' if known else 'unavailable',
            'destination':deepcopy(destination),'criteria':deepcopy(brief),'queried_at':snapshot.get('generated_at',''),
            'date':snapshot.get('generated_at','')[:10],'arrival_time':'','total_matching':len(rows),
            'evaluated_count':len(rows),'query_limit':len(rows),'areas':areas,'routes':routes,
            'pending_listings':pending[:12],'matching_count':len(eligible),'basis':basis,
            'limitations':[DESTINATION['reference_note'],
                '公共交通使用已有班次通勤参考；未按个人到校时间核对当天班次。' if transit else '开车、骑行、步行均使用各自路网；估算不含实时交通。',
                f'已检查全部{len(rows)}套符合房型和预算的房源标注，返回全部{len(eligible)}套符合通勤上限的房源。']}
    from .estimates import attach_estimates
    return attach_estimates({'intent':'recommend_areas','agent':'agent2','content':f"按你的预算和房型，找到{len(eligible)}套{MODE_LABELS[mode]}到悉大主校区约{maximum}分钟内的房源。"+
            ('可以提高预算、调整房型或明确放宽通勤上限。' if not eligible else ''),
            'listings':eligible,'actions':[],'commute_recommendation':report},rows,brief)
