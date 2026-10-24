"""Curated evidence retrieval. No network, generated facts or inferred suitability."""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from ..bootstrap import ROOT

TOPICS = {'parks':'公园与户外', 'food':'餐饮', 'shopping':'购物', 'library':'图书馆',
          'community':'社区设施', 'walkability':'散步步道', 'quiet':'安静', 'safety':'安全'}
PRIORITIES_SCHEMA = {'type':'array','maxItems':8,'uniqueItems':True,'items':{'enum':list(TOPICS)}}
DATA_PATH = ROOT / 'agent2/data/areas/sydney-evidence.json'


def sydney_today():
    return datetime.now(ZoneInfo('Australia/Sydney')).date()


def needs_review(report):
    """A saved snapshot cannot keep its current-reference badge forever."""
    for area in report.get('areas',[]):
        context=area.get('area_context',area)
        for record in context.get('evidence',[]):
            if record.get('freshness')!='current_reference':continue
            try:
                age=(sydney_today()-date.fromisoformat(record['source']['checked_at'])).days
                if not 0<=age<=record['review_after_days']:return True
            except (KeyError,TypeError,ValueError):return True
    return False


class AreaKnowledge:
    def __init__(self, path=DATA_PATH):
        raw=path.read_bytes()
        data=json.loads(raw)
        self.version=data['dataset_version']
        self.fingerprint=sha256(raw).hexdigest()
        self.records=data['records']
        identifiers=set()
        for record in self.records:
            source=record['source']; url=urlsplit(source['url'])
            if (record['evidence_id'] in identifiers or not record['summary'] or not record['limitation']
                    or not record['scope_label'] or not record['topics'] or set(record['topics'])-set(TOPICS)
                    or record['kind'] not in ('official','venue','media','resident_opinion')
                    or record['geographic_scope'] not in ('facility','nearby_facility','precinct','suburb','lga')
                    or url.scheme!='https' or not url.hostname or url.username or url.password):
                raise ValueError('Invalid area evidence')
            date.fromisoformat(source['checked_at'])
            for field in ('published_at','updated_at'):
                if source[field]:date.fromisoformat(source[field])
            identifiers.add(record['evidence_id'])

    def evidence(self, suburb, topics, today):
        result=[]
        for record in self.records:
            if record['suburb']!=suburb:continue
            item=deepcopy(record)
            age=(today-date.fromisoformat(item['source']['checked_at'])).days
            item['freshness']=('background' if item['kind'] in ('media','resident_opinion') else
                               'current_reference' if 0<=age<=item['review_after_days'] else 'needs_review')
            # Resident anecdotes and LGA averages never establish a suburb condition.
            item['supports_topics']=[t for t in topics if t in item['topics'] and t not in ('quiet','safety')
                and item['freshness']=='current_reference' and item['geographic_scope'] not in ('lga','nearby_facility')]
            result.append(item)
        result.sort(key=lambda r:(-len(r['supports_topics']), not bool(set(r['topics']) & set(topics)),r['evidence_id']))
        return result

    def advice(self, catalog, brief, areas=None, limit=4, today=None):
        today=today or sydney_today()
        topics=list(brief.get('lifestyle_priorities',[]))
        filters={k:brief[k] for k in ('min_bedrooms','min_bathrooms','min_car_spaces') if k in brief}
        budget_applied=(brief.get('budget_period')=='week' and brief.get('budget_scope')=='whole_property'
                        and type(brief.get('budget_amount')) in (int,float) and brief['budget_amount']>0)
        if budget_applied:filters['max_weekly_rent']=brief['budget_amount']
        rows=catalog.matching(filters)
        selected=list(areas) if areas else ([brief['suburb']] if brief.get('suburb') else sorted({r['suburb'] for r in rows}))
        items=[]
        for suburb in selected:
            group=[r for r in rows if r['suburb']==suburb]
            evidence=self.evidence(suburb,topics,today)
            matched=[topic for topic in topics if any(topic in e['supports_topics'] for e in evidence)]
            items.append({'suburb':suburb, 'matching_count':len(group),
                'min_weekly_rent':min((r['weekly_rent'] for r in group),default=None),
                'max_weekly_rent':max((r['weekly_rent'] for r in group),default=None),
                'matched_topics':matched, 'missing_topics':[t for t in topics if t not in matched],
                'match_reasons':[f'你看重{TOPICS[t]}，本区有相关的设施资料可供核对。' for t in matched],
                'evidence':evidence[:4],
                'notes':(['区域资料尚未整理，不能据此判断生活条件。'] if not evidence else [])+
                        (['当前库存没有符合本次可比较预算及房型条件的房源；这里只提供区域资料。'] if not group else [])})
        if not areas:
            items.sort(key=lambda a:(-len(a['matched_topics']),a['min_weekly_rent'] if a['min_weekly_rent'] is not None else float('inf'),a['suburb']))
        limitations=['区域资料只用于生活偏好参考，不代表具体房源的质量、安静程度、安全或可租状态。',
                     '设施存在不代表离这套房步行可达；通勤只认单独查询的实际路线，尚未查询时不能判定满足。',
                     '库存数量和周租范围来自当前房源快照，不是全区域市场统计；背景报道和住户观点不计入已核对的条件。']
        if not budget_applied:
            limitations.append('预算金额、周期或计价对象未明确为整套每周，未用预算筛除，也未按人数乘除租金。')
        criteria=[]
        if brief.get('budget_amount'):
            scope={'whole_property':'整套','per_room':'每间','per_person':'每人'}.get(brief.get('budget_scope'),'计价对象待确认')
            period={'week':'每周','month':'每月'}.get(brief.get('budget_period'),'预算周期待确认')
            criteria.append(f"{scope}{period}上限 AUD {brief['budget_amount']:g}")
        for key,label in (('min_bedrooms','卧'),('min_bathrooms','卫'),('min_car_spaces','车位')):
            if key in brief:criteria.append(f"至少{brief[key]}{label}" if brief[key] else label+'不限')
        return {'dataset_version':self.version,'fingerprint':self.fingerprint,'checked_at':today.isoformat(),
                'criteria_summary':' · '.join(criteria),
                'coverage':{'covered_suburbs':len({r['suburb'] for r in self.records}&set(catalog.suburbs)),
                            'catalog_suburbs':len(catalog.suburbs)},
                'priorities':[{'topic':t,'label':TOPICS[t]} for t in topics],
                'budget_applied':budget_applied,'areas':items[:limit],'limitations':limitations}
