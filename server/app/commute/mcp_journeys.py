"""Convert MCP summaries to existing route facts; recompute elapsed and transfers."""
import math
from datetime import datetime,timezone
from ..common import ApiError

MODES={'TRAIN':'train','METRO':'metro','BUS':'bus','COACH':'bus','SCHOOL_BUS':'bus',
       'LIGHT_RAIL':'light_rail','FERRY':'ferry','WALK':'walk','WALK_ALT':'walk','CYCLE':'bike'}

def instant(value):
    if not isinstance(value,str):raise ValueError()
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.utcoffset() is None:raise ValueError()
    return stamp.astimezone(timezone.utc)

def number(value,low=0,high=10080):
    return type(value) in (int,float) and math.isfinite(value) and low<=value<=high

def short(value,limit=180):
    return value[:limit] if isinstance(value,str) else None

def normalize_journeys(payload):
    try:
        entries=payload['journeys']
        if not isinstance(entries,list) or len(entries)>5:raise ValueError()
        result=[]
        for entry in entries:
            start,end=instant(entry['departure']),instant(entry['arrival'])
            elapsed=(end-start).total_seconds()/60
            if not number(elapsed) or type(entry['changes']) is not int or not 0<=entry['changes']<=50:raise ValueError()
            source_legs=entry['legs']
            if not isinstance(source_legs,list) or not 1<=len(source_legs)<=100:raise ValueError()
            legs=[];transit=[];services=[];walking=0;walking_known=True;previous=start
            for item in source_legs:
                mode=MODES.get(item['mode'])
                # Upstream enum omits some Metro classes. Unknown legs use our
                # direct provider instead of being mislabeled as train or walk.
                if not mode:raise ValueError()
                if not number(item.get('duration_min')):raise ValueError()
                origin,destination=item['from'],item['to']
                if not isinstance(origin,dict) or not isinstance(destination,dict):raise ValueError()
                departure,arrival=origin.get('departure'),destination.get('arrival')
                minutes=item['duration_min']
                if departure and arrival:
                    begin,finish=instant(departure),instant(arrival)
                    if not previous<=begin<=finish<=end:raise ValueError()
                    previous=finish;minutes=(finish-begin).total_seconds()/60
                elif mode=='walk':walking_known=False
                if mode=='walk':walking+=minutes
                elif mode!='bike':transit.append(mode)
                service=short(item.get('route'))
                if service and service not in services:services.append(service)
                legs.append({'mode':mode,'duration_minutes':round(minutes,2),'service':service,
                    'from':short(origin.get('name')),'to':short(destination.get('name')),
                    'departure_at':departure,'arrival_at':arrival,
                    'from_stop_id':stop_id(origin.get('id')),'to_stop_id':stop_id(destination.get('id')),
                    'platform':short(origin.get('platform'),100),
                    'alerts':[a[:300] for a in item.get('alerts',[])[:5] if isinstance(a,str)] if isinstance(item.get('alerts',[]),list) else []})
            transfers=max(0,len(transit)-1)
            if entry['changes']!=transfers:raise ValueError()
            result.append({'duration_minutes':round(elapsed,2),'walking_minutes':round(walking,2) if walking_known else None,
                'transfers':transfers,'departure_at':entry['departure'],'arrival_at':entry['arrival'],
                'transit_modes':list(dict.fromkeys(transit)),'services':services,'legs':legs})
        return result
    except (KeyError,ValueError,TypeError,AttributeError,OverflowError):
        raise ApiError(502,'mcp_invalid_route','The transit service route failed timetable or transport-mode checks.') from None

def stop_id(value):
    return value if isinstance(value,str) and value.isascii() and value.isdigit() and 3<=len(value)<=12 else None
