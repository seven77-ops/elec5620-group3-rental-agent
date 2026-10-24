"""Concise replies assembled only from retrieved evidence and current inventory."""
from ..areas.evidence import TOPICS


def summarize(report,catalog,brief,focus='balanced'):
    areas=report['areas']
    if not areas:return '当前房源快照中，没有区域符合这次房型和可比较预算条件。你更愿意调整预算、卧室要求，还是区域范围？'
    topics=[p['topic'] for p in report['priorities']]
    names='、'.join(a['suburb'] for a in areas)
    unknown=[t for t in topics if t in ('quiet','safety')]
    if topics and len(unknown)==len(topics) and focus!='housing':
        labels='、'.join(TOPICS[t] for t in unknown)
        text=f'现有资料还不能判断 {names} 哪个更符合你看重的{labels}，不能用公园或图书馆的存在替代这类判断。'
        if any('quiet'==t for t in unknown):text+=' 安静程度需要核对具体楼栋、临街朝向和不同时段的噪音。'
        if all(not a['evidence'] for a in areas):text+=' 这几个区域的生活资料也尚未整理。'
        return text+' 下方保留房源库存和资料缺口，供你继续筛选。'
    parts=[]
    if topics and focus!='housing':parts.append('你这次看重'+'、'.join(TOPICS[t] for t in topics)+'。')
    if unknown and focus!='housing':parts.append('其中'+'、'.join(TOPICS[t] for t in unknown)+'还不能判断，不能视为已满足。')
    if report['criteria_summary']:parts.append('按这次条件（'+report['criteria_summary']+'）：')
    else:parts.append('先看 '+names+' 已有的资料与房源：')
    for area in areas:
        name=area['suburb'];count=area['matching_count']
        if count:
            low=area['min_weekly_rent'];high=area['max_weekly_rent']
            price=f'AUD {low:g}' if low==high else f'AUD {low:g}–{high:g}'
            line=f'{name}：当前快照有{count}条符合房屋条件的候选，标价{price}/周。'
        else:
            line=f'{name}：当前快照没有符合这次房屋条件的候选。'
            if report['budget_applied']:
                filters={k:v for k,v in brief.items() if k in ('min_bedrooms','min_bathrooms','min_car_spaces')}
                available=catalog.matching({**filters,'suburb':name})
                if available:line+=f"保持房型要求，该区现有库存最低标价为 AUD {min(r['weekly_rent'] for r in available):g}/周，超过本次预算。"
        if focus!='housing':
            evidence=next((e for e in area['evidence'] if e['supports_topics']),None)
            if evidence:line+=' '+evidence['summary']
            elif not area['evidence']:line+=' 区域生活资料尚未整理。'
            elif topics:line+=' 暂缺与你这次生活偏好直接对应的已核对资料。'
        parts.append(line)
    eligible=[a for a in areas if a['matching_count']]
    if focus=='housing' and eligible:
        cheapest=min(eligible,key=lambda a:a['min_weekly_rent'])
        parts.append(f"这批符合条件的候选里，可先看 {cheapest['suburb']} 的低标价房源；这不是全区域市场租金结论，计价对象和在租状态仍需核实。")
    elif topics and eligible:
        strongest=max(len(a['matched_topics']) for a in eligible)
        supported=[a for a in eligible if len(a['matched_topics'])==strongest]
        if strongest and len(supported)==1 and len(eligible)>1:
            a=supported[0];labels='、'.join(TOPICS[t] for t in a['matched_topics'])
            parts.append(f'按目前能核对的资料，可优先了解 {a["suburb"]} 的{labels}配套；其他区域的资料缺口不代表没有这些配套。')
        elif strongest and len(eligible)>1:
            backed='、'.join(a['suburb'] for a in eligible if a['matched_topics'])
            parts.append(f'{backed} 有与你偏好相关的配套资料，接下来可以结合去学校或公司的实际通勤继续比较；没有对应资料的区域仍需补充核实。')
    elif not topics:parts.append('你更看重餐饮、户外、图书馆还是通勤？明确侧重后可以继续缩小范围。')
    return '\n'.join(parts)
