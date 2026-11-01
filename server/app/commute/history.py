"""Reuse only recent reports for the same complete scheduled query."""
from copy import deepcopy
from datetime import datetime,timezone


def recent_routes(reports,brief,destination,arrival,listing_ids,catalog_fingerprint):
    from .planner import timing_matches,number
    result={}
    expected={**brief,'commute_hard_limit':True}
    for report in reports or []:
        if (report.get('destination')!=destination or report.get('criteria')!=expected
                or report.get('catalog_fingerprint')!=catalog_fingerprint):continue
        try:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(report['queried_at'].replace('Z','+00:00'))).total_seconds()
            if not 0<=age<=1800:continue
        except (KeyError,ValueError,TypeError):continue
        for route in report.get('routes',[]):
            if route.get('listing_id') not in listing_ids:continue
            checked_at=route.get('queried_at',report['queried_at'])
            try:
                age=(datetime.now(timezone.utc)-datetime.fromisoformat(checked_at.replace('Z','+00:00'))).total_seconds()
                if not 0<=age<=1800:continue
            except (ValueError,TypeError,AttributeError):continue
            route={**route,'queried_at':checked_at}
            if route.get('duration_minutes') is not None:
                if route.get('basis')!='scheduled_live_query' or not timing_matches(route,arrival):continue
                mode=brief.get('commute_mode','public_transport')
                if mode!='public_transport' and mode not in route.get('transit_modes',[]):continue
                minutes=route['duration_minutes']
                if not number(minutes,0,10080):continue
                maximum=brief.get('max_transfers')
                if maximum is not None and (type(route.get('transfers')) is not int or not 0<=route['transfers']<=maximum):continue
                route={**route,'status':'ok' if minutes<=brief['commute_max_minutes'] else 'over_limit'}
            elif route.get('status') not in ('unavailable','unsupported'):continue
            if 'transit_options' in route:
                from .transit_options import valid_option,distinct
                items=route['transit_options']
                route['transit_options']=distinct([r for r in items[:30] if valid_option(r)]) if isinstance(items,list) else []
            result[route['listing_id']]=deepcopy(route)
    return result
