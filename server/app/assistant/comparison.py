"""Personal comparisons explain catalogue facts against explicit, current needs."""
from .dialogue import brief_summary

CORE = (('min_bedrooms','bedrooms','卧室'),('min_bathrooms','bathrooms','浴室'),('min_car_spaces','car_spaces','车位'))
QUESTIONS = [
    '这套房源目前仍可出租吗？最早可入住日期是什么时候？',
    '标示周租是整套、每间还是每人？水、电、燃气和网络账单包含哪些？',
    '看房时能否分别在白天和晚间检查临街、邻居及设备噪音，并了解隔音情况？',
    '请核实家具、房屋状况，以及实际路线在所需时段的通勤时间。',
]


def verification_checklist():
    return {'title':'看房与询问核实清单','items':list(QUESTIONS)}


def current_confirmed_profile(case):
    confirmations=case.get('confirmations',[])
    last=confirmations[-1] if confirmations else None
    draft=case.get('draft',{})
    return last['profile'] if (last and last.get('draft_revision')==draft.get('revision') and
        last.get('fingerprint')==draft.get('fingerprint') and case.get('agent1',{}).get('state')=='Confirmed') else None


def comparison_needs(case,conversation):
    brief=conversation.get('rental_brief') or {}
    query=conversation.get('last_search_filters') or {}
    confirmed=current_confirmed_profile(case)
    needs={}; sources=[]
    if confirmed:
        needs={**confirmed.get('housing_preferences',{}),'max_weekly_rent':confirmed['budget']['maximum']}
        sources.append('当前已确认偏好')
    def use_brief():
        needs.update({k:v for k,v in brief.items() if k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces')})
        if 'budget_amount' in brief:
            # A monthly or unqualified amount cannot become a weekly ceiling.
            needs.pop('max_weekly_rent',None)
            if brief.get('budget_period')=='week': needs['max_weekly_rent']=brief['budget_amount']
    if brief:
        use_brief(); sources.append('本次明确租房需求（'+brief_summary(brief)+'）')
    if query:
        needs.update(query); sources.append('最近房源查询')
    if brief and conversation.get('dialogue_mode')=='collect_preferences': use_brief()
    return needs,'；'.join(sources) if sources else '未提供个人比较条件；仅列出已知房源差异',brief


def build_comparison(cards,case,conversation):
    needs,basis,brief=comparison_needs(case,conversation)
    confirmed=current_confirmed_profile(case)
    hard_requirements=confirmed.get('hard_requirements',[]) if confirmed else []
    items=[]; ranks=[]
    for row in cards:
        matches=[]; tradeoffs=[]; violations=0
        if needs.get('suburb'):
            if row['suburb']==needs['suburb']: matches.append('区域符合 '+needs['suburb'])
            else: tradeoffs.append('区域不符合 '+needs['suburb']); violations+=1
        for key,field,label in CORE:
            minimum=needs.get(key)
            if minimum is None: continue
            if minimum==0:
                matches.append(label+'无要求；额外'+label+'不作为个人优势')
            elif row[field]>=minimum:
                detail='开放式睡眠空间' if field=='bedrooms' and row.get('advertised_bedrooms')==0 else label
                matches.append(f"{detail} {row[field]:g}，符合至少 {minimum:g} 的数量条件")
            else: tradeoffs.append(f"{label} {row[field]:g}，低于至少 {minimum:g} 的要求"); violations+=1
        if 'private_bedroom' in hard_requirements and row.get('advertised_bedrooms')==0:
            tradeoffs.append('已知为开放式睡眠空间，不符合已确认的独立卧室硬要求'); violations+=1
        ceiling=needs.get('max_weekly_rent')
        if ceiling is not None:
            if row['weekly_rent']<=ceiling: matches.append(f"房源标示周租 AUD {row['weekly_rent']:g} 在查询金额上限 {ceiling:g} 内；个人费用待核实")
            else: tradeoffs.append(f"房源标示周租高于查询金额上限 AUD {row['weekly_rent']-ceiling:g}；计价对象待核实"); violations+=1
        if not matches and not tradeoffs: matches.append('可核对已展示的卧卫、车位和标示周租')
        checks=list(QUESTIONS)
        if row.get('advertised_bedrooms')==0: checks.append('房源为开放式空间，请确认是否符合独立卧室需求。')
        items.append({'listing_id':row['listing_id'],'matches':matches,'tradeoffs':tradeoffs,'to_verify':checks})
        ranks.append((violations,row['weekly_rent'],row['listing_id']))
    meaningful=any(k in needs for k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces','max_weekly_rent'))
    eligible=[rank for rank in ranks if rank[0]==0]
    recommended=min(eligible)[2] if meaningful and eligible else None
    if recommended: summary='这些房源中，优先考虑符合明确条件且标示周租较低的一套。'
    elif meaningful: summary='这些房源没有完全符合明确条件的一套；请先查看取舍，再决定是否调整预览条件。'
    else: summary='尚无个人条件，先比较已知房源差异；补充你更在意的条件后可进一步判断。'
    if cards:
        summary+=f"这些房源标示周租范围为 AUD {min(r['weekly_rent'] for r in cards):g}–{max(r['weekly_rent'] for r in cards):g}。"
    summary+='计价对象、账单和在租状态待核实，不能据此认定个人总费用或实际性价比。'
    if brief.get('budget_amount') and brief.get('budget_period')!='week': summary+='月预算或未确认周期的预算未用于周租比较，请确认每周金额。'
    return {'basis':basis,'recommended_listing_id':recommended,'items':items,'summary':summary}


def prepare_enquiry(row):
    questions=list(QUESTIONS)
    return {'listing_id':row['listing_id'],'address':row['address'],'subject':'房源询问：'+row['address'],
        'body':'您好，我想了解 '+row['address']+'。\n'+'\n'.join(f'{i}. {q}' for i,q in enumerate(questions,1))+'\n如方便，请告知看房安排。谢谢。',
        'questions':questions,'source_url':row['source_url']}
