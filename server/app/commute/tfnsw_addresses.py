"""Secondary building geocoder, restricted to exact street/suburb/number identities.

Only public catalogue addresses are accepted. Street/locality/stop results never
become house coordinates. A source building range is explicitly disclosed.
"""
from copy import deepcopy
from hashlib import sha256
import re,math
from urllib.parse import urlencode
from .locations import listing_address,normalized,valid_point
from ..real_data.providers import TFNSW_DOC
from ..common import now

ENDPOINT='https://api.transport.nsw.gov.au/v1/tp/stop_finder'


def query_params(row):
    return {'outputFormat':'rapidJSON','coordOutputFormat':'EPSG:4326',
            'name_sf':listing_address(row),'type_sf':'any','TfNSWSF':'true',
            'odvSugMacro':'1','anyMaxSizeHitList':5}


def number_rank(wanted,actual):
    if wanted==actual:return 0
    # Only an advertised single street number at an official range endpoint.
    # Never expand to arbitrary interior numbers, another street or a suburb.
    if re.fullmatch(r'\d+',wanted) and re.fullmatch(r'\d+-\d+',actual):
        low,high=map(int,actual.split('-'))
        if 0<high-low<=50 and int(wanted) in (low,high):return 1
    return None


def identity(row,entry):
    address=listing_address(row)
    matched=re.fullmatch(r'(\d+[A-Z]?(?:-\d+[A-Z]?)?) (.+)',address or '')
    if not matched or not isinstance(entry,dict):return None
    try:
        if entry['type']!='singlehouse' or normalized(entry['parent']['name'])!=normalized(row['suburb']):return None
        if str(entry['postCode'])!=str(row['postcode']):return None
        road=normalized(entry['streetName'])+' '+normalized(row['suburb'])
        if road!=matched[2]:return None
        return number_rank(matched[1],str(entry['buildingNumber']).upper())
    except (KeyError,TypeError,AttributeError):return None


def address_point(row,data,queried_at=None):
    candidates=[]
    if not isinstance(data,dict) or not isinstance(data.get('locations'),list) or len(data['locations'])>10:return None
    for entry in data['locations']:
        rank=identity(row,entry)
        if rank is None:continue
        try:
            raw_id=entry['id'];coords=entry['coord']
            if not isinstance(raw_id,str) or not raw_id.startswith('streetID:') or len(raw_id)>1000:continue
            if not isinstance(entry.get('name'),str) or not 1<=len(entry['name'])<=300:continue
            if not isinstance(coords,list) or len(coords)!=2:continue
            point={'latitude':coords[0],'longitude':coords[1]}
            if not valid_point(point):continue
            if type(entry.get('matchQuality')) not in (int,float) or not math.isfinite(entry['matchQuality']) or entry['matchQuality']<240:continue
            candidates.append((rank,entry,point))
        except (KeyError,TypeError):continue
    if not candidates:return None
    best=min(c[0] for c in candidates);candidates=[c for c in candidates if c[0]==best]
    # Same address with conflicting coordinates stays unresolved.
    if len({(c[2]['latitude'],c[2]['longitude']) for c in candidates})!=1:return None
    rank,entry,point=sorted(candidates,key=lambda c:c[1]['id'])[0]
    meta={k:deepcopy(entry[k]) for k in ('id','name','type','streetName','buildingNumber','postCode','parent','coord','matchQuality')}
    return {**point,'id':'tfnsw:address:'+sha256(entry['id'].encode()).hexdigest()[:24],
            'label':entry['name'],'provider':'tfnsw_stop_finder',
            'precision':'tfnsw_building_'+('range' if '-' in str(entry['buildingNumber']) else 'address')+'_not_unit_entrance',
            'source_url':TFNSW_DOC,'request_url':ENDPOINT+'?'+urlencode(query_params(row)),
            'matched_address':meta,'queried_at':queried_at or now(),
            'original_address':row['address'],'original_suburb':row['suburb']}


def valid_cached_point(row,point):
    if not isinstance(point,dict) or point.get('provider')!='tfnsw_stop_finder':return False
    try:
        rebuilt=address_point(row,{'locations':[point['matched_address']]},queried_at=point['queried_at'])
        return bool(rebuilt and point==rebuilt)
    except (KeyError,TypeError,ValueError):return False


def resolve(row,provider):
    if not listing_address(row) or not getattr(provider,'tfnsw_key',''):return None
    data=provider.request('GET',ENDPOINT,{'Authorization':'apikey '+provider.tfnsw_key,'Accept':'application/json'},
                          params=query_params(row))
    return address_point(row,data)
