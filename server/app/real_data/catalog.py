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
FILTER_FIELDS = ('suburb', 'min_bedrooms', 'min_bathrooms', 'min_car_spaces', 'max_weekly_rent', 'sort')


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
                row['bedroom_label'] = '1（开放式）'
            else:
                row['bedroom_label'] = f"{row['bedrooms']:g}"
        self.suburbs = sorted({r['suburb'] for r in rows})
        self.as_of = max(row['captured_at'] for row in rows)
        self.fingerprint = hashlib.sha256(json.dumps(list(self._rows.values()), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self._photos = load_photos(Path(photos_path) if photos_path is not None else self.path.with_name('photos.json'), self._rows)

    def metadata(self):
        return {'data_mode': 'real_listings', 'total': len(self._rows), 'suburb_count': len(self.suburbs),
                'suburbs': list(self.suburbs), 'captured_at': self.as_of, 'fingerprint': self.fingerprint,
                'core_fields': list(CORE_FIELDS), 'availability_verified': False,
                'detail_read_count': sum(r['source_observation']['detail_read'] for r in self._rows.values()),
                'open_plan_as_one_count': sum(r['bedroom_count_basis']=='open_plan_as_one' for r in self._rows.values()),
                'photo_listing_count': len(self._photos),
                'photo_count': sum(len(photos) for photos in self._photos.values())}

    def get(self, identifier):
        require(identifier in self._rows, 404, 'listing_not_found', '未找到这条真实房源广告。')
        return {**deepcopy(self._rows[identifier]), 'listing_id': identifier, 'commute_minutes': None,
                'photos': deepcopy(self._photos.get(identifier, []))}

    def filters(self, values):
        require(isinstance(values, dict) and not set(values) - set(FILTER_FIELDS), 422, 'invalid_filters', '房源筛选字段无效。')
        result = {k:v for k,v in values.items() if v is not None}
        if 'suburb' in result:
            require(isinstance(result['suburb'], str) and result['suburb'] in self.suburbs, 422, 'invalid_filters', '请选择房源库中的区域。')
        for key in ('min_bedrooms', 'min_bathrooms', 'min_car_spaces'):
            if key in result:
                require(type(result[key]) is int and 0 <= result[key] <= 100, 422, 'invalid_filters', '房间和车位数量须为0至100的整数。')
        if 'max_weekly_rent' in result:
            amount = result['max_weekly_rent']
            require(type(amount) in (int, float) and math.isfinite(amount) and 0 <= amount <= 1000000000000,
                    422, 'invalid_filters', '最高广告周租须为0至1000000000000的有效数字。')
        result.setdefault('sort', 'rent_asc')
        require(result['sort'] in ('rent_asc', 'rent_desc', 'bedrooms_desc'), 422, 'invalid_filters', '请选择支持的排序方式。')
        return result

    def matching(self, filters):
        f = self.filters(filters)
        rows = list(self._rows.values())
        if 'suburb' in f: rows = [r for r in rows if r['suburb'] == f['suburb']]
        for field in CORE_FIELDS[:3]:
            key = 'min_' + field
            if key in f: rows = [r for r in rows if r[field] >= f[key]]
        if 'max_weekly_rent' in f: rows = [r for r in rows if r['weekly_rent'] <= f['max_weekly_rent']]
        order = f['sort']
        rows.sort(key=lambda r: ((-r['weekly_rent'] if order == 'rent_desc' else -r['bedrooms'] if order == 'bedrooms_desc' else r['weekly_rent']), r['record_id']))
        return [self.get(row['record_id']) for row in rows]

    def search(self, filters=None, page=1, page_size=20):
        require(type(page) is int and page >= 1 and type(page_size) is int and 1 <= page_size <= 100,
                422, 'invalid_pagination', '页码须为正整数，每页最多100条。')
        f = self.filters(filters or {})
        rows = self.matching(f)
        return {'items': rows[(page-1)*page_size:page*page_size], 'total': len(rows), 'page': page,
                'page_size': page_size, 'filters': f, 'catalog': self.metadata()}


def register_catalog_routes(app, services):
    def search(suburb: str | None = None, min_bedrooms: int | None = None, min_bathrooms: int | None = None,
               min_car_spaces: int | None = None, max_weekly_rent: float | None = None,
               sort: str = 'rent_asc', page: int = 1, page_size: int = 20):
        require(services.settings.catalog is not None, 503, 'real_catalog_unavailable', '真实房源库未加载。')
        return services.settings.catalog.search({'suburb':suburb, 'min_bedrooms':min_bedrooms,
            'min_bathrooms':min_bathrooms, 'min_car_spaces':min_car_spaces,
            'max_weekly_rent':max_weekly_rent, 'sort':sort}, page, page_size)
    def detail(listing_id: str):
        require(services.settings.catalog is not None, 503, 'real_catalog_unavailable', '真实房源库未加载。')
        return services.settings.catalog.get(listing_id)
    app.get('/api/v1/listings')(search)
    app.get('/api/v1/listings/{listing_id}')(detail)
