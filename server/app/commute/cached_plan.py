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
    from .usyd import student_brief
    brief=student_brief(brief)
    from .matching import reference_matches
    from .estimates import estimate_for
    from ..real_data.providers import TFNSW_DOC
    from ..common import require
    require(catalog is not None,503,'real_catalog_unavailable','The live listing catalogue is unavailable.')
    filters={k:brief[k] for k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces') if brief.get(k) is not None}
    if brief.get('budget_period')=='week' and brief.get('budget_scope')=='whole_property':filters['max_weekly_rent']=brief['budget_amount']
    rows=catalog.matching(filters);mode=brief.get('commute_mode','public_transport');maximum=brief['commute_max_minutes']
    transit=mode in ('public_transport','train','metro','bus')
    basis='scheduled_reference' if transit else 'routing_estimate'
    constraints={'usyd_mode':mode,'usyd_max_minutes':maximum,
                 **{'usyd_'+k:brief[k] for k in ('travel_day','travel_date','max_transfers') if k in brief}}
    source_label='Existing scheduled transit reference' if transit else 'Road-network estimate'
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
               'reason':('Existing scheduled transit reference; not queried for a personal arrival time.' if transit else 'Road-network estimate; '+('excludes live congestion, parking and walking after alighting.' if mode=='drive' else 'excludes indoor walking and travel to a specific classroom.')) if ok else 'The existing route exceeds the commute limit.' if minutes is not None and minutes>maximum else 'This listing has no commute reference meeting current requirements and is not counted as a match.',
               'basis':'coarse_estimate' if estimate else basis,'mode':mode,'transit_modes':item.get('transit_modes',[]) if transit and item else [],
               'reference_arrival_at':(item or estimate or {}).get('reference_arrival_at'),
               'distance_m':item.get('distance_m') if item else None}
        routes.append(route)
        if estimate and ok:route['reason']='Filtered using street, suburb or postcode route ranges. The upper estimate is checked against commute requirements.'
        card={**row,'commute_minutes':minutes,'commute_status':route['status'],'recommendation_mode':mode}
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
            'verified_route_count':len(group),'reasons':[f"{len(group)} listings have {MODE_LABELS[mode]} {source_label} within {maximum} minutes."],
            'tradeoffs':[source_label+' does not guarantee actual travel time. Check against your specific class location.']} for suburb,group in grouped.items()]
    areas.sort(key=lambda a:(a['fastest_minutes'],a['min_weekly_rent']))
    known=sum(r['duration_minutes'] is not None for r in routes)
    snapshot=getattr(catalog,'commutes',None) or {}
    report={'status':'ready' if known==len(rows) and rows else 'partial' if known else 'unavailable',
            'destination':deepcopy(destination),'criteria':deepcopy(brief),'queried_at':snapshot.get('generated_at',''),
            'date':snapshot.get('generated_at','')[:10],'arrival_time':'','total_matching':len(rows),
            'evaluated_count':len(rows),'query_limit':len(rows),'areas':areas,'routes':routes,
            'pending_listings':pending[:12],'matching_count':len(eligible),'basis':basis,
            'limitations':[DESTINATION['reference_note'],
                'Public transport uses existing scheduled references; services for a personal arrival time are not checked.' if transit else 'Driving, cycling and walking use their respective networks. Estimates exclude live traffic.',
                f'Checked all {len(rows)} listings matching property and budget requirements and returned all {len(eligible)} that meet the commute limit.']}
    from .estimates import attach_estimates
    from ..assistant.recommendation_options import metadata, filters_for
    return attach_estimates({'intent':'recommend_areas','agent':'agent2',**metadata(catalog,filters_for(brief),brief,len(eligible)), 'content':f"Found {len(eligible)} listings meeting budget and property requirements with {MODE_LABELS[mode]} travel to the USYD main campus within approximately {maximum} minutes."+
            ('You can increase the budget, adjust property requirements or explicitly relax the commute limit.' if not eligible else ''),
            'listings':eligible,'actions':[],'commute_recommendation':report},rows,brief)
