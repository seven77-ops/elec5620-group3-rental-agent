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
                422, 'invalid_input', '邮编须为四位数字。')
        require(type(bedrooms) is int and 0 <= bedrooms <= 20, 422, 'invalid_input', '卧室数须为整数。')
        require(rent_scope in ('whole_property', 'per_room', 'per_person'), 422, 'invalid_input', '请选择计价对象。')
        require(weekly_rent is None or numeric(weekly_rent, 0, 100_000), 422, 'invalid_input', '周租须为有效非负金额。')
        result = {'status': 'unavailable', 'postcode': postcode, 'bedrooms': bedrooms,
                  'rent_scope': rent_scope, 'weekly_rent': weekly_rent, 'dwelling_type': 'flat_unit',
                  'benchmarks': [], 'coverage': self.coverage(),
                  'limitations': ['仅供历史租金参考，不是单套房产估值或签约建议。',
                                  '按邮区和一卧/两卧公寓分类，不适用于合租单间或按人报价。',
                                  '未控制面积、家具、楼层和账单；登记月份不是入住月份。',
                                  '两个期间的样本和方法不同，不能直接据此判断租金涨跌。']}
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
