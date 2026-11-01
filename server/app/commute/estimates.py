"""Explicit coarse ranges derived from current, located houses on the street/in the area.

These estimates never create coordinates, planned journeys, transfer counts or precision.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json,math,re,statistics
from zoneinfo import ZoneInfo
from .locations import listing_address,normalized
from .usyd import MODES

LABELS={'street':'Street estimate','suburb':'Suburb estimate','postcode':'Postcode estimate'}


def street_key(row):
    address=listing_address(row)
    if not address:return None
    suburb=normalized(row['suburb'])
    road=re.sub(r'^\d+[A-Z]?(?:-\d+[A-Z]?)?\s+','',address)
    return (suburb,road)


def current(route):
    if not isinstance(route,dict) or route.get('status') not in ('planned','routing_estimate'):return False
    value=route.get('duration_minutes')
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=10080:return False
    try:
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(route['queried_at'].replace('Z','+00:00'))).total_seconds()
        return 0<=age<=(7 if route['status']=='planned' else 30)*86400
    except (KeyError,TypeError,ValueError):return False


def derive_estimates(rows,records):
    groups={level:defaultdict(list) for level in LABELS}
    for identifier,record in records.items():
        row=rows.get(identifier)
        if not row or not record.get('origin'):continue
        for mode,route in record.get('modes',{}).items():
            if not current(route):continue
            anchor={'id':identifier,'point':record['origin'].get('id',identifier),'route':route}
            street=street_key(row)
            if street:groups['street'][(street,mode)].append(anchor)
            groups['suburb'][(row['suburb'],mode)].append(anchor)
            groups['postcode'][(row['postcode'],mode)].append(anchor)
    result={}
    for identifier,row in rows.items():
        if records.get(identifier,{}).get('origin'):continue
        modes={}
        for mode in MODES:
            for level,key in (('street',street_key(row)),('suburb',row['suburb']),('postcode',row['postcode'])):
                candidates=groups[level].get((key,mode),[]) if key else []
                # Several apartments at one building do not establish area coverage.
                unique={a['point']:a for a in sorted(candidates,key=lambda a:a['id'])}
                anchors=list(unique.values())
                if not anchors:continue
                if mode in ('public_transport','train','metro','bus'):
                    timed=defaultdict(list)
                    for anchor in anchors:
                        stamp=anchor['route'].get('reference_arrival_at')
                        if stamp:
                            try:
                                local=datetime.fromisoformat(stamp).astimezone(ZoneInfo('Australia/Sydney'))
                                timed[(local.strftime('%H:%M'),'weekday' if local.weekday()<5 else 'weekend')].append(anchor)
                            except (ValueError,TypeError):continue
                    if not timed:continue
                    anchors=max(timed.values(),key=len)
                values=[a['route']['duration_minutes'] for a in anchors]
                padding={'street':{'walk':5,'bike':4,'drive':5},'suburb':{'walk':15,'bike':8,'drive':10},'postcode':{'walk':20,'bike':12,'drive':15}}[level].get(mode,{'street':8,'suburb':12,'postcode':18}[level])
                if len(anchors)==1 and level!='street':padding+=5
                stamps=[a['route']['queried_at'] for a in anchors]
                source=[{'id':a['id'],'point':a['point'],'route':a['route']} for a in anchors]
                modes[mode]={'status':'coarse_estimate','level':level,'label':LABELS[level],
                    'lower_minutes':max(1,math.floor(min(values)-padding)),
                    'upper_minutes':math.ceil(max(values)+padding),
                    'typical_minutes':round(statistics.median(values)),
                    'anchor_count':len(anchors),'source_listing_ids':[a['id'] for a in anchors],
                    'source_urls':sorted({a['route']['source_url'] for a in anchors}),
                    'queried_at':min(stamps),'reference_arrival_at':anchors[0]['route'].get('reference_arrival_at'),
                    'evidence_fingerprint':sha256(json.dumps(source,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                    'method':'located_neighbour_route_range_with_location_margin',
                    'limitations':'Estimated from existing routes on the same street, suburb or postcode with a location margin. This property has not been located precisely; this is not actual door-to-campus travel time.'}
                break
        if modes:result[identifier]=modes
    return result


def estimate_for(row,mode):
    item=(row.get('usyd_commute') or {}).get('estimates',{}).get(mode)
    if not isinstance(item,dict) or item.get('status')!='coarse_estimate':return None
    try:
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(item['queried_at'].replace('Z','+00:00'))).total_seconds()
        if not 0<=age<=(7 if mode in ('public_transport','train','metro','bus') else 30)*86400:return None
        if not 0<item['lower_minutes']<=item['upper_minutes']<=10140:return None
    except (KeyError,ValueError,TypeError):return None
    return item


def estimate_matches(row,filters):
    mode=filters.get('usyd_mode','public_transport');item=estimate_for(row,mode)
    if not item or item['upper_minutes']>filters['usyd_max_minutes']:return False
    if mode in ('public_transport','train','metro','bus'):
        # A coarse area range cannot establish a particular trip date or transfer cap.
        if filters.get('usyd_travel_date') or filters.get('usyd_max_transfers') is not None:return False
        try:
            stamp=datetime.fromisoformat(item['reference_arrival_at']).astimezone(ZoneInfo('Australia/Sydney'))
            if filters.get('usyd_arrival_time') and filters['usyd_arrival_time']!=stamp.strftime('%H:%M'):return False
            if filters.get('usyd_travel_day') and (stamp.weekday()<5)!=(filters['usyd_travel_day']=='weekday'):return False
        except (KeyError,ValueError,TypeError):return False
    return True


def attach_estimates(answer,rows,brief):
    """Inspection cards only: never create an eligible listing or a checked journey."""
    mode=brief.get('commute_mode','public_transport')
    maximum=brief.get('commute_max_minutes',240)
    report=answer['commute_recommendation']
    checked={r['listing_id'] for r in report.get('routes',[]) if r.get('duration_minutes') is not None}
    checked.update(r['listing_id'] for r in answer.get('listings',[]))
    candidates=[r for r in rows if r['listing_id'] not in checked
                and not (r.get('usyd_commute') or {}).get('origin') and estimate_for(r,mode)]
    candidates.sort(key=lambda r:(estimate_for(r,mode)['upper_minutes']>maximum,
                                 estimate_for(r,mode)['upper_minutes'],r['weekly_rent'],r['listing_id']))
    report['estimated_listings']=deepcopy(candidates[:6])
    shown={r['listing_id'] for r in candidates[:6]}
    report['pending_listings']=[r for r in report.get('pending_listings',[]) if r['listing_id'] not in shown]
    return answer
