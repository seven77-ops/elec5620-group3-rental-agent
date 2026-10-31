"""Present the complete eligible set, with explicit conversation-aware rotation."""
from collections import Counter,defaultdict,deque

PAGE_SIZE=12


def interleave(rows):
    groups=defaultdict(deque)
    for row in rows:groups[row['suburb']].append(row)
    result=[]
    while any(groups.values()):
        for group in groups.values():
            if group:result.append(group.popleft())
    return result


def arrange(answer,conversation,brief,refresh=False):
    report=answer.get('commute_recommendation')
    if not report:return answer
    rows=answer.get('listings',[])
    appearances=Counter(row['listing_id'] for message in conversation.get('messages',[])
        if message.get('commute_recommendation') for row in message.get('listings',[])[:PAGE_SIZE])
    ordered=[]
    levels=sorted({appearances[r['listing_id']] for r in rows}) if refresh else [None]
    for level in levels:
        group=[r for r in rows if level is None or appearances[r['listing_id']]==level]
        ordered.extend(interleave(group) if brief.get('commute_priority','balanced')=='balanced' else group)
    answer['listings']=ordered
    # Area tabs describe the entire eligible result, including later pages.
    existing={a['suburb']:a for a in report.get('areas',[])}
    grouped=defaultdict(list)
    for row in ordered:grouped[row['suburb']].append(row)
    report['areas']=[{**existing.get(suburb,{}),'suburb':suburb,'count':len(group),
        'min_weekly_rent':min(r['weekly_rent'] for r in group),
        'max_weekly_rent':max(r['weekly_rent'] for r in group)} for suburb,group in grouped.items()]
    report['matching_count']=len(ordered)
    if refresh and ordered:
        answer['content']+= '  All filters are retained, prioritising listings shown less often.'
    return answer
