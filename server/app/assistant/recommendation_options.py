"""Deterministic filter context and one-change counterfactuals over the same inventory."""
from copy import deepcopy
from .commute_choice import normalize

FIELD_MAP = {'budget_amount':'max_weekly_rent','commute_mode':'usyd_mode',
             'commute_max_minutes':'usyd_max_minutes','max_transfers':'usyd_max_transfers',
             **{k:k for k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces')}}


def filters_for(brief):
    brief=normalize(brief)
    result={k:brief[k] for k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces') if brief.get(k) is not None}
    if brief.get('budget_period')=='week' and brief.get('budget_scope')=='whole_property' and brief.get('budget_amount') is not None:
        result['max_weekly_rent']=brief['budget_amount']
    if brief.get('commute_mode') and brief.get('commute_max_minutes'):
        result.update(usyd_mode=brief['commute_mode'],usyd_max_minutes=brief['commute_max_minutes'])
        if brief.get('max_transfers') is not None:result['usyd_max_transfers']=brief['max_transfers']
    return result


def criteria_for(filters,brief=None):
    result=normalize(brief or {})
    for key in ('arrival_time','travel_date','travel_day'):result.pop(key,None)
    for target,source in FIELD_MAP.items():
        if source in filters:result[target]=filters[source]
    if 'max_weekly_rent' in filters:result['budget_period']='week'
    if 'suburb' not in filters:result['suburb']=None
    return result


def alternatives(catalog,filters,total):
    if total:return []
    choices=[]
    if 'max_weekly_rent' in filters and filters['max_weekly_rent']<=1_000_000_000_000-50:
        amount=filters['max_weekly_rent']+50
        choices.append(('budget',f'Increase weekly rent limit by AUD 50 (to {amount:g}/week)',{'budget_amount':amount}))
    if 'usyd_max_minutes' in filters and filters['usyd_max_minutes']<=230:
        minutes=filters['usyd_max_minutes']+10
        choices.append(('commute',f'Increase commute limit by 10 minutes (to {minutes} minutes)',{'commute_max_minutes':minutes}))
    if filters.get('suburb'):choices.append(('area','Expand to all suburbs',{'suburb':None}))
    result=[]
    for identifier,label,patch in choices:
        changed=deepcopy(filters)
        for key,value in patch.items():
            if value is None:changed.pop(FIELD_MAP[key],None)
            else:changed[FIELD_MAP[key]]=value
        count=len(catalog.matching(changed))
        result.append({'id':identifier,'label':label,'patch':patch,'count':count,'additional_count':count-total})
    return result


def metadata(catalog,filters,brief=None,total=None):
    filters=catalog.filters(filters)
    total=len(catalog.matching(filters)) if total is None else total
    return {'recommendation_criteria':criteria_for(filters,brief),'recommendation_filters':filters,
            'recommendation_catalog_fingerprint':catalog.fingerprint,
            'recommendation_alternatives':alternatives(catalog,filters,total)}
