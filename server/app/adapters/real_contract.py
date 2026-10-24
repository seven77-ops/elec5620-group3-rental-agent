"""Documentary comparisons against frozen, explicitly unverified real sources."""
from copy import deepcopy
import re
import unicodedata


def real_context(saved, review):
    baseline=deepcopy(saved.get('real_context'))
    if baseline is None: return None
    fields=review['fields']; ad=baseline['selection']['listing_snapshot']
    followup=baseline['followup']; facts=followup['facts']; checks=[]
    def add(key,label,source,value,other,status=None):
        if status is None:
            status='missing' if value is None or other in (None,'') else ('match' if value==other else 'different')
        checks.append({'key':key,'label':label,'source':source,'reference_value':other,
            'contract_value':value,'status':status})
    def value(key): return fields.get(key,{}).get('value')
    def norm(v): return re.sub(r'[^\w]','',unicodedata.normalize('NFKC',str(v)).casefold())
    address=value('address')
    add('address','房屋地址','广告快照',address,ad['address'],
        'missing' if not address else ('match' if norm(address)==norm(ad['address']) else 'different'))
    rent=value('rent_amount'); period=value('rent_period'); scope=value('rent_scope'); currency=value('currency')
    # Unknown advertised scope is never filled from user notes or contract extraction.
    compatible=period=='week' and currency=='AUD' and scope==ad.get('rent_scope') and scope is not None
    add('advertised_rent','广告周租（AUD）','广告快照',rent,ad['weekly_rent'],
        None if compatible else 'basis_unknown')
    if followup['version']:
        comparable=(period==facts['rent_period'] and period!='unknown' and scope==facts['rent_scope']
                    and scope not in (None,'unknown') and currency=='AUD')
        add('recorded_rent','补充记录中的租金（AUD）','用户记录 v'+str(followup['version']),rent,facts['rent_amount'],
            None if comparable and facts['rent_amount'] is not None else 'basis_unknown')
        for key,label in (('start_date','起租日期'),('end_date','结束日期'),('landlord','出租方'),('bond','押金（AUD）')):
            if facts[key] not in (None,''):
                status = None
                if key == 'bond':
                    # Bond amounts may use a different currency from the rent line.
                    quote = fields.get('bond', {}).get('evidence') or {}
                    quote = quote.get('quote') or ''
                    explicit_aud = bool(re.search(r'\bAUD\b', quote, re.I))
                    other_currency = bool(re.search(r'\b(?:USD|EUR|GBP|NZD|CAD|SGD|CNY)\b', quote, re.I))
                    if currency != 'AUD' or not explicit_aud or other_currency:
                        status = 'basis_unknown'
                add('recorded_'+key,label,'用户记录 v'+str(followup['version']),value(key),facts[key],status)
    baseline['checks']=checks
    return baseline
