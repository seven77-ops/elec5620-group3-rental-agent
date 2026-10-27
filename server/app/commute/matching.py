"""Apply every saved commute condition; reuse recent checked routes without network I/O."""
from copy import deepcopy
from datetime import datetime,timezone
from .snapshot import observation
from .usyd import DESTINATION
from .planner import arrival_for,timing_matches
from ..common import ApiError

TRANSIT=('public_transport','train','metro','bus')
FILTER_KEYS=('usyd_mode','usyd_max_minutes','usyd_arrival_time','usyd_travel_day','usyd_travel_date','usyd_max_transfers')


def reference_matches(row,filters):
    mode=filters.get('usyd_mode','public_transport');route=observation(row,mode)
    if not route:
        from .estimates import estimate_matches
        return estimate_matches(row,filters)
    if route['duration_minutes']>filters['usyd_max_minutes']:return False
    if mode not in TRANSIT:return True
    maximum=filters.get('usyd_max_transfers')
    if maximum is not None and (type(route.get('transfers')) is not int or route['transfers']>maximum):return False
    try:
        from zoneinfo import ZoneInfo
        baseline=datetime.fromisoformat(route['reference_arrival_at']).astimezone(ZoneInfo('Australia/Sydney'))
        if filters.get('usyd_arrival_time') and filters['usyd_arrival_time']!=baseline.strftime('%H:%M'):return False
        if filters.get('usyd_travel_day') and (baseline.weekday()<5)!=(filters['usyd_travel_day']=='weekday'):return False
        if filters.get('usyd_travel_date') and filters['usyd_travel_date']!=baseline.date().isoformat():return False
    except (KeyError,ValueError,TypeError):return False
    return True


def matching_for_case(ctx,case_id,filters,db=None):
    catalog=ctx.settings.catalog;f=catalog.filters(filters)
    if 'usyd_max_minutes' not in f:return catalog.matching(f)
    base={k:v for k,v in f.items() if k not in FILTER_KEYS}
    rows=catalog.matching(base)
    if not case_id:return [r for r in rows if reference_matches(r,f)]
    def read(connection):
        ctx.get(connection,'case',case_id)
        return ctx.repo.get(connection,'assistant_commute_report',case_id)
    if db is None:
        with ctx.repo.transaction() as connection:saved=read(connection)
    else:saved=read(db)
    mode=f.get('usyd_mode','public_transport');fresh={};target=None
    if mode in TRANSIT and saved and saved.get('catalog_fingerprint')==catalog.fingerprint:
        report=saved.get('message',{}).get('commute_recommendation',{})
        try:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(saved['created_at'].replace('Z','+00:00'))).total_seconds()
            criteria=report['criteria']
            requested={**criteria,**{key:f[source] for source,key in (
                ('usyd_arrival_time','arrival_time'),('usyd_travel_day','travel_day'),('usyd_travel_date','travel_date')) if f.get(source)}}
            target=arrival_for(requested)
            if (0<=age<=1800 and report['destination']['id']==DESTINATION['id'] and report.get('basis')!='routing_estimate'):
                for route in report['routes']:
                    checked_at=route.get('queried_at',report.get('queried_at',saved['created_at']))
                    try:
                        route_age=(datetime.now(timezone.utc)-datetime.fromisoformat(checked_at.replace('Z','+00:00'))).total_seconds()
                        if not 0<=route_age<=1800:continue
                    except (ValueError,TypeError,AttributeError):continue
                    if route.get('basis') in ('coarse_estimate','area_estimate'):continue
                    if route.get('duration_minutes') is None or route['duration_minutes']>f['usyd_max_minutes'] or not timing_matches(route,target):continue
                    if mode!='public_transport' and mode not in route.get('transit_modes',[]):continue
                    maximum=f.get('usyd_max_transfers')
                    if maximum is not None and (type(route.get('transfers')) is not int or route['transfers']>maximum):continue
                    fresh[route['listing_id']]={**route,'queried_at':checked_at}
        except (KeyError,ValueError,TypeError,ApiError):fresh={}
    result=[]
    for row in rows:
        route=fresh.get(row['listing_id'])
        if route:
            item=deepcopy(row);annotation=item.get('usyd_commute')
            if annotation:
                if route.get('origin'):
                    from .snapshot import distance_metres
                    annotation['origin']=deepcopy(route['origin'])
                    annotation['straight_line_distance_m']=distance_metres(route['origin'])
                annotation['modes'][mode]={**deepcopy(route),'status':'planned','queried_at':route['queried_at'],
                    'reference_arrival_at':target.isoformat(),'basis':'recent_checked_query'}
                annotation['reference_arrival_at']=target.isoformat()
            result.append(item)
        elif reference_matches(row,f):result.append(row)
    return result
