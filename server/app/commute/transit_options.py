"""Bounded actual journeys, distinct paths and per-request transit selection.

Category slots are observations of journeys that include a mode, not separate
services to average. Estimates never enter this module's candidate pool.
"""
from copy import deepcopy
from datetime import datetime,timezone
import json
import math

TRANSIT=('public_transport','train','metro','bus')
LEG_MODES={'unknown','walk','train','metro','bus','light_rail','ferry'}
LIMIT=6
SOURCE='https://opendata.transport.nsw.gov.au/'
PATH_FIELDS=('duration_minutes','walking_minutes','transfers','departure_at','arrival_at','transit_modes','services','legs')


def stamp(value):
    if not isinstance(value,str):raise ValueError('Missing timestamp')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.utcoffset() is None:raise ValueError('Timezone required')
    return result.astimezone(timezone.utc)


def number(value,high=10080):
    return type(value) in (int,float) and math.isfinite(value) and 0<=value<=high


def valid_option(route,*,fresh=True,legacy=False):
    try:
        if not isinstance(route,dict) or route.get('status')!='planned' or not number(route.get('duration_minutes')):return False
        if not isinstance(route.get('source_url'),str) or not route['source_url'].startswith(SOURCE):return False
        checked=stamp(route['queried_at'])
        if fresh and not 0<=(datetime.now(timezone.utc)-checked).total_seconds()<=7*86400:return False
        for key in ('walking_minutes','leg_travel_minutes'):
            if route.get(key) is not None and (not number(route[key]) or route[key]>route['duration_minutes']+0.05):return False
        transfers=route.get('transfers')
        if transfers is not None and (type(transfers) is not int or not 0<=transfers<=50):return False
        modes=route.get('transit_modes',[])
        if not isinstance(modes,list) or len(modes)>5 or len(set(modes))!=len(modes) or any(m not in LEG_MODES-{'walk','unknown'} for m in modes):return False
        services=route.get('services',[])
        if not isinstance(services,list) or len(services)>100 or any(not isinstance(s,str) or len(s)>180 for s in services):return False
        departure,arrival=route.get('departure_at'),route.get('arrival_at')
        if departure is not None or arrival is not None:
            begin,end=stamp(departure),stamp(arrival)
            if abs((end-begin).total_seconds()/60-route['duration_minutes'])>0.011:return False
        elif not legacy:return False
        reference=route.get('reference_arrival_at')
        if reference is not None:
            target=stamp(reference)
            if arrival and not 0<=(target-end).total_seconds()<=3600:return False
        elif not legacy:return False
        legs=route.get('legs')
        if legs is not None:
            if not isinstance(legs,list) or not 1<=len(legs)<=100:return False
            total=0;previous=begin if departure else None
            for leg in legs:
                if not isinstance(leg,dict) or leg.get('mode') not in LEG_MODES or not number(leg.get('duration_minutes')):return False
                total+=leg['duration_minutes']
                if leg['mode'] not in ('walk','unknown') and leg['mode'] not in modes:return False
                for key in ('service','from','to','from_stop_id','to_stop_id','platform'):
                    if leg.get(key) is not None and (not isinstance(leg[key],str) or len(leg[key])>300):return False
                first,last=leg.get('departure_at'),leg.get('arrival_at')
                if first is not None or last is not None:
                    if first is None or last is None:
                        # Some walking legs have only one endpoint timestamp.
                        point=stamp(first or last)
                        if departure and not begin<=point<=end:return False
                    else:
                        start,finish=stamp(first),stamp(last)
                        if start>finish or abs((finish-start).total_seconds()/60-leg['duration_minutes'])>0.011:return False
                        if previous and start<previous:return False
                        if arrival and finish>end:return False
                        previous=finish
            if total>route['duration_minutes']+max(0.05,len(legs)*0.011):return False
        return True
    except (KeyError,ValueError,TypeError,AttributeError,OverflowError):return False


def path_key(route):
    value={k:route.get(k) for k in PATH_FIELDS}
    value['transit_modes']=sorted(value.get('transit_modes') or [])
    return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)


def distinct(routes,limit=LIMIT):
    seen=set();result=[]
    for route in sorted(routes,key=lambda r:(r['duration_minutes'],path_key(r))):
        key=path_key(route)
        if key in seen:continue
        seen.add(key);result.append({k:deepcopy(v) for k,v in route.items() if k not in ('transit_options','selected_transit_route')})
        if len(result)==limit:break
    return result


def options(annotation,limit=LIMIT,selected=None):
    if not isinstance(annotation,dict) or not annotation.get('origin'):return []
    pool=[]
    supplied=annotation.get('transit_options',[])
    if isinstance(supplied,list):pool.extend(r for r in supplied[:30] if valid_option(r))
    slots=annotation.get('modes',{})
    for mode in TRANSIT:
        route=slots.get(mode) if isinstance(slots,dict) else None
        if valid_option(route,legacy=True) and (mode=='public_transport' or mode in route.get('transit_modes',[])):
            pool.append(route)
    result=distinct(pool,limit)
    if selected and limit and path_key(selected) not in {path_key(r) for r in result}:
        result=distinct(result[:limit-1]+[selected],limit)
    return result


def select(annotation,mode='public_transport',max_transfers=None):
    def allowed(route):
        return (valid_option(route,legacy=True) and (mode=='public_transport' or mode in route.get('transit_modes',[]))
                and (max_transfers is None or type(route.get('transfers')) is int and 0<=route['transfers']<=max_transfers))
    selected=annotation.get('selected_transit_route')
    if isinstance(selected,dict) and selected.get('mode')==mode and allowed(selected):
        return {**deepcopy(selected),'mode':mode}
    slot=annotation.get('modes',{}).get(mode)
    personal=isinstance(slot,dict) and slot.get('basis') in ('scheduled_live_query','recent_checked_query') and valid_option(slot,legacy=True)
    if personal and allowed(slot):return {**deepcopy(slot),'mode':mode}
    usable=[r for r in options(annotation,limit=None) if allowed(r)]
    if personal:
        usable=[r for r in usable if r.get('reference_arrival_at')==slot.get('reference_arrival_at')
                and r.get('basis') in ('scheduled_live_query','recent_checked_query')]
    return {**deepcopy(usable[0]),'mode':mode} if usable else None


def planned_journeys(journeys,reference_arrival_at,queried_at,limit=LIMIT):
    """Retain provider journeys verbatim apart from provenance; never create legs."""
    candidates=[]
    for journey in journeys[:30] if isinstance(journeys,list) else []:
        if not isinstance(journey,dict):continue
        item={**deepcopy(journey),'status':'planned','source_url':SOURCE+'dataset/trip-planner-apis',
              'queried_at':queried_at,'reference_arrival_at':reference_arrival_at}
        if valid_option(item):candidates.append(item)
    return distinct(candidates,limit)
