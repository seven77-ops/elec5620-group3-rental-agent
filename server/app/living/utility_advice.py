"""Source-grounded utility answers. Monetary facts come exclusively from SQLite."""
from copy import deepcopy
import re
from .utility_catalog import amount, public_plan

LABELS={'internet':'网络','electricity':'电力','gas':'燃气','water':'供水'}
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
            content='以下是收录套餐中可比较的网络方案，按首12个月基础月租排序；不是全市场最低价，也未核实具体地址可用性。'
            if budget is not None:content+=f' 月预算 AUD {amount(budget)} 按恢复原价后的月租筛选。'
            if speed is not None:content+=f' 下载参考至少 {amount(speed)} Mbps，需核对你家的接入技术。'
            for p in chosen:content+='\n'+p['name']+'：'+p['price_summary']+f"；首年基础月租 AUD {amount(p['first_year_base_cost_aud'])}。"
            content+='\n首年金额不含路由器、运费、特殊安装或提前离网费用；促销资格、优惠码和设备留网条件请看套餐详情。你可以补充人数、速度和预算，我再缩小范围。'
        else:content='当前有效记录里没有同时满足这些预算和速度条件的网络套餐。预算按恢复原价后的月租核对；不能把前几个月优惠价当作长期价格。可以调整预算或速度，或到官网查询其他方案。'
    elif category=='water':
        chosen=rows[:1]
        content='Sydney Water服务由房屋地址决定，不能自由更换成另一家零售商。'
        for p in chosen:content+='\n'+'\n'.join(p['pricing_lines'])
        content+='\n私人租赁中，固定供水和污水等产权费用通常由房东承担；用水费转付给租客须满足独立水表、节水要求、提供用量账单证据等条件。租客通常不用另开Sydney Water账户。'
        if chosen:content+=' 费用责任规则见下方NSW官方说明。'
        if not chosen:content+=' 当前没有有效水价快照，金额请到Sydney Water官网核对。'
    else:
        # Energy comparisons need the actual meter tariff and usage profile; do not invent a monthly bill.
        ordered=sorted(rows,key=lambda p:('CONT_LOAD' in p['pricing'].get('model',''),'TIME_OF_USE' in p['pricing'].get('model',''),p['name'],p['id']))
        chosen=[];seen=set()
        for p in ordered:
            key=(p['provider_id'],p['category'],p['name'])
            if key not in seen:chosen.append(p);seen.add(key)
            if len(chosen)>=6:break
        content='电力、燃气通常由每日固定费加实际用量费组成；分时电价还取决于用电时段，燃气可能按阶梯计费。没有账单用量和电表费率，不能据单价认定哪家最便宜。'
        if not category and not named:
            # Overview shows one representative offer per category/provider, including broadband and water.
            chosen=[];seen=set()
            for p in rows:
                key=(p['provider_id'],p['category'])
                if key not in seen:chosen.append(p);seen.add(key)
            content='已收录网络、电力、燃气及Sydney Water的官方套餐和计费参考。可以问“每月80以内的网络套餐”“AGL电费怎么收”或“水费谁付”。'
        elif chosen:
            for p in chosen:content+='\n'+p['name']+'（'+p['network_label']+'）：'+'；'.join(p['pricing_lines'][:3])
            content+='\n电气显示的是含GST的优惠前基准费率；折扣、返现、受控负荷和连接费用另按条件核对。提供邮编、账单用量及单一/分时电表信息后再比较，不能把配网范围当成楼栋已可开户。'
        else:content+=' 当前没有匹配的有效快照；过期费率不会作为推荐。'
    return {'content':content,'plans':[public_plan(p) for p in chosen],'availability':'address_unconfirmed',
            'criteria':{'category':category,'postcode':postcode,'max_monthly_aud':budget,'minimum_download_mbps':speed},
            'scope':'本地官方快照；非全市场、非实时报价，需按地址核验。'}
