"""Concise replies assembled only from retrieved evidence and current inventory."""
from ..areas.evidence import TOPICS


def summarize(report,catalog,brief,focus='balanced'):
    areas=report['areas']
    if not areas:return 'No area in the current listing snapshot matches these property and comparable budget requirements. Would you prefer to adjust budget, bedrooms or suburb range?'
    topics=[p['topic'] for p in report['priorities']]
    names=', '.join(a['suburb'] for a in areas)
    unknown=[t for t in topics if t in ('quiet','safety')]
    if topics and len(unknown)==len(topics) and focus!='housing':
        labels=', '.join(TOPICS[t] for t in unknown)
        text=f'Available evidence cannot determine which of {names} better meets your priorities for {labels}. The presence of parks or libraries cannot establish this.'
        if any('quiet'==t for t in unknown):text+=' Check the specific building, street orientation and noise at different times to assess quietness.'
        if all(not a['evidence'] for a in areas):text+=' Lifestyle information for these areas is not yet compiled.'
        return text+' Listing inventory and evidence gaps are shown below to support further filtering.'
    parts=[]
    if topics and focus!='housing':parts.append('Your priorities: '+', '.join(TOPICS[t] for t in topics)+'.')
    if unknown and focus!='housing':parts.append('Among these, '+', '.join(TOPICS[t] for t in unknown)+' cannot yet be assessed or treated as satisfied.')
    if report['criteria_summary']:parts.append('Using these requirements ('+report['criteria_summary']+'):')
    else:parts.append('Review '+names+' and its available evidence and listings:')
    for area in areas:
        name=area['suburb'];count=area['matching_count']
        if count:
            low=area['min_weekly_rent'];high=area['max_weekly_rent']
            price=f'AUD {low:g}' if low==high else f'AUD {low:g}–{high:g}'
            line=f'{name}: the current snapshot has {count} matching candidates, advertised at {price}/week.'
        else:
            line=f'{name}: the current snapshot has no candidates matching these property requirements.'
            if report['budget_applied']:
                filters={k:v for k,v in brief.items() if k in ('min_bedrooms','min_bathrooms','min_car_spaces')}
                available=catalog.matching({**filters,'suburb':name})
                if available:line+=f" Keeping the property requirements, the lowest advertised rent in this area is AUD {min(r['weekly_rent'] for r in available):g}/week, above this budget."
        if focus!='housing':
            evidence=next((e for e in area['evidence'] if e['supports_topics']),None)
            if evidence:line+=' '+evidence['summary']
            elif not area['evidence']:line+=' Area lifestyle information is not yet compiled.'
            elif topics:line+=' Verified evidence directly relevant to your lifestyle priorities is unavailable.'
        parts.append(line)
    eligible=[a for a in areas if a['matching_count']]
    if focus=='housing' and eligible:
        cheapest=min(eligible,key=lambda a:a['min_weekly_rent'])
        parts.append(f"Among these matching candidates, consider the lower-priced listings in {cheapest['suburb']} first.")
    elif topics and eligible:
        strongest=max(len(a['matched_topics']) for a in eligible)
        supported=[a for a in eligible if len(a['matched_topics'])==strongest]
        if strongest and len(supported)==1 and len(eligible)>1:
            a=supported[0];labels=', '.join(TOPICS[t] for t in a['matched_topics'])
            parts.append(f'Based on currently verifiable evidence, consider {labels} facilities in {a["suburb"]} first. Evidence gaps for other areas do not mean those facilities are absent.')
        elif strongest and len(eligible)>1:
            backed=', '.join(a['suburb'] for a in eligible if a['matched_topics'])
            parts.append(f'{backed} has facilities evidence relevant to your preferences. Continue comparing it with your actual commute; areas without relevant evidence need further checks.')
    elif not topics:parts.append('Which matters more: dining, outdoor spaces, libraries or commuting? Choose priorities to narrow the options.')
    return '\n'.join(parts)
