"""Versioned official utility-plan observations in a separate local SQLite database."""
from copy import deepcopy
from contextlib import closing
from datetime import date, datetime, time
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SEED=Path(__file__).with_name('data')/'utility-plans.json'
CATEGORIES={'electricity','gas','internet','water'}
HOSTS={'www.telstra.com.au','www.optus.com.au','www.tpg.com.au','www.aussiebroadband.com.au',
       'www.superloop.com','www.sydneywater.com.au','www.energymadeeasy.gov.au'}
MODELS={'SINGLE_RATE':'单一费率','SINGLE_RATE_CONT_LOAD':'单一费率＋受控负荷',
        'TIME_OF_USE':'分时费率','TIME_OF_USE_CONT_LOAD':'分时费率＋受控负荷','FLEXIBLE_CONT_LOAD':'灵活费率＋受控负荷'}
PERIODS={'P1D':'每天','P1M':'每月','P3M':'每季度','P1Y':'每年'}


def day(value=None):
    if value is None:return datetime.now(ZoneInfo('Australia/Sydney')).date()
    if isinstance(value,datetime):return value.date()
    return value if isinstance(value,date) else date.fromisoformat(str(value)[:10])


def instant(value=None):
    zone=ZoneInfo('Australia/Sydney')
    if value is None:return datetime.now(zone)
    if isinstance(value,datetime):return value.replace(tzinfo=zone) if value.tzinfo is None else value
    parsed=datetime.fromisoformat(str(value).replace('Z','+00:00')) if 'T' in str(value) else datetime.combine(day(value),time.min)
    return parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed


def amount(value):
    return f'{float(value):.4f}'.rstrip('0').rstrip('.')


def valid_seed(seed):
    if not isinstance(seed,dict) or seed.get('schema_version')!=1 or not isinstance(seed.get('plans'),list):raise ValueError('Invalid utility plan snapshot')
    day(seed['checked_on']);seen=set()
    for p in seed['plans']:
        if not p.get('id') or p['id'] in seen or p.get('category') not in CATEGORIES or not p.get('provider_id') or p.get('currency')!='AUD':raise ValueError('Invalid utility plan identity')
        seen.add(p['id']);u=urlsplit(p['source_url'])
        if u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password:raise ValueError('Unsafe utility source URL')
        day(p['observed_at'])
        for field in ('valid_from','valid_to'):
            if p.get(field):day(p[field])
        if not p.get('name') or not isinstance(p.get('pricing'),dict) or not isinstance(p.get('conditions'),list):raise ValueError('Invalid utility plan facts')
        if p['category']=='internet':
            v=p['pricing']
            for key in ('monthly_aud','download_mbps','upload_mbps'):
                if type(v.get(key)) not in (int,float) or not 0<=v[key]<100000:raise ValueError('Invalid internet price/speed')
            if v.get('intro_monthly_aud') is not None and (type(v['intro_monthly_aud']) not in (int,float) or v['intro_monthly_aud']<0 or type(v.get('intro_months')) is not int or not 1<=v['intro_months']<=24):raise ValueError('Invalid introductory price')
            if v.get('offer_ends_on'):day(v['offer_ends_on'])
        elif p['category'] in ('electricity','gas'):
            if not p['pricing'].get('tariff_periods') or p['pricing'].get('raw_gst_basis')!='exclusive':raise ValueError('Missing energy tariff evidence')
    return seed


class UtilityPlanCatalog:
    def __init__(self,database,seed_path=None):
        self.database=Path(database).resolve();self.database.parent.mkdir(parents=True,exist_ok=True)
        seed=valid_seed(json.loads(Path(seed_path or SEED).read_text()))
        body=json.dumps(seed,sort_keys=True,ensure_ascii=False,allow_nan=False)
        self.fingerprint=hashlib.sha256(body.encode()).hexdigest();self.checked_on=seed['checked_on'];self.freshness_days=seed.get('freshness_days',30)
        with closing(sqlite3.connect(self.database,timeout=30)) as db, db:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('CREATE TABLE IF NOT EXISTS utility_snapshots (id TEXT PRIMARY KEY, checked_on TEXT NOT NULL, metadata TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS utility_plans (snapshot_id TEXT NOT NULL, id TEXT NOT NULL, provider_id TEXT NOT NULL, category TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(snapshot_id,id), FOREIGN KEY(snapshot_id) REFERENCES utility_snapshots(id))')
            db.execute('CREATE INDEX IF NOT EXISTS utility_plan_lookup ON utility_plans(snapshot_id,category,provider_id)')
            if not db.execute('SELECT 1 FROM utility_snapshots WHERE id=?',(self.fingerprint,)).fetchone():
                db.execute('INSERT INTO utility_snapshots VALUES (?,?,?)',(self.fingerprint,self.checked_on,json.dumps({k:v for k,v in seed.items() if k!='plans'},ensure_ascii=False)))
                db.executemany('INSERT INTO utility_plans VALUES (?,?,?,?,?)',[(self.fingerprint,p['id'],p['provider_id'],p['category'],json.dumps(p,ensure_ascii=False,allow_nan=False)) for p in seed['plans']])

    def search(self,category=None,provider_id=None,postcode=None,on=None,include_unavailable=False):
        if category is not None and category not in CATEGORIES:return []
        query='SELECT body FROM utility_plans WHERE snapshot_id=?';args=[self.fingerprint]
        for field,value in (('category',category),('provider_id',provider_id)):
            if value is not None:query+=' AND '+field+'=?';args.append(value)
        with closing(sqlite3.connect(self.database.as_uri()+'?mode=ro',uri=True,timeout=30)) as db:
            rows=[json.loads(r[0]) for r in db.execute(query,args)]
        today=day(on);at=instant(on);result=[]
        for p in rows:
            p['status']='current';observed=day(p['observed_at'])
            if p.get('valid_from') and (instant(p['valid_from'])>at if 'T' in p['valid_from'] else day(p['valid_from'])>today):p['status']='not_yet_effective'
            elif p.get('valid_to') and (instant(p['valid_to'])<at if 'T' in p['valid_to'] else day(p['valid_to'])<today):p['status']='expired'
            elif (today-observed).days>self.freshness_days or today<observed:p['status']='stale'
            if not include_unavailable and p['status']!='current':continue
            postcodes=p.get('geography',{}).get('includedPostcodes',[])
            if postcode and postcodes and str(postcode) not in postcodes:continue
            p['availability']='address_unconfirmed'
            p['network_label']=' / '.join(p.get('geography',{}).get('distributors',[]))
            decorate(p,today);result.append(p)
        result.sort(key=lambda p:(p['category'],'CONT_LOAD' in p['pricing'].get('model',''),'TIME_OF_USE' in p['pricing'].get('model',''),p['name'],p['id']))
        return result

    def summary(self):
        rows=self.search(include_unavailable=True)
        return {'checked_on':self.checked_on,'fingerprint':self.fingerprint,'total':len(rows),
                'current':sum(p['status']=='current' for p in rows),'freshness_days':self.freshness_days,
                'scope':'所收录的官方套餐快照；未覆盖全市场，未核实具体地址，非实时报价。'}


def decorate(p,today):
    v=p['pricing'];lines=[]
    if p['category']=='internet':
        promo=v.get('intro_monthly_aud') is not None and (not v.get('offer_ends_on') or day(v['offer_ends_on'])>=today)
        p['promotion_active']=promo;p['effective_monthly_aud']=v['intro_monthly_aud'] if promo else v['monthly_aud']
        months=min(v.get('intro_months',0),12) if promo else 0
        p['first_year_base_cost_aud']=float(Decimal(str(p['effective_monthly_aud']))*months+Decimal(str(v['monthly_aud']))*(12-months))
        if promo:lines.append(f"前{v['intro_months']}个月 AUD {amount(v['intro_monthly_aud'])}/月；之后 AUD {amount(v['monthly_aud'])}/月")
        else:lines.append(f"AUD {amount(v['monthly_aud'])}/月"+('；原促销已结束' if v.get('intro_monthly_aud') is not None else ''))
        lines += [f"典型晚高峰下载/上传 {amount(v['download_mbps'])}/{amount(v['upload_mbps'])} Mbps · 无限流量",
                  f"首12个月基础月租合计 AUD {amount(p['first_year_base_cost_aud'])}；不含路由器、运费及特殊安装"]
        if v.get('promo_code') and promo:lines.append('优惠码：'+v['promo_code'])
        if v.get('offer_ends_on') and promo:lines.append('优惠申请截止：'+v['offer_ends_on'])
        lines.append(v.get('hardware_notes','设备条件另核。'))
    elif p['category'] in ('electricity','gas'):
        unit=v['unit'];lines.append(MODELS.get(v['model'],v['model'])+'；以下为含GST的优惠前基准费率')
        for period in v['tariff_periods']:
            label=f"{period['start_date']}至{period['end_date']}"
            if period.get('daily_supply_aud') is not None:lines.append(f"{label}：固定费 AUD {amount(period['daily_supply_aud'])}/天")
            for rate in period['rates']:
                chunks=[]
                for index,b in enumerate(rate['blocks']):
                    block=f"第{index+1}档 {amount(b['volume'])}{unit}" if b.get('volume') is not None else ('其余用量' if len(rate['blocks'])>1 else rate['name'])
                    chunks.append(f"{block} {amount(b['unit_price_aud']*100)}澳分/{unit}")
                times='；'.join('/'.join(t['days'])+' '+t['startTime']+'–'+t['endTime'] for t in rate.get('time_windows',[]))
                lines.append('；'.join(chunks)+('（阶梯周期：'+PERIODS.get(rate.get('block_period'),str(rate.get('block_period')))+'）' if len(chunks)>1 else '')+(' · '+times if times else ''))
        for load in v.get('controlled_load',[]):
            charge='；'.join(f"{amount(b['unit_price_aud']*100)}澳分/{unit}"+(f"（该档{amount(b['volume'])}{unit}）" if b.get('volume') is not None else '') for b in load['blocks'])
            supply=f"；另加固定费 AUD {amount(load['daily_supply_aud'])}/天" if load.get('daily_supply_aud') is not None else ''
            lines.append('受控负荷 '+load['name']+'：'+charge+supply)
        for d in v.get('discounts',[]):
            rate=d.get('value',{}).get('rate');lines.append(d['name']+(f" {amount(float(rate)*100)}%" if rate is not None else '')+'；适用项目及条件须核对，未从上述基准价重复扣除')
        for i in v.get('incentives',[]):
            if i.get('name'):lines.append('可能的优惠：'+i['name']+'；仅在满足条款时适用，未抵扣比较金额')
    else:
        lines=[f"普通用水 AUD {amount(v['usage_aud_per_kl'])}/kL；旱情价 AUD {amount(v['drought_usage_aud_per_kl'])}/kL",
               f"再生水 AUD {amount(v['recycled_aud_per_kl'])}/kL（适用物业）",
               f"房东固定费用参考：供水 AUD {amount(v['water_service_aud_per_quarter'])}/季度；污水 AUD {amount(v['wastewater_aud_per_quarter'])}/季度",
               '季度固定费示例按最长92天计，实际按天计算；雨水费按区域和房型另计。',v['drought_condition']]
    p['price_summary']=lines[0] if lines else '费率需核对';p['pricing_lines']=lines
    return p


def public_plan(plan):
    result=deepcopy(plan)
    for key in ('raw_tariff_periods','raw_controlled_load'):
        result['pricing'].pop(key,None)
    return result
