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
                and arrival.astimezone(SYDNEY).date()==requested.date() and 0<=(requested-arrival).total_seconds()<=3600)
    except (KeyError,ValueError,TypeError,AttributeError,OverflowError):
        return False


def directions_url(row,destination,mode="public_transport"):
    """An ordinary outbound URL: constructing it makes no Google API request."""
    return 'https://www.google.com/maps/dir/?'+urlencode({'api':'1',
        'origin':f"{row['address']} NSW {row.get('postcode','')}".strip(),
        'destination':f"{destination['latitude']},{destination['longitude']}", 'travelmode':{'drive':'driving','bike':'bicycling','walk':'walking'}.get(mode,'transit')})


def arrival_for(brief):
    clock=brief.get('arrival_time')
    require(isinstance(clock,str) and re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',clock),
            422,'invalid_commute_time','Provide a valid arrival time in HH:mm format.')
    day=brief.get('travel_day','weekday')
    require(day in ('weekday','weekend'),422,'invalid_commute_day','Choose weekdays or weekends.')
    current=datetime.now(SYDNEY)
    try:
        chosen=date.fromisoformat(brief['travel_date']) if brief.get('travel_date') else current.date()
        arrival=datetime.combine(chosen,time.fromisoformat(clock),SYDNEY)
    except (ValueError,TypeError):
        raise ApiError(422,'invalid_commute_date','Travel date must use YYYY-MM-DD.') from None
    matches=lambda dt: (dt.weekday()<5)==(day=='weekday')
    if brief.get('travel_date'):
        require(matches(arrival),422,'commute_day_mismatch','The selected date does not match the weekday or weekend condition.')
    else:
        while arrival<=current or not matches(arrival): arrival+=timedelta(days=1)
    require(current<arrival<=current+timedelta(days=30),422,'invalid_commute_date','Choose an arrival time within the next 30 days.')
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

    def prepare(self,brief,destination,allow_external=False,previous_reports=None,listing_ids=None):
        require(isinstance(brief,dict),422,'invalid_commute_brief','Invalid commute requirements.')
        require(valid_point(destination) and all(isinstance(destination.get(k),str) and destination[k]
                for k in ('id','label','precision','source_url')),422,'invalid_destination','Choose a destination returned by the server.')
        require(type(brief.get('commute_max_minutes')) is int and 1<=brief['commute_max_minutes']<=240,
                422,'invalid_commute_limit','The commute limit must be 1 to 240 minutes.')
        require(brief.get('commute_priority','balanced') in ('balanced','rent','commute'),
                422,'invalid_commute_priority','Invalid commute ranking preference.')
        if 'max_transfers' in brief:
            require(type(brief['max_transfers']) is int and 0<=brief['max_transfers']<=5,
                    422,'invalid_transfers','The transfer limit must be 0 to 5.')
        mode=brief.get('commute_mode','public_transport')
        if mode in ('public_transport','train','metro','bus') and 'arrival_time' not in brief:
            from .cached_plan import reference_answer
            return reference_answer(self.ctx.settings.catalog,brief,destination)
        if mode in ('drive','bike','walk') and getattr(self.ctx.settings.catalog,'commutes',None):
            from .cached_plan import road_answer
            return road_answer(self.ctx.settings.catalog,brief,destination)
        arrival=arrival_for(brief)
        catalog=self.ctx.settings.catalog
        require(catalog is not None,503,'real_catalog_unavailable','The live listing catalogue is unavailable.')
        filters={k:brief[k] for k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces') if brief.get(k) is not None}
        limitations=[f'Commutes are checked for up to {QUERY_LIMIT} listings sampled across suburbs in the current catalogue, not the whole city.',
                      'Property and destination points are not verified unit doors or walking entrances. Walking inside buildings and campuses is unverified.',
                      'Advertised rent scope, bills, availability, move-in dates and quietness remain unverified. Per-person costs and affordability are not guaranteed.',
                      'Routes use scheduled times. Total duration includes waiting and transfers; Opal fares are excluded.',
                      'Where verified address caches exist, up to half the sample uses straight-line coordinate proximity; the rest uses advertised weekly rent and suburb rotation. Straight-line distance does not establish commute time.']
        if (brief.get('budget_period')=='week' and brief.get('budget_scope')=='whole_property'
                and number(brief.get('budget_amount'),0.01)):
            filters['max_weekly_rent']=brief['budget_amount']
        else:
            limitations.append('The budget period or scope is not directly comparable to advertised weekly rent. Budget filtering and occupant-based rent conversion were not applied.')
        rows=catalog.matching(filters)
        if listing_ids is not None:
            rows=[row for row in rows if row['listing_id'] in listing_ids]
        from .history import recent_routes
        reused=recent_routes(previous_reports,brief,destination,arrival,{r['listing_id'] for r in rows},catalog.fingerprint)
        remaining=[r for r in rows if r['listing_id'] not in reused]
        if getattr(catalog,'commutes',None):
            from .cached_plan import shortlist
            selected=shortlist(remaining,brief,QUERY_LIMIT)
        else:
            selected=bounded_candidates(remaining,destination,self.resolver)
        report={'status':'unavailable','destination':deepcopy(destination),'criteria':deepcopy(brief),'catalog_fingerprint':catalog.fingerprint,
                'queried_at':now(),'date':arrival.date().isoformat(),'arrival_time':brief['arrival_time'],
                'total_matching':len(rows),'evaluated_count':0,'query_limit':QUERY_LIMIT,
                'areas':[],'routes':[],'limitations':limitations}
        reason=None
        mode=brief.get('commute_mode','public_transport')
        if allow_external is not True: reason='No consent was given for location or transit queries in this run.'
        elif mode not in ('public_transport','train','metro','bus'): reason='Actual route lookup currently supports public transport only. This mode is unsupported.'
        elif not self.ctx.data_provider.public_config().get('tfnsw',{}).get('configured'):
            reason='The backend transit connection is not configured, so actual commute durations cannot be verified.'
        if reason: limitations.append(reason)
        if not rows: limitations.append('The current catalogue has no listings matching the supplied property and directly comparable weekly rent requirements.')
        # Actual Repository opens its own short transactions; no database operation occurs here.
        connection=getattr(self.ctx.repo,'connection',None)
        if selected and not reason:
            require(not getattr(connection,'in_transaction',False),409,'commute_transaction_open',
                    'External commute data must be queried outside the database transaction.')
        deadline=monotonic()+24
        attempted=set()
        attempt_lock=Lock()
        def unavailable(row,why,status='unavailable',precision=None):
            return {'listing_id':row['listing_id'],'status':status,'duration_minutes':None,'walking_minutes':None,
                    'transfers':None,'departure_at':None,'arrival_at':None,'source_url':TFNSW_DOC,
                    'route_url':directions_url(row,destination),'origin_precision':precision or 'unknown','reason':why}
        def evaluate(row):
            if reason: return unavailable(row,reason,'unsupported' if mode not in ('public_transport','train','metro','bus') else 'unavailable')
            if monotonic()>=deadline: return unavailable(row,'The query time budget was exhausted before checking this listing.')
            with attempt_lock: attempted.add(row['listing_id'])
            try:
                origin=(row.get('usyd_commute') or {}).get('origin') or self.resolver.listing(row)
                if not origin: return unavailable(row,'No unique official full-address point was found. Suburb-centre coordinates were not substituted.')
                if monotonic()>=deadline: return unavailable(row,'The query time budget was exhausted before checking the route.',precision=origin['precision'])
                response=getattr(self.ctx,'transit_provider',self.ctx.data_provider).trips({'origin':{k:origin[k] for k in ('latitude','longitude')},
                    'destination':{k:destination[k] for k in ('latitude','longitude')},
                    'arrival_at':arrival.isoformat(),'allow_external':True})
                journeys=response.get('journeys',[])
                usable=[]
                for journey in journeys:
                    if not number(journey.get('duration_minutes'),0,10080): continue
                    if mode in ('train','metro','bus') and mode not in journey.get('transit_modes',[]): continue
                    if brief.get('max_transfers') is not None and (type(journey.get('transfers')) is not int
                            or journey['transfers']>brief['max_transfers']): continue
                    # The provider validates elapsed timing; the planner additionally
                    # enforces this user's actual Sydney arrival date and deadline.
                    if not timing_matches(journey,arrival): continue
                    usable.append(journey)
                if not usable:
                    return unavailable(row,'The provider returned no route with verifiable times and duration that arrives on time on the selected date and meets transfer limits.',precision=origin['precision'])
                chosen=min(usable,key=lambda r:r['duration_minutes'])
                over=chosen['duration_minutes']>brief['commute_max_minutes']
                return {'listing_id':row['listing_id'],'status':'over_limit' if over else 'ok',
                        **{k:chosen.get(k) for k in ('duration_minutes','walking_minutes','transfers','departure_at','arrival_at','transit_modes','services','legs')},
                        'source_url':TFNSW_DOC,'route_url':directions_url(row,destination),'origin_precision':origin['precision'],
                        'mode':mode,'basis':'scheduled_live_query',
                        'transport_backend':response.get('transport_backend','tfnsw_direct'),
                        'fallback_used':response.get('fallback_used',False),
                        'origin':{**deepcopy(origin),'original_address':row['address'],'original_suburb':row['suburb']},
                        'reason':'The verified scheduled commute exceeds the specified limit.' if over else 'Verified public transport timetable, including waiting and transfers.'}
            except ApiError as error:
                return unavailable(row,'Location or transit query failed: '+error.message)
        if reason:
            routes=[evaluate(row) for row in selected]
        else:
            # Three workers, five-second location timeout and existing twelve-second TfNSW timeout.
            # No new task starts external I/O after 24s: last in-flight request ends by ~36s.
            with ThreadPoolExecutor(max_workers=3) as pool: routes=list(pool.map(evaluate,selected))
            report['evaluated_count']=len(attempted)
        routes=list(reused.values())+[{**route,'queried_at':now()} for route in routes]
        evaluated_ids={route['listing_id'] for route in routes}
        selected=[r for r in rows if r['listing_id'] in evaluated_ids]
        report['routes']=routes
        route_by_id={r['listing_id']:r for r in routes}
        verified=[r for r in routes if r['duration_minutes'] is not None]
        report['status']='ready' if routes and len(verified)==len(routes) else 'partial' if verified else 'unavailable'
        if len(selected)<len(rows): limitations.append(f'{len(rows)} listings match inventory requirements; {len(selected)} were sampled this run. Unchecked listings cannot be treated as meeting the commute limit.')
        hard=True
        report['criteria']['commute_hard_limit']=True
        eligible=[]
        for row in selected:
            route=route_by_id[row['listing_id']]
            if hard and route['status']!='ok': continue
            # Explicit maximum transfers is a constraint, never accepted when unknown.
            maximum=brief.get('max_transfers')
            if maximum is not None and (type(route.get('transfers')) is not int
                    or not 0<=route['transfers']<=maximum): continue
            card={**deepcopy(row),'commute_minutes':route['duration_minutes'],'commute_status':route['status']}
            if route.get('origin') and card.get('usyd_commute'):
                from .snapshot import distance_metres
                annotation=card['usyd_commute'];annotation['origin']=deepcopy(route['origin'])
                annotation['straight_line_distance_m']=distance_metres(route['origin'])
                annotation.pop('estimates',None)
                annotation['modes'][mode]={**deepcopy(route),'status':'planned',
                    'queried_at':route['queried_at'],'reference_arrival_at':arrival.isoformat()}
                annotation['reference_arrival_at']=arrival.isoformat()
            eligible.append(card)
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
        for row in eligible: groups[row['suburb']].append(row)
        eligible_suburbs={row['suburb']:i for i,row in reversed(list(enumerate(eligible)))}
        for suburb,group in groups.items():
            if suburb not in eligible_suburbs: continue
            facts=[route_by_id[r['listing_id']] for r in group if r['listing_id'] in route_by_id]
            known=[r for r in facts if r['duration_minutes'] is not None]
            ok=[r for r in facts if r['status']=='ok']
            report['areas'].append({'suburb':suburb,'count':len(group),
                'min_weekly_rent':min(r['weekly_rent'] for r in group),'max_weekly_rent':max(r['weekly_rent'] for r in group),
                'fastest_minutes':min((r['duration_minutes'] for r in known),default=None),'verified_route_count':len(known),
                'reasons':[f'{len(group)} listings match inventory filters in the current catalogue.',f'{len(ok)} routes verified in this run meet the commute limit.'],
                'tradeoffs':[('Property and advertised-rent candidates only; no verified listing in this run meets the commute limit.' if not ok else f'{len(ok)} verified routes in this area meet the commute limit.'),
                             f'{len(known)} routes in this area are verified; other commutes remain unconfirmed.',
                             'Advertised weekly rent scope and availability still require confirmation.']})
        report['areas'].sort(key=lambda area:(eligible_suburbs.get(area['suburb'],math.inf),area['min_weekly_rent'],area['suburb']))
        report['matching_count']=len(eligible)
        from .usyd import MODE_LABELS
        content=(f"Found {len(eligible)} listings meeting your budget and property requirements with {MODE_LABELS.get(mode,'public transport')} travel to the USYD main campus within {brief['commute_max_minutes']} minutes."
                 if eligible else 'These commute routes cannot currently be queried. Open a map from listing details.' if reason
                 else f"No listings were found within {brief['commute_max_minutes']} minutes. Adjust budget, property requirements or commute time.")
        from .estimates import attach_estimates
        return attach_estimates({'intent':'recommend_areas','agent':'agent2','content':content,'listings':eligible,'actions':[],
                'commute_recommendation':report},rows,brief)
