"""Normalize AER public product facts without changing tariff blocks or GST basis."""
from copy import deepcopy
from decimal import Decimal
from urllib.parse import quote


def gross(value):
    return float((Decimal(str(value))*Decimal('1.1')).quantize(Decimal('.00000001')))


def energy_plan(detail, observed_at):
    category=detail['fuelType'].lower();unit='kWh' if category=='electricity' else 'MJ'
    contract=detail[category+'Contract'];brand=detail['brand'];identifier=detail['planId']
    periods=[]
    for raw in contract.get('tariffPeriod',[]):
        p={'name':raw['displayName'],'start_date':raw['startDate'],'end_date':raw['endDate'],'rates':[]}
        if raw.get('dailySupplyCharge') is not None:p['daily_supply_aud']=gross(raw['dailySupplyCharge'])
        for rate_type,group in [('singleRate',raw.get('singleRate'))]+[('timeOfUseRates',x) for x in raw.get('timeOfUseRates',[])]:
            if not group:continue
            p['rates'].append({'name':group.get('displayName',rate_type),'kind':group.get('type','SINGLE_RATE'),
                'block_period':group.get('period'),'time_windows':deepcopy(group.get('timeOfUse',[])),
                'blocks':[{'unit_price_aud':gross(r['unitPrice']), 'volume':r.get('volume'),
                    'unit':r.get('measureUnit',unit).replace('KWH','kWh')} for r in group.get('rates',[])]})
        periods.append(p)
    conditions=['NSW residential. A matching postcode does not verify the building or meter. Check distribution network, meter and network tariff.',
                'Displayed usage and daily supply charges include 10% GST. Baseline rates exclude discounts, cashback and rebates.',
                'Rates: '+('Fixed; check the fixed period and exceptions.' if contract.get('isFixed') else 'Variable; the provider may change them with notice under its terms.')]
    if 'New' in detail['displayName'] or 'new' in detail['displayName']:conditions.append('Only for eligible new or moving customers.')
    if 'CONT_LOAD' in contract['pricingModel']:conditions.append('Includes controlled-load rates. Dedicated circuits such as hot water are charged separately; general usage rates alone cannot establish the total.')
    if contract.get('benefitPeriod'):conditions.append('Benefit period: '+contract['benefitPeriod'])
    discounts=[]
    for discount in contract.get('discounts',[]):
        method=discount.get('methodUType');v=discount.get(method,{})
        discounts.append({'name':discount.get('displayName',discount['type']),'type':discount['type'],'method':method,'value':v})
    controlled=[]
    for raw in contract.get('controlledLoad',[]):
        groups=([raw['singleRate']] if raw.get('singleRate') else raw.get('timeOfUseRates',[]))
        for group in groups:
            controlled.append({'name':raw.get('displayName',group.get('displayName','Controlled load')),
                'block_period':group.get('period'),'time_windows':deepcopy(group.get('timeOfUse',[])),
                'daily_supply_aud':gross(group['dailySupplyCharge']) if group.get('dailySupplyCharge') is not None else None,
                'blocks':[{'unit_price_aud':gross(r['unitPrice']),'volume':r.get('volume'),'unit':r.get('measureUnit',unit)} for r in group.get('rates',[])]})
    return {'id':'aer:'+identifier,'provider_id':brand,'category':category,'name':detail['displayName'],
        'external_plan_id':identifier,'source_url':'https://www.energymadeeasy.gov.au/plan?id='+quote(identifier.split('@')[0]),
        'data_source_url':f'https://cdr.energymadeeasy.gov.au/{brand}/cds-au/v1/energy/plans/'+quote(identifier,safe=''),
        'source_version':3,'observed_at':observed_at,'source_updated_at':detail.get('lastUpdated'),
        'valid_from':detail.get('effectiveFrom'),'valid_to':detail.get('effectiveTo'),'currency':'AUD',
        'geography':deepcopy(detail['geography']),'conditions':conditions,
        'pricing':{'model':contract['pricingModel'],'unit':unit,'gst_basis':'inclusive_10_percent',
            'raw_gst_basis':'exclusive','raw_tariff_periods':deepcopy(contract.get('tariffPeriod',[])),
            'tariff_periods':periods,'raw_controlled_load':deepcopy(contract.get('controlledLoad',[])),'controlled_load':controlled,
            'discounts':discounts,'incentives':[{'name':x.get('displayName'),'category':x.get('category')} for x in contract.get('incentives',[])],
            'fees':[{'type':x['type'],'amount':x.get('amount'),'term':x.get('term'),'description':x.get('description')} for x in contract.get('fees',[])],
            'is_fixed':contract.get('isFixed'),'term_type':contract.get('termType'),'benefit_period':contract.get('benefitPeriod'),
            'time_zone':contract.get('timeZone'),'meter_types':contract.get('meterTypes',[]),'bill_frequency':contract.get('billFrequency',[]),
            'payment_options':contract.get('paymentOption',[]),'cooling_off_days':contract.get('coolingOffDays'),
            'eligibility':deepcopy(contract.get('eligibility',[])),
            'terms_url':{'agl':'https://www.agl.com.au/','origin':'https://www.originenergy.com.au/electricity-gas/','energyaustralia':'https://www.energyaustralia.com.au/'}[brand]}}
