"""Source-grounded utility answers. Monetary facts come exclusively from SQLite."""
from copy import deepcopy
import re
from .utility_catalog import amount, public_plan

LABELS={'internet':'Internet','electricity':'Electricity','gas':'Gas','water':'Water'}
PROVIDERS={'agl':('agl',),'origin':('origin',),'energyaustralia':('energyaustralia','energy australia'),
    'telstra':('telstra',),'optus':('optus',),'tpg':('tpg',),'aussie-broadband':('aussie broadband','aussie'),
    'superloop':('superloop',),'sydney-water':('sydney water',)}


def explicit_number(text,patterns):
    for pattern in patterns:
        match=re.search(pattern,text,re.I)
        if match:
            value=float(match.group(1))
            if 0<=value<=100000:return value
    return None


def advise(catalog,message,category=None,profile=None,on=None):
    profile=profile or {};folded=message.casefold()
    if category not in LABELS:
        category=next((c for c,words in [('internet',('网络','网费','宽带','nbn','internet','wifi','wi-fi')),
                ('water',('水费','供水','water')),('gas',('燃气','天然气','gas')),('electricity',('电费','电力','electricity'))]
                if any(w in folded for w in words)),None)
    named=[provider for provider,names in PROVIDERS.items() if any(re.search(r'(?<![a-z])'+re.escape(n)+r'(?![a-z])',folded) for n in names)]
    if category is None and named and all(p in ('telstra','optus','tpg','aussie-broadband','superloop') for p in named):category='internet'
    if category is None and named==['sydney-water']:category='water'
    postcode_match=re.search(r'(?:邮编|postcode)\s*[:：]?\s*(\d{4})(?!\d)',message,re.I)
    postcode=postcode_match.group(1) if postcode_match else profile.get('postcode') or None
    rows=catalog.search(category=category,postcode=postcode,on=on)
    if named:rows=[p for p in rows if p['provider_id'] in named]
    budget=speed=None
    if category=='internet':
        budget=explicit_number(message,[r'(?:每(?:个)?月|一个月|月租|月预算|月费)\s*(?:预算|不超过|最多|低于|上限|控制在|在|为|是|[:：])?\s*(?:AUD\s*|\$)?(\d+(?:\.\d+)?)',r'(\d+(?:\.\d+)?)\s*(?:澳元|元|刀)?\s*(?:以内|以下|左右)?\s*[/／]\s*月',r'(\d+(?:\.\d+)?)\s*(?:澳元|元|刀)?\s*(?:以内|以下|左右)?\s*(?:一个月|每个月|每月)'])
        if budget is None and not re.search(r'每年|一年|每周|一周|总预算|总共|半年',message):
            budget=explicit_number(message,[r'预算\s*(?:是|为|不超过|最多|上限)?\s*(?:AUD\s*|\$)?(\d+(?:\.\d+)?)',r'(\d+(?:\.\d+)?)\s*(?:澳元|元|刀)?\s*(?:以内|以下)'])
        speed=explicit_number(message,[r'(\d+(?:\.\d+)?)\s*(?:Mbps|兆(?:宽带|网络|网速))'])
        asks_nbn=bool(re.search(r'nbn|光纤|固定宽带',folded))
        rejects_5g=bool(re.search(r'(?:不要|不用|不考虑|排除|非)\s*5g',folded))
        asks_5g='5g' in folded and not rejects_5g
        if rejects_5g or (asks_nbn and not asks_5g):rows=[p for p in rows if '5G' not in p['pricing'].get('technology',[])]
        elif asks_5g and not asks_nbn:rows=[p for p in rows if '5G' in p['pricing'].get('technology',[])]
        if budget is not None:rows=[p for p in rows if p['pricing']['monthly_aud']<=budget]
        if speed is not None:rows=[p for p in rows if p['pricing']['download_mbps']>=speed]
        rows.sort(key=lambda p:(p['first_year_base_cost_aud'],p['pricing']['monthly_aud'],-p['pricing']['download_mbps'],p['id']))
        # Compare the best matching observed offer per provider, avoiding three near-identical cards.
        picked=[];seen=set()
        for p in rows:
            if p['provider_id'] not in seen:picked.append(p);seen.add(p['provider_id'])
        chosen=picked[:3]
        if chosen:
            content='These included internet plans are ranked by their first 12 months of base fees. They are not a market-wide cheapest-price comparison and address availability is unverified.'
            if budget is not None:content+=f' The AUD {amount(budget)} monthly budget is checked against the ongoing monthly fee after promotions.'
            if speed is not None:content+=f' Download reference at least {amount(speed)} Mbps; check your home access technology.'
            for p in chosen:content+='\n'+p['name']+': '+p['price_summary']+f"; first-year base fees AUD {amount(p['first_year_base_cost_aud'])}."
            content+='\nFirst-year totals exclude router, delivery, special installation and early exit costs. Check promotional eligibility, codes and hardware retention terms in plan details. Add household size, speed and budget to narrow the choices.'
        else:content='No current included internet plan meets both budget and speed requirements. Budget uses ongoing monthly fees, not introductory prices. Adjust budget or speed, or check official sites for other plans.'
    elif category=='water':
        chosen=rows[:1]
        content='Sydney Water service is determined by the property address; another retailer cannot be freely selected.'
        for p in chosen:content+='\n'+'\n'.join(p['pricing_lines'])
        content+='\nIn private rentals, fixed water and wastewater ownership charges are usually the landlord responsibility. Passing usage charges to a tenant requires conditions including separate metering, water efficiency and billing evidence. Tenants usually do not open a separate Sydney Water account.'
        if chosen:content+=' See the NSW official guidance below for payment responsibilities.'
        if not chosen:content+=' No current water-price snapshot is available. Check amounts on the Sydney Water website.'
    else:
        # Energy comparisons need the actual meter tariff and usage profile; do not invent a monthly bill.
        ordered=sorted(rows,key=lambda p:('CONT_LOAD' in p['pricing'].get('model',''),'TIME_OF_USE' in p['pricing'].get('model',''),p['name'],p['id']))
        chosen=[];seen=set()
        for p in ordered:
            key=(p['provider_id'],p['category'],p['name'])
            if key not in seen:chosen.append(p);seen.add(key)
            if len(chosen)>=6:break
        content='Electricity and gas usually combine daily supply and usage charges. Time-of-use electricity depends on usage times and gas may use blocks. Without billed usage and meter tariffs, unit prices alone cannot establish the cheapest provider.'
        if not category and not named:
            # Overview shows one representative offer per category/provider, including broadband and water.
            chosen=[];seen=set()
            for p in rows:
                key=(p['provider_id'],p['category'])
                if key not in seen:chosen.append(p);seen.add(key)
            content='Official internet, electricity, gas and Sydney Water plans and pricing references are included. Try asking for internet plans under AUD 80 per month, AGL electricity rates, or who pays water charges.'
        elif chosen:
            for p in chosen:content+='\n'+p['name']+' ('+p['network_label']+'): '+';'.join(p['pricing_lines'][:3])
            content+='\nEnergy prices shown are baseline rates including GST before discounts. Check discounts, cashback, controlled load and connection costs separately. Compare using postcode, billed usage and meter tariff; distribution-network coverage does not establish building eligibility.'
        else:content+=' No matching current snapshot is available. Expired rates are excluded from recommendations.'
    return {'content':content,'plans':[public_plan(p) for p in chosen],'availability':'address_unconfirmed',
            'criteria':{'category':category,'postcode':postcode,'max_monthly_aud':budget,'minimum_download_mbps':speed},
            'scope':'Local official snapshots; not market-wide or live quotes. Verify against your address.'}
