"""Keyless official NSW Spatial Services points; never a suburb-centroid fallback.

Layer fields verified against the public ArcGIS REST layer metadata, October 2026.
A returned address/POI point is not a verified pedestrian entrance or unit location.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import math
import re
from ..common import ApiError, require
from ..real_data.providers import DataProviders

BASE = 'https://portal.spatial.nsw.gov.au/server/rest/services/'
ADDRESS = BASE + 'NSW_Geocoded_Addressing_Theme_multiCRS/MapServer/1'
POIS = (
    ('university', BASE + 'NSW_FOI_Education_Facilities_multiCRS/MapServer/5'),
    ('station', BASE + 'NSW_FOI_Transport_Facilities_multiCRS/MapServer/1'),
    ('building', BASE + 'NSW_Features_of_Interest_Category_multiCRS/MapServer/3'),
)
# Normalization changes spelling, never the house number, street or suburb identity.
STREET_WORDS = {'ST':'STREET','RD':'ROAD','AVE':'AVENUE','AV':'AVENUE','PDE':'PARADE',
                'HWY':'HIGHWAY','CT':'COURT','PL':'PLACE','DR':'DRIVE','CRES':'CRESCENT',
                'TCE':'TERRACE','LN':'LANE','CCT':'CIRCUIT'}


def normalized(value):
    text = re.sub(r'[,.;]', ' ', value.upper())
    return ' '.join(STREET_WORDS.get(word, word) for word in text.split())


def valid_point(point):
    return (isinstance(point, dict) and all(type(point.get(k)) in (int,float) and math.isfinite(point[k])
            for k in ('latitude','longitude')) and -37.6 <= point['latitude'] <= -28.0
            and 140.9 <= point['longitude'] <= 159.2)


def listing_address(row):
    address,suburb=row.get('address'),row.get('suburb')
    if not isinstance(address,str) or not isinstance(suburb,str): return None
    address=normalized(address)
    address=re.sub(r'^FURNISHED\s+(?=\d)', '', address)
    address=re.sub(r'^(?:UNIT\s+)?[A-Z0-9-]+\s*/\s*(?=\d)', '', address)
    suburb=normalized(suburb)
    if not address.endswith(' '+suburb): address+=' '+suburb
    return address if re.match(r'^\d+[A-Z]?(?:-\d+[A-Z]?)?\s+\S',address) else None


def is_listed_range_endpoint(row,point):
    """A sourced endpoint within an advertised building-number range, not an exact unit."""
    address=listing_address(row)
    matched=re.fullmatch(r'(\d+)-(\d+) (.+)',address or '')
    actual=re.fullmatch(r'(\d+) (.+)',normalized(point.get('label','')))
    return bool(matched and actual and int(actual[1]) in (int(matched[1]),int(matched[2])) and actual[2]==matched[3])


def validated_origin(row,point):
    if not isinstance(point,dict):return False
    if point.get('provider')=='tfnsw_stop_finder':
        from .tfnsw_addresses import valid_cached_point
        return valid_cached_point(row,point)
    identifier=row.get('listing_id') or row.get('record_id')
    if LocationResolver(points={identifier:point}).cached_listing(row):return True
    if point.get('precision')!='official_listed_range_endpoint_not_unit_entrance' or not is_listed_range_endpoint(row,point):return False
    if point.get('original_address')!=row['address'] or point.get('original_suburb')!=row['suburb']:return False
    canonical=deepcopy(point)
    canonical.update(precision='official_address_point_not_unit_entrance',original_address=point['label'])
    exact={**row,'address':point['label']}
    return bool(LocationResolver(points={identifier:canonical}).cached_listing(exact))


class LocationResolver:
    def __init__(self, transport=None, points=None):
        self.provider = DataProviders(env={}, transport=transport)
        self.provider.timeout = 5
        self._listing_cache = {}
        self._seeded_points = deepcopy(points) if isinstance(points,dict) else {}

    def _query(self, url, kind, where, limit):
        fields = ('OBJECTID,address,addresspointtype,addresspointuncertainty' if kind == 'address'
                  else 'OBJECTID,generalname,alternativelabel,planimetricaccuracy')
        data = self.provider.request('GET', url + '/query', {'Accept':'application/json'}, params={
            'f':'json','where':where,'outFields':fields,'outSR':'4326',
            'returnGeometry':'true','resultRecordCount':limit,
            **({'orderByFields':'generalname ASC'} if kind!='address' else {})})
        try:
            if (not isinstance(data,dict) or 'error' in data or not isinstance(data.get('features'),list)
                    or len(data['features']) > limit or data.get('spatialReference',{}).get('wkid') != 4326):
                raise ValueError()
            result = []
            for feature in data['features']:
                attrs, geometry = feature['attributes'], feature['geometry']
                oid = attrs['OBJECTID']
                label = attrs.get('address') if kind=='address' else attrs.get('generalname') or attrs.get('alternativelabel')
                if not isinstance(label,str) or not label.strip() or len(label)>300 or type(oid) is not int or oid<=0:
                    raise ValueError()
                alternative = attrs.get('alternativelabel')
                if kind!='address' and isinstance(alternative,str) and alternative.strip() and alternative not in label:
                    label += ' — ' + alternative
                point = {'id':f'nsw:{kind}:{oid}', 'label':label.strip(), 'latitude':geometry['y'],
                         'longitude':geometry['x'], 'precision': 'official_address_point_not_unit_entrance' if kind=='address'
                         else 'official_poi_point_not_entrance', 'source_url':url + '/query?objectIds=' + str(oid) + '&outFields=*&outSR=4326&f=pjson'}
                if not valid_point(point): raise ValueError()
                accuracy=attrs.get('addresspointuncertainty') if kind=='address' else attrs.get('planimetricaccuracy')
                if type(accuracy) in (int,float) and math.isfinite(accuracy) and accuracy>=0:
                    point['accuracy_metres']=accuracy
                result.append(point)
            return result
        except (KeyError,TypeError,ValueError,AttributeError):
            raise ApiError(502,'location_invalid_response','The NSW location response could not be validated. No coordinates were generated.') from None

    def search(self, query, limit=5):
        require(isinstance(query,str) and 2<=len(query.strip())<=180 and
                not any(ord(c)<32 for c in query),422,'invalid_location_query','Provide an address or place name of 2 to 180 characters.')
        require(type(limit) is int and 1<=limit<=5,422,'invalid_location_limit','At most 5 location candidates are allowed.')
        query = normalized(query.strip())
        # SQL literal escaping plus removal of wildcard syntax; fixed fields and host only.
        literal = query.replace("'", "''").replace('%','').replace('_','')
        if re.match(r'^\d',query):
            return self._query(ADDRESS,'address',f"address = '{literal}'",limit)
        tokens=literal.split()
        # Each supplied token must occur in either field. Campus qualifiers may be
        # stored separately from the institution name and must never be dropped.
        where=' AND '.join(f"(UPPER(generalname) LIKE '%{token}%' OR UPPER(alternativelabel) LIKE '%{token}%')"
                           for token in tokens)
        def run(spec):
            kind,url=spec
            try:
                return self._query(url,kind,where,limit)
            except ApiError as error:
                return error
        # At most three independent public queries; each has a 5-second total timeout.
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(run,POIS))
        found={}
        for result in results:
            if not isinstance(result,list): continue
            for item in result:
                label=normalized(item['label'])
                if not all(re.search(r'(?<!\w)'+re.escape(token)+r'(?!\w)',label) for token in query.split()): continue
                # The university and building layers may expose the same physical
                # feature; identical names/points do not represent campus ambiguity.
                key=(label,round(item['latitude'],8),round(item['longitude'],8))
                found.setdefault(key,item)
        if not found:
            errors=[result for result in results if isinstance(result,ApiError)]
            if errors: raise errors[0]
        return list(found.values())[:limit]

    def listing(self, row):
        cached=self.cached_listing(row)
        if cached: return cached
        address=listing_address(row)
        if not address: return None
        if address in self._listing_cache: return deepcopy(self._listing_cache[address])
        literal=address.replace("'","''")
        candidates=self._query(ADDRESS,'address',f"address = '{literal}'",5)
        matches=[item for item in candidates if normalized(item['label'])==address]
        # Multiple address points remain ambiguous, even when all labels match.
        result=matches[0] if len(matches)==1 and len(candidates)<5 else None
        self._listing_cache[address]=deepcopy(result)
        return deepcopy(result)

    def cached_listing(self,row):
        """Only matching source-backed cached points; this method performs no I/O."""
        address=listing_address(row)
        if not address: return None
        if address in self._listing_cache: return deepcopy(self._listing_cache[address])
        point=self._seeded_points.get(row.get('listing_id') or row.get('record_id'))
        if isinstance(point,dict) and point.get('provider')=='tfnsw_stop_finder':
            from .tfnsw_addresses import valid_cached_point
            return deepcopy(point) if valid_cached_point(row,point) else None
        if (not isinstance(point,dict) or not valid_point(point)
                or point.get('original_address')!=row.get('address') or point.get('original_suburb')!=row.get('suburb')
                or not isinstance(point.get('label'),str) or normalized(point['label'])!=address
                or not re.fullmatch(r'nsw:address:[1-9]\d*',point.get('id',''))
                or point.get('precision')!='official_address_point_not_unit_entrance'):
            return None
        oid=point['id'].rsplit(':',1)[1]
        expected=ADDRESS+'/query?objectIds='+oid+'&outFields=*&outSR=4326&f=pjson'
        if point.get('source_url')!=expected: return None
        return {key:deepcopy(value) for key,value in point.items() if key not in ('original_address','original_suburb')}

    def prefetch(self,rows,batch_size=20):
        """Explicit one-time public-data harvest. Caller supplies external-data consent.

        Queries exact building addresses in chunks of twenty with three workers;
        no file writes, inferred points, retries or per-turn automatic invocation.
        """
        require(isinstance(rows,list) and len(rows)<=1000,422,'location_batch_limit','Location collection supports at most 1000 public listings.')
        require(type(batch_size) is int and 1<=batch_size<=20,422,'location_batch_limit','Address batches must contain 1 to 20 items.')
        groups={}
        for row in rows:
            address=listing_address(row)
            if address: groups.setdefault(address,[]).append(row)
        addresses=list(groups)
        batches=[addresses[i:i+batch_size] for i in range(0,len(addresses),batch_size)]
        def run(batch):
            literals=','.join("'"+item.replace("'","''")+"'" for item in batch)
            try:
                candidates=self._query(ADDRESS,'address','address IN ('+literals+')',100)
                if len(candidates)>=100: return {},'The address response reached its limit. Coordinates for this batch were not accepted.'
                points={}
                for address in batch:
                    matches=[point for point in candidates if normalized(point['label'])==address]
                    point=matches[0] if len(matches)==1 else None
                    self._listing_cache[address]=deepcopy(point)
                    if point:
                        for row in groups[address]:
                            identifier=row.get('listing_id') or row.get('record_id')
                            points[identifier]={**point,'original_address':row['address'],'original_suburb':row['suburb']}
                return points,None
            except ApiError as error: return {},error.message
        with ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(run,batches))
        points={identifier:point for result,error in results for identifier,point in result.items()}
        return {'points':points,'queried_count':len(addresses),'resolved_count':len(points),
                'errors':[error for result,error in results if error]}
