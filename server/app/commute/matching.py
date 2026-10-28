"""Rental discovery uses stored duration estimates without a class-time deadline."""
from .snapshot import observation

TRANSIT=('public_transport','train','metro','bus')
FILTER_KEYS=('usyd_mode','usyd_max_minutes','usyd_arrival_time','usyd_travel_day','usyd_travel_date','usyd_max_transfers')


def reference_matches(row,filters):
    mode=filters.get('usyd_mode','public_transport');route=observation(row,mode)
    if not route:
        from .estimates import estimate_matches
        approximate={k:v for k,v in filters.items() if k not in ('usyd_arrival_time','usyd_travel_day','usyd_travel_date')}
        return estimate_matches(row,approximate)
    if route['duration_minutes']>filters['usyd_max_minutes']:return False
    if mode not in TRANSIT:return True
    maximum=filters.get('usyd_max_transfers')
    return maximum is None or (type(route.get('transfers')) is int and 0<=route['transfers']<=maximum)


def matching_for_case(ctx,case_id,filters,db=None):
    # Legacy scheduled reports remain historical records; they do not authorize
    # or veto the current approximate-duration recommendation pool.
    if case_id:
        if db is None:
            with ctx.repo.transaction() as connection:ctx.get(connection,'case',case_id)
        else:ctx.get(db,'case',case_id)
    return ctx.settings.catalog.matching(filters)
