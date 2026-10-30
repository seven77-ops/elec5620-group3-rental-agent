"""Curated evidence retrieval. No network, generated facts or inferred suitability."""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from ..bootstrap import ROOT

TOPICS = {'parks':'Parks and outdoors', 'food':'Dining', 'shopping':'Shopping', 'library':'Libraries',
          'community':'Community facilities', 'walkability':'Walking paths', 'quiet':'Quietness', 'safety':'Safety'}
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
                'match_reasons':[f'You prioritise {TOPICS[t]}; this area has relevant facilities evidence to review.' for t in matched],
                'evidence':evidence[:4],
                'notes':(['Area information is not yet compiled; living conditions cannot be established from this gap.'] if not evidence else [])+
                        (['Current inventory has no listings matching the comparable budget and property requirements. Only area information is shown here.'] if not group else [])})
        if not areas:
            items.sort(key=lambda a:(-len(a['matched_topics']),a['min_weekly_rent'] if a['min_weekly_rent'] is not None else float('inf'),a['suburb']))
        limitations=['Area information supports lifestyle preferences only; it does not establish a property quality, quietness, safety or availability.',
                     'Facility presence does not establish walking access from this property. Commute requirements need a separately checked actual route.',
                     'Inventory counts and weekly rent ranges come from the current listing snapshot, not whole-area market statistics. Background reports and resident opinions do not count as verified criteria.']
        if not budget_applied:
            limitations.append('The amount, period or scope does not establish a whole-property weekly budget. Budget filtering and occupant-based rent conversion were not applied.')
        criteria=[]
        if brief.get('budget_amount'):
            scope={'whole_property':'whole property ','per_room':'per room ','per_person':'per person '}.get(brief.get('budget_scope'),'rent scope unconfirmed ')
            period={'week':'weekly ','month':'monthly '}.get(brief.get('budget_period'),'budget period unconfirmed ')
            criteria.append(f"{scope}{period}limit AUD {brief['budget_amount']:g}")
        for key,label in (('min_bedrooms','bedrooms'),('min_bathrooms','bathrooms'),('min_car_spaces','parking spaces')):
            if key in brief:criteria.append(f"At least {brief[key]} {label}" if brief[key] else label+' unrestricted')
        return {'dataset_version':self.version,'fingerprint':self.fingerprint,'checked_at':today.isoformat(),
                'criteria_summary':' · '.join(criteria),
                'coverage':{'covered_suburbs':len({r['suburb'] for r in self.records}&set(catalog.suburbs)),
                            'catalog_suburbs':len(catalog.suburbs)},
                'priorities':[{'topic':t,'label':TOPICS[t]} for t in topics],
                'budget_applied':budget_applied,'areas':items[:limit],'limitations':limitations}
