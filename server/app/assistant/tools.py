"""Bounded deterministic tools: cards and explanatory facts come from the catalogue."""
from ..real_data.preferences import preference_context
from ..real_data.market import MarketData
from .comparison import build_comparison,verification_checklist

UNKNOWN = '是否仍在租、计价对象、账单、起租日期和通勤均待核实。'
CLARIFY = '请确认预算是每周还是每月、按人还是整套，并补充区域、卧卫车位要求或明确房源编号。'
CLARIFICATION_TEMPLATES = {
    'budget_units': '请确认预算金额是每周还是每月、按人、按房间还是整套，以及是否含账单。',
    'reference': '请指出要讨论的房源编号，或在已展示的卡片中选择。',
    'unknown_fact': '目前没有已核实的噪音、隔音、通勤、账单和在租数据。我整理了可直接询问中介和看房时检查的问题；也可以先比较已知卧卫、车位和周租。',
    'missing_preferences': '请补充区域、预算及计价对象、人数和卧卫车位需求。',
    'conflicting_preferences': '偏好条件存在冲突，请确认期望预算不高于最高预算，并核对通勤上下限与入住日期。',
}


def known_listings(conversation):
    # Repeated cards regain their current display recency before the context bound.
    identifiers={}
    for message in conversation['messages']:
        for row in message['listings']:
            identifiers.pop(row['listing_id'],None)
            identifiers[row['listing_id']]=True
    return list(identifiers)


def reference_listings(conversation):
    return next((m['listings'] for m in reversed(conversation['messages']) if m['listings']),[])


def execute(intent,case,conversation,catalog,requested_ids):
    name=intent['intent']; cards=[]; actions=[]
    if name=='workflow':
        from .workflow import execute_workflow
        return execute_workflow(intent,case,conversation,catalog,requested_ids)
    agent={'update_preferences':'agent1','search':'agent2','compare':'agent2','explain':'agent2','market':'agent2','select':'agent2',
           'contract':'agent3','aftercare':'agent4','followup':'agent2','draft_contract':'agent3'}.get(name,'assistant')
    ids=requested_ids or intent.get('listing_ids',[])
    if not ids and name in ('compare','explain','select'):
        return {'intent':'clarify','agent':agent,'content':'请指出要讨论的房源，可提供房源编号或在卡片中选择。','listings':[],'actions':[]}
    if name=='search':
        # Unconfirmed drafts are context only; never silently used as confirmed filters.
        filters=preference_context(case['confirmations'][-1]['profile'],catalog)['filters'] if (
            case['confirmations'] and case['confirmations'][-1]['fingerprint']==case['draft']['fingerprint'] and
            case['confirmations'][-1]['draft_revision']==case['draft']['revision']) else {}
        filters={**(conversation.get('last_search_filters') or filters),**intent.get('filters',{})}
        return search_answer(catalog,filters)
    elif name in ('compare','explain','select'):
        cards=[catalog.get(i) for i in ids]
        if name=='compare' and len(cards)<2:
            return {'intent':'clarify','agent':agent,'content':'请选择至少两套已展示的房源进行比较。','listings':[],'actions':[]}
        lines=[f"{r['address']}（{r['listing_id']}）：{r['bedroom_label']}卧、{r['bathrooms']:g}卫、{r['car_spaces']:g}车位，房源 AUD {r['weekly_rent']:g}/周。" for r in cards]
        if name=='compare': lines.append(f"前两套房源周租相差 AUD {abs(cards[0]['weekly_rent']-cards[1]['weekly_rent']):g}；计价对象未核实，不能据此认定个人总费用差异。")
        if name=='select':
            actions=[{'type':'navigate','label':'前往候选页确认保存','page':'recommendations'}]
            lines.append('请在候选页按当前确认偏好生成报告，再明确确认保存。')
        content='\n'.join(lines)+'\n'+UNKNOWN
    elif name=='followup':
        selection=case.get('selection')
        current=(selection and case['confirmations'] and
            selection.get('profile_fingerprint')==case['draft']['fingerprint'] and
            case['confirmations'][-1]['fingerprint']==case['draft']['fingerprint'] and
            case['confirmations'][-1]['draft_revision']==case['draft']['revision'])
        if not current:
            content='请先保存一套符合当前确认需求的房源候选，再准备看房与询问。'
            actions=[{'type':'navigate','label':'先保存房源候选','page':'recommendations'}]
        else:
            from ..adapters.candidate_followup import enquiry_questions, DEFAULT_FACTS
            content='围绕你已保存的 '+selection['listing_snapshot']['address']+'，建议先问：\n'
            content+='\n'.join(f'{i}. {q}' for i,q in enumerate(enquiry_questions(selection,DEFAULT_FACTS),1))
            content+='\n可在房源跟进里记录中介回复；已有合同可直接复核。这份清单尚未发送给中介。'
            actions=[{'type':'navigate','label':'记录回复与看房安排','page':'recommendations?followup=1'},
                {'type':'navigate','label':'已有合同，开始复核','page':'contract?mode=review'}]
    elif name=='market':
        market=intent.get('market')
        if market is None:
            content='请提供邮编、房源卧室数和已核实的租金计价对象；房源计价对象未知时不能判断高低。'
        else:
            result=MarketData().lookup(**market)
            if result['status']=='available':
                lines=[f"历史参考：{market['postcode']}，{market['bedrooms']}卧整套公寓。"]
                for r in result['benchmarks']:
                    lines.append(f"房源对应分类的历史周租中位数 AUD {r['median']:g}；来源：{r['source_url']}")
                content='\n'.join(lines)+'\n'+' '.join(result['limitations'])
            else: content='当前历史参考未覆盖该邮编、卧室数或计价对象。覆盖范围为 '+', '.join(result['coverage']['postcodes'])+'；仅支持一卧、两卧整套公寓。'
    elif name=='draft_contract':
        content='可以先准备新州普通整租住宅的未签署草稿。请在合同助手核对房源、拟定租金、双方姓名和租期；未知信息留空，确认后才保存。'
        actions=[{'type':'navigate','label':'准备租约草稿','page':'contract?mode=draft'}]
    elif name in ('contract','aftercare'):
        content='合同审核由 Agent3 处理，请前往合同页完成材料和确认。' if name=='contract' else '租后事项由 Agent4 处理，请前往租后页查看并确认具体操作。'
        actions=[{'type':'navigate','label':'前往合同审核' if name=='contract' else '前往租后服务','page':'contract?mode=review' if name=='contract' else name}]
    else: content=CLARIFICATION_TEMPLATES.get(intent.get('clarification_reason'),CLARIFY) if name=='clarify' else '我可以收集偏好、筛选真实房源、比较房源，并引导合同和租后事项。请告诉我你的需求。'
    result={'intent':name,'agent':agent,'content':content,'listings':cards,'actions':actions}
    if name=='compare':
        result['comparison']=build_comparison(cards,case,conversation)
        result['content']+='\n'+result['comparison']['summary']
    if name in ('compare','explain') or (name=='clarify' and intent.get('clarification_reason')=='unknown_fact'):
        result['verification_checklist']=verification_checklist()
    return result


def query_text(filters):
    parts=[filters.get('suburb') or '不限区域']
    for key,label in (('min_bedrooms','卧'),('min_bathrooms','卫'),('min_car_spaces','车位')):
        if key in filters: parts.append(f"至少{filters[key]}{label}" if filters[key] else label+'不限')
    if 'max_weekly_rent' in filters: parts.append(f"房源周租上限{filters['max_weekly_rent']:g}澳元")
    return '，'.join(parts)


def search_answer(catalog,filters):
    result=catalog.search(filters,page_size=5)
    f=result['filters']; cards=result['items']; actions=[]
    if cards:
        content=f"按这些条件找到 {result['total']} 条房源，先给你看 {len(cards)} 条。"+query_text(f)+'。'
    else:
        content='按'+query_text(f)+'，当前房源库没有匹配的房源。'
        if 'max_weekly_rent' in f:
            without_budget={k:v for k,v in f.items() if k!='max_weekly_rent'}
            rows=catalog.matching({**without_budget,'sort':'rent_asc'})
            if rows:
                lowest=rows[0]['weekly_rent']; delta=lowest-f['max_weekly_rent']
                content+=f"\n保持区域、卧卫和车位要求，最低房源周租是 AUD {lowest:g}，比你的上限高 AUD {delta:g}。"
                alternative={**f,'max_weekly_rent':lowest}
                actions.append({'type':'suggestion','label':f'看看每周 {lowest:g} 的选择',
                    'message':'只预览房源：'+query_text(alternative)+'。不要修改已保存的偏好。'})
        if 'suburb' in f:
            elsewhere={k:v for k,v in f.items() if k!='suburb'}
            rows=catalog.matching(elsewhere)
            if rows:
                examples='、'.join(list(dict.fromkeys(row['suburb'] for row in rows))[:3])
                content+=f"\n保留预算、卧卫和车位要求，扩大到其他区域有 {len(rows)} 条，例如 {examples}。"
                actions.append({'type':'suggestion','label':f'扩大区域看看（{len(rows)}条）',
                    'message':'只预览房源：'+query_text(elsewhere)+'。不要修改已保存的偏好。'})
        if actions: content+='\n你更愿意调整预算，还是扩大区域？我会等你选择。'
        else: content+='\n暂时没有只调整预算或区域就能匹配的方案。你愿意先调整哪项条件？'
    content+='\n这是房源标价预览，偏好尚未修改；在租状态、账单和计价对象仍需核实。'
    return {'intent':'search','agent':'agent2','content':content,'listings':cards,'actions':actions,'_search_filters':f}


def preference_summary(profile):
    """Show all consequential inherited values before the explicit confirmation."""
    b=profile['budget']; h=profile.get('housing_preferences',{}); c=profile['commute']; dates=profile['move_in_window']
    scope={'per_person':'按人','per_room':'按房间','whole_property':'整套'}[b['scope']]
    mode={'private_room':'独立单间','shared_room':'共享房间','whole_property':'整租','student_accommodation':'学生公寓'}[profile['rental_mode']]
    budget_mode='按房源金额粗筛' if h.get('budget_match_mode','advertised_amount')=='advertised_amount' else '仅同计价对象筛预算'
    labels={'commute':'通勤','cost':'费用','housing':'居住','amenities':'设施',
        'private_bedroom':'独立卧室','private_bathroom':'独立卫浴','furnished':'家具',
        'laundry':'洗衣设施','kitchen_access':'厨房','public_transport':'公共交通',
        'walk':'步行','drive':'驾车','bike':'骑行'}
    destination='悉尼大学（预设目的地，待核实）' if profile['destination_id']=='demo-usyd' else profile['destination_id']
    def readable_values(values):
        return '、'.join(labels.get(k,k)+' '+f'{v:g}' for k,v in values.items()) or '未指定'
    result=[f"预算：偏好 {b['preferred']:g}，上限 {b['maximum']:g} AUD/周；{scope}，{'含账单' if b['includes_bills'] else '不含账单'}；{'硬上限' if b['hard_limit'] else '可协商'}。",
        f"人数：{profile['occupants']}；租赁方式：{mode}。",
        f"区域：{h.get('suburb') or '不限'}；至少卧室 {h.get('min_bedrooms') if h.get('min_bedrooms') is not None else '不限'}、浴室 {h.get('min_bathrooms') if h.get('min_bathrooms') is not None else '不限'}、车位 {h.get('min_car_spaces') if h.get('min_car_spaces') is not None else '不限'}；{budget_mode}。",
        f"通勤：目的地 {destination}；方式 {'、'.join(labels.get(k,k) for k in c['modes'])}；偏好 {c['preferred_minutes']:g}、最长 {c['maximum_minutes']:g} 分钟；{'硬限制' if c['hard_limit'] else '可协商'}；到达 {profile['arrival_time']}（{profile['timezone']}）。",
        f"入住：{dates['from']} 至 {dates['to']}；租期 {profile['lease_months']:g} 个月。",
        '硬要求：'+('、'.join(labels.get(k,k) for k in profile['hard_requirements']) or '无')+'；软偏好：'+readable_values(profile['soft_preferences'])+'；权重：'+readable_values(profile['weights'])+'。',
        '0卧开放式按1个睡眠空间计算；计价对象、账单、通勤和在租状态仍须核实。']
    return result


def filter_summary(filters):
    labels={'suburb':'区域','min_bedrooms':'至少卧室','min_bathrooms':'至少浴室','min_car_spaces':'至少车位','max_weekly_rent':'最高房源周租 AUD','sort':'排序'}
    orders={'rent_asc':'周租从低到高','rent_desc':'周租从高到低','bedrooms_desc':'卧室从多到少'}
    return '，'.join(labels[k]+' '+(orders[v] if k=='sort' else str(v)) for k,v in filters.items()) or '所有房源'


CARD_CONTEXT_FIELDS = ('listing_id','address','suburb','postcode','bedrooms','advertised_bedrooms',
    'bedroom_label','bedroom_count_basis','bathrooms','car_spaces','weekly_rent','rent_scope',
    'bills_included','available_from','commute_minutes','source_url','captured_at')


def listing_context(catalog,identifiers):
    """Facts are always reloaded from the current catalogue, never transcript copies."""
    from ..common import ApiError
    result=[]
    for identifier in identifiers[-100:]:
        try: row=catalog.get(identifier)
        except ApiError as exc:
            if exc.code=='listing_not_found': continue
            raise
        result.append({key:row[key] for key in CARD_CONTEXT_FIELDS if key in row})
    return result


def history_context(conversation,identifiers):
    allowed=set(identifiers)
    return [{'role':m['role'],'content':m['content'][:3000],
        'listing_ids':[r['listing_id'] for r in m['listings'] if r['listing_id'] in allowed],
        'display_order':[{'position':index+1,'listing_id':r['listing_id']}
            for index,r in enumerate(m['listings']) if r['listing_id'] in allowed]}
        for m in conversation['messages'][-20:]]
