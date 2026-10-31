"""Validated, immutable public-advertisement snapshot. No synthetic fallback."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit
from ..bootstrap import ROOT
from ..common import require
from .photos import load_photos

CORE_FIELDS = ('bedrooms', 'bathrooms', 'car_spaces', 'weekly_rent')
FILTER_FIELDS = ('usyd_arrival_time','usyd_travel_day','usyd_travel_date','usyd_max_transfers','usyd_max_minutes','usyd_mode','suburb', 'min_bedrooms', 'min_bathrooms', 'min_car_spaces', 'max_weekly_rent', 'sort')


def catalog_fingerprint(rows):
    """Bind facts using the established display-token encoding across UI locales."""
    canonical_rows = [dict(row, bedroom_label='1\uff08\u5f00\u653e\u5f0f\uff09')
                      if row['bedroom_count_basis']=='open_plan_as_one' else row for row in rows]
    return hashlib.sha256(json.dumps(canonical_rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


class RealCatalog:
    def __init__(self, path=None, photos_path=None):
        self.path = Path(path) if path is not None else ROOT / 'agent2/data/real/listings.json'
        rows = json.loads(self.path.read_text())
        if not isinstance(rows, list) or not rows:
            raise ValueError('Real listing catalogue must be a nonempty array')
        identifiers, urls, addresses = set(), set(), set()
        try:
            for row in rows:
                if not isinstance(row, dict): raise ValueError('Invalid catalogue row')
                identifier, url = row['record_id'], urlsplit(row['source_url'])
                if (row['source_platform'] != 'domain' or not identifier.startswith('domain:')
                    or identifier != 'domain:' + row['source_listing_id']
                    or not row['source_listing_id'].isdigit()
                    or url.scheme != 'https' or url.hostname != 'www.domain.com.au'
                    or url.username or url.password or url.port or url.query or url.fragment
                    or not url.path.endswith('-'+row['source_listing_id'])
                    or row['listing_status'] != 'advertised_unconfirmed'
                    or row['verification_status'] != 'public_advertisement_only'
                    or not row['suburb'] or not row['address']):
                    raise ValueError('Only real public candidate advertisements are accepted')
                if re.search(r'car\s*space|carspace|parking space|storage unit|garage only', row['address'], re.I):
                    raise ValueError('Parking-only and storage advertisements are not residential listings')
                for key in CORE_FIELDS:
                    value = row[key]
                    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                        raise ValueError('Missing or invalid core housing field')
                if row['weekly_rent'] <= 0 or row['weekly_rent'] > 100000:
                    raise ValueError('Invalid advertised weekly rent')
                if any(row[k] > 100 for k in CORE_FIELDS[:3]): raise ValueError('Invalid housing count')
                datetime.fromisoformat(row['captured_at'])
                address = (' '.join(row['address'].casefold().split()), row['postcode'])
                if identifier in identifiers or row['source_url'] in urls or address in addresses:
                    raise ValueError('Duplicate real advertisement')
                identifiers.add(identifier); urls.add(row['source_url']); addresses.add(address)
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError('Real catalogue is incomplete or malformed') from exc
        self._rows = {row['record_id']: deepcopy(row) for row in rows}
        # Project policy requested by the user: an advertised zero-bedroom studio
        # counts as one open-plan sleeping space, never as a separate bedroom.
        for row in self._rows.values():
            row['advertised_bedrooms'] = row['bedrooms']
            row['bedroom_count_basis'] = 'open_plan_as_one' if row['bedrooms'] == 0 else 'advertised'
            if row['bedrooms'] == 0:
                row['bedrooms'] = 1
                row['bedroom_label'] = '1 (open-plan)'
            else:
                row['bedroom_label'] = f"{row['bedrooms']:g}"
        self.suburbs = sorted({r['suburb'] for r in rows})
        self.as_of = max(row['captured_at'] for row in rows)
        # Keep the established catalogue binding stable across display-language changes.
        # Only the legacy display token is canonicalised; listing facts still enter the hash.
        self.fingerprint = catalog_fingerprint(self._rows.values())
        from ..commute.snapshot import load_snapshot
        self.commutes=load_snapshot(self)
        if self.commutes:
            from ..commute.estimates import derive_estimates
            for record in self.commutes['records'].values():record.pop('estimates',None)
            estimates=derive_estimates(self._rows,self.commutes['records'])
            for identifier,modes in estimates.items():self.commutes['records'][identifier]['estimates']=modes
            self.commutes.setdefault('coverage',{})['coarse_estimated']=len(estimates)
        self._photos = load_photos(Path(photos_path) if photos_path is not None else self.path.with_name('photos.json'), self._rows)

    def metadata(self):
        return {'data_mode': 'real_listings', 'total': len(self._rows), 'suburb_count': len(self.suburbs),
                'suburbs': list(self.suburbs), 'captured_at': self.as_of, 'fingerprint': self.fingerprint,
                'core_fields': list(CORE_FIELDS), 'availability_verified': False,
                'detail_read_count': sum(r['source_observation']['detail_read'] for r in self._rows.values()),
                'open_plan_as_one_count': sum(r['bedroom_count_basis']=='open_plan_as_one' for r in self._rows.values()),
                'audience':'USYD Camperdown/Darlington students','usyd_commute_coverage':(self.commutes or {}).get('coverage'),
                'photo_listing_count': len(self._photos),
                'photo_count': sum(len(photos) for photos in self._photos.values())}

    def get(self, identifier):
        require(identifier in self._rows, 404, 'listing_not_found', 'Live listing advertisement not found.')
        from ..commute.snapshot import public_record
        return {**deepcopy(self._rows[identifier]), 'listing_id': identifier, 'commute_minutes': None,
                'usyd_commute':public_record(self.commutes,identifier),
                'photos': deepcopy(self._photos.get(identifier, []))}

    def filters(self, values):
        require(isinstance(values, dict) and not set(values) - set(FILTER_FIELDS), 422, 'invalid_filters', 'Invalid listing filter fields.')
        result = {k:v for k,v in values.items() if v is not None and k not in ('usyd_arrival_time','usyd_travel_day','usyd_travel_date')}
        if 'suburb' in result:
            require(isinstance(result['suburb'], str) and result['suburb'] in self.suburbs, 422, 'invalid_filters', 'Choose a suburb in the listing catalogue.')
        for key in ('min_bedrooms', 'min_bathrooms', 'min_car_spaces'):
            if key in result:
                require(type(result[key]) is int and 0 <= result[key] <= 100, 422, 'invalid_filters', 'Room and parking counts must be integers from 0 to 100.')
        if 'max_weekly_rent' in result:
            amount = result['max_weekly_rent']
            require(type(amount) in (int, float) and math.isfinite(amount) and 0 <= amount <= 1000000000000,
                    422, 'invalid_filters', 'Maximum advertised weekly rent must be a valid number from 0 to 1000000000000.')
        if 'usyd_mode' in result:
            from ..commute.usyd import MODES
            require(result['usyd_mode'] in MODES,422,'invalid_filters','Choose a supported campus commute mode.')
        if 'usyd_max_minutes' in result:
            require(type(result['usyd_max_minutes']) is int and 1<=result['usyd_max_minutes']<=240,422,'invalid_filters','The campus commute limit must be 1 to 240 minutes.')
        if 'usyd_arrival_time' in result:require(isinstance(result['usyd_arrival_time'],str) and bool(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',result['usyd_arrival_time'])),422,'invalid_filters','Arrival time must use HH:mm.')
        if 'usyd_travel_day' in result:require(result['usyd_travel_day'] in ('weekday','weekend'),422,'invalid_filters','Choose weekdays or weekends.')
        if 'usyd_travel_date' in result:
            try:datetime.strptime(result['usyd_travel_date'],'%Y-%m-%d')
            except (ValueError,TypeError):require(False,422,'invalid_filters','Invalid travel date format.')
        if 'usyd_max_transfers' in result:require(type(result['usyd_max_transfers']) is int and 0<=result['usyd_max_transfers']<=5,422,'invalid_filters','The transfer limit must be 0 to 5.')
        result.setdefault('sort', 'rent_asc')
        require(result['sort'] in ('rent_asc', 'rent_desc', 'bedrooms_desc'), 422, 'invalid_filters', 'Choose a supported sort order.')
        return result

    def matching(self, filters):
        f = self.filters(filters)
        rows = list(self._rows.values())
        if 'suburb' in f: rows = [r for r in rows if r['suburb'] == f['suburb']]
        for field in CORE_FIELDS[:3]:
            key = 'min_' + field
            if key in f: rows = [r for r in rows if r[field] >= f[key]]
        if 'max_weekly_rent' in f: rows = [r for r in rows if r['weekly_rent'] <= f['max_weekly_rent']]
        if 'usyd_max_minutes' in f:
            from ..commute.matching import reference_matches
            rows=[r for r in rows if reference_matches(self.get(r['record_id']),f)]
        order = f['sort']
        rows.sort(key=lambda r: ((-r['weekly_rent'] if order == 'rent_desc' else -r['bedrooms'] if order == 'bedrooms_desc' else r['weekly_rent']), r['record_id']))
        result=[self.get(row['record_id']) for row in rows]
        if 'usyd_max_minutes' in f:
            from ..commute.snapshot import observation
            from ..commute.transit_options import TRANSIT,options
            mode=f.get('usyd_mode','public_transport')
            for row in result:
                route=observation(row,mode,max_transfers=f.get('usyd_max_transfers'))
                row['recommendation_mode']=mode
                if route:
                    row['commute_minutes']=route['duration_minutes']
                    if mode in TRANSIT:
                        row['usyd_commute']['selected_transit_route']={**deepcopy(route),'mode':mode}
                        row['usyd_commute']['transit_options']=options(row['usyd_commute'],selected=route)
        return result

    def search(self, filters=None, page=1, page_size=20):
        require(type(page) is int and page >= 1 and type(page_size) is int and 1 <= page_size <= 100,
                422, 'invalid_pagination', 'Page numbers must be positive integers, with at most 100 items per page.')
        f = self.filters(filters or {})
        rows = self.matching(f)
        return {'items': rows[(page-1)*page_size:page*page_size], 'total': len(rows), 'page': page,
                'page_size': page_size, 'filters': f, 'catalog': self.metadata()}


def register_catalog_routes(app, services):
    def search(suburb: str | None = None, min_bedrooms: int | None = None, min_bathrooms: int | None = None,
               min_car_spaces: int | None = None, max_weekly_rent: float | None = None,
               usyd_max_minutes: int | None = None, usyd_mode: str | None = None,
               usyd_arrival_time: str | None = None,usyd_travel_day: str | None = None,usyd_travel_date: str | None = None,usyd_max_transfers: int | None = None,case_id: str | None = None,
               sort: str = 'rent_asc', page: int = 1, page_size: int = 20):
        require(services.settings.catalog is not None, 503, 'real_catalog_unavailable', 'The live listing catalogue is unavailable.')
        catalog=services.settings.catalog
        values={'suburb':suburb, 'min_bedrooms':min_bedrooms,
            'min_bathrooms':min_bathrooms, 'min_car_spaces':min_car_spaces,
            'max_weekly_rent':max_weekly_rent,'usyd_max_minutes':usyd_max_minutes,'usyd_mode':usyd_mode,'usyd_arrival_time':usyd_arrival_time,'usyd_travel_day':usyd_travel_day,'usyd_travel_date':usyd_travel_date,'usyd_max_transfers':usyd_max_transfers, 'sort':sort}
        if case_id and usyd_max_minutes is not None:
            from ..commute.matching import matching_for_case
            require(type(page) is int and page>=1 and 1<=page_size<=100,422,'invalid_pagination','Invalid pagination parameters.')
            f=catalog.filters(values);rows=matching_for_case(services,case_id,f)
            return {'items':rows[(page-1)*page_size:page*page_size],'total':len(rows),'page':page,'page_size':page_size,'filters':f,'catalog':catalog.metadata()}
        return catalog.search(values,page,page_size)
    def detail(listing_id: str):
        require(services.settings.catalog is not None, 503, 'real_catalog_unavailable', 'The live listing catalogue is unavailable.')
        return services.settings.catalog.get(listing_id)
    app.get('/api/v1/listings')(search)
    app.get('/api/v1/listings/{listing_id}')(detail)
