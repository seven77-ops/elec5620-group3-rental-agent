"""Offline historical rent reference, independent of the recommendation score."""
from copy import deepcopy
import json
import math
from pathlib import Path
from ..bootstrap import ROOT
from ..common import require


def numeric(value, minimum, maximum):
    return type(value) in (int, float) and minimum <= value <= maximum and math.isfinite(value)


class MarketData:
    def __init__(self, path=None):
        self.data = json.loads(Path(path or ROOT / 'agent2/data/market/nsw-usyd-2026.json').read_text())

    def coverage(self):
        return {key: deepcopy(self.data[key]) for key in ('postcodes', 'bedrooms', 'dwelling_type', 'rent_scope')}

    def lookup(self, postcode, bedrooms, rent_scope, weekly_rent=None):
        require(isinstance(postcode, str) and len(postcode) == 4 and postcode.isascii() and postcode.isdigit(),
                422, 'invalid_input', 'Postcode must contain four digits.')
        require(type(bedrooms) is int and 0 <= bedrooms <= 20, 422, 'invalid_input', 'Bedrooms must be an integer.')
        require(rent_scope in ('whole_property', 'per_room', 'per_person'), 422, 'invalid_input', 'Choose the rent scope.')
        require(weekly_rent is None or numeric(weekly_rent, 0, 100_000), 422, 'invalid_input', 'Weekly rent must be a valid nonnegative amount.')
        result = {'status': 'unavailable', 'postcode': postcode, 'bedrooms': bedrooms,
                  'rent_scope': rent_scope, 'weekly_rent': weekly_rent, 'dwelling_type': 'flat_unit',
                  'benchmarks': [], 'coverage': self.coverage(),
                  'limitations': ['Historical rent reference only; not an individual property valuation or signing recommendation.',
                                  'Grouped by postcode and one- or two-bedroom apartments; not applicable to shared rooms or per-person prices.',
                                  'Does not control for size, furnishings, floor or bills. Registration month is not move-in month.',
                                  'The two periods use different samples and methods; they cannot directly establish rent changes.']}
        if rent_scope != 'whole_property':
            result['status'] = 'scope_mismatch'
            return result
        sources = {s['id']: s for s in self.data['sources']}
        for cohort in self.data['cohorts']:
            if cohort['postcode'] == postcode and cohort['bedrooms'] == bedrooms:
                row = deepcopy(cohort)
                row['source_url'] = sources[row['source_id']]['url']
                row['difference_aud'] = None if weekly_rent is None else round(weekly_rent - row['median'], 2)
                row['difference_percent'] = None if weekly_rent is None else round((weekly_rent / row['median'] - 1) * 100, 4)
                result['benchmarks'].append(row)
        if result['benchmarks']:
            result['status'] = 'available'
        return result
