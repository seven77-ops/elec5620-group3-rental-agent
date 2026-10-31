"""Validated all-listing USYD annotations, independent of user case data."""
from copy import deepcopy
from datetime import datetime,timezone
import json, math
from pathlib import Path
from .usyd import DESTINATION,CAMPUS_FINGERPRINT,MODES
from .locations import valid_point


def distance_metres(origin,destination=DESTINATION):
    lat1,lat2=map(math.radians,(origin['latitude'],destination['latitude']))
    dlat=lat2-lat1;dlon=math.radians(destination['longitude']-origin['longitude'])
    return round(6371008.8*2*math.asin(min(1,math.sqrt(math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2))))


def load_snapshot(catalog,path=None):
    path=Path(path) if path else catalog.path.with_name('usyd-commutes.json')
    if not path.is_file():return None
    try:
        data=json.loads(path.read_text())
        if data.get('schema_version')!='1.0' or data.get('catalog_fingerprint')!=catalog.fingerprint or data.get('campus_fingerprint')!=CAMPUS_FINGERPRINT or data.get('destination')!=DESTINATION:return None
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(data['generated_at'].replace('Z','+00:00'))).total_seconds()
        if not 0<=age<=30*86400:return None
        records=data['records']
        if set(records)!=set(catalog._rows):return None
        from .locations import validated_origin
        for key,record in records.items():
            source=catalog._rows[key]
            if record['listing_id']!=key or record['address']!=source['address'] or record['suburb']!=source['suburb']:return None
            origin=record.get('origin')
            if origin is not None and not valid_point(origin):return None
            if origin is not None and not validated_origin(source,origin):return None
            if set(record['modes'])!=set(MODES):return None
            if 'transit_options' in record:
                from .transit_options import valid_option,LIMIT
                extra=record['transit_options']
                if not isinstance(extra,list) or len(extra)>LIMIT or (extra and not valid_point(origin)):return None
                if any(not valid_option(route,fresh=False) for route in extra):return None
            for mode,route in record['modes'].items():
                value=route.get('duration_minutes')
                if route['status'] not in ('planned','routing_estimate','unavailable','no_observed_option'):return None
                if value is not None:
                    if not valid_point(origin) or type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=10080:return None
                    if route['status'] not in ('planned','routing_estimate'):return None
                    backend={'walk':'foot','bike':'bike','drive':'car'}.get(mode)
                    host=f'https://routing.openstreetmap.de/routed-{backend}/' if backend else 'https://opendata.transport.nsw.gov.au/'
                    if not route.get('source_url','').startswith(host):return None
                    if mode in ('train','metro','bus') and mode not in route.get('transit_modes',[]):return None
        return data
    except (OSError,ValueError,TypeError,KeyError,AttributeError):return None


def public_record(data,identifier):
    if not data:return None
    record=deepcopy(data['records'].get(identifier))
    if not record:return None
    from .transit_options import options
    record.pop('selected_transit_route',None)
    record['transit_options']=options(record)
    record.update(destination=deepcopy(DESTINATION),generated_at=data['generated_at'],
                  reference_arrival_at=record['modes']['public_transport'].get('reference_arrival_at') or data.get('reference_arrival_at'),reference_note=DESTINATION['reference_note'])
    return record


def observation(row,mode,max_transfers=None):
    annotation=row.get('usyd_commute') or {}
    from .transit_options import TRANSIT,select
    if mode in TRANSIT:return select(annotation,mode,max_transfers)
    item=annotation.get('modes',{}).get(mode)
    if not item or item.get('status') not in ('planned','routing_estimate') or item.get('duration_minutes') is None:return None
    if item['status'] in ('planned','routing_estimate'):
        try:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(item['queried_at'].replace('Z','+00:00'))).total_seconds()
            if not 0<=age<=(7 if item['status']=='planned' else 30)*86400:return None
        except (KeyError,ValueError,TypeError):return None
    # Scheduled transit snapshots are for discovery, never live arrival verification.
    return item
