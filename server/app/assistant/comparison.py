"""Personal comparisons explain catalogue facts against explicit, current needs."""
from .dialogue import brief_summary

CORE = (('min_bedrooms','bedrooms','bedrooms'),('min_bathrooms','bathrooms','bathrooms'),('min_car_spaces','car_spaces','parking spaces'))
QUESTIONS = [
    'Is this property still available, and what is the earliest move-in date?',
    'Is the advertised weekly rent for the whole property, per room or per person? Which water, electricity, gas and internet bills are included?',
    'Can I check street, neighbour and equipment noise during the day and evening, and assess soundproofing at the inspection?',
    'Please verify furnishings, property condition and commute time using the actual route at the required time.',
]


def verification_checklist():
    return {'title':'Inspection and enquiry checklist','items':list(QUESTIONS)}


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
        from ..real_data.profile import supplied_profile
        confirmed=supplied_profile(confirmed,case.get('requirements_contract')!='supplied-only-v1')
        needs={**confirmed.get('housing_preferences',{})}
        if 'maximum' in confirmed.get('budget',{}): needs['max_weekly_rent']=confirmed['budget']['maximum']
        sources.append('Current confirmed preferences')
    def use_brief():
        needs.update({k:v for k,v in brief.items() if k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces')})
        if 'budget_amount' in brief:
            # A monthly or unqualified amount cannot become a weekly ceiling.
            needs.pop('max_weekly_rent',None)
            if brief.get('budget_period')=='week': needs['max_weekly_rent']=brief['budget_amount']
    if brief:
        use_brief(); sources.append('Explicit rental requirements ('+brief_summary(brief)+')')
    if query:
        needs.update(query); sources.append('Most recent listing query')
    if brief and conversation.get('dialogue_mode')=='collect_preferences': use_brief()
    return needs,'; '.join(sources) if sources else 'No personal comparison criteria supplied; showing known listing differences only',brief


def build_comparison(cards,case,conversation):
    needs,basis,brief=comparison_needs(case,conversation)
    confirmed=current_confirmed_profile(case)
    if confirmed:
        from ..real_data.profile import supplied_profile
        confirmed=supplied_profile(confirmed,case.get('requirements_contract')!='supplied-only-v1')
    hard_requirements=confirmed.get('hard_requirements',[]) if confirmed else []
    items=[]; ranks=[]
    for row in cards:
        matches=[]; tradeoffs=[]; violations=0
        if needs.get('suburb'):
            if row['suburb']==needs['suburb']: matches.append('Suburb matches '+needs['suburb'])
            else: tradeoffs.append('Suburb does not match '+needs['suburb']); violations+=1
        for key,field,label in CORE:
            minimum=needs.get(key)
            if minimum is None: continue
            if minimum==0:
                matches.append(label+' unrestricted; additional '+label+' does not count as a personal advantage')
            elif row[field]>=minimum:
                detail='open-plan sleeping space' if field=='bedrooms' and row.get('advertised_bedrooms')==0 else label
                matches.append(f"{detail} {row[field]:g}, meeting the minimum of {minimum:g}")
            else: tradeoffs.append(f"{label} {row[field]:g}, below the minimum of {minimum:g}"); violations+=1
        if 'private_bedroom' in hard_requirements and row.get('advertised_bedrooms')==0:
            tradeoffs.append('This is a known open-plan sleeping space and does not meet your confirmed private-bedroom requirement'); violations+=1
        ceiling=needs.get('max_weekly_rent')
        if ceiling is not None:
            if row['weekly_rent']<=ceiling: matches.append(f"Advertised weekly rent AUD {row['weekly_rent']:g} is within the query limit of {ceiling:g}")
            else: tradeoffs.append(f"Advertised weekly rent is AUD {row['weekly_rent']-ceiling:g} above the query limit"); violations+=1
        if not matches and not tradeoffs: matches.append('Compare the displayed bedrooms, bathrooms, parking and advertised weekly rent')
        checks=list(QUESTIONS)
        if row.get('advertised_bedrooms')==0: checks.append('This listing is open-plan. Check whether it meets your private-bedroom needs.')
        items.append({'listing_id':row['listing_id'],'matches':matches,'tradeoffs':tradeoffs,'to_verify':checks})
        ranks.append((violations,row['weekly_rent'],row['listing_id']))
    meaningful=any(k in needs for k in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces','max_weekly_rent'))
    eligible=[rank for rank in ranks if rank[0]==0]
    recommended=min(eligible)[2] if meaningful and eligible else None
    if recommended: summary='Among these listings, first consider one that meets your explicit requirements and has lower advertised weekly rent.'
    elif meaningful: summary='None of these listings meets all explicit requirements. Review the tradeoffs before deciding whether to adjust the preview filters.'
    else: summary='No personal criteria are available yet. Compare known listing differences, then add your priorities for a more tailored assessment.'
    if cards:
        summary+=f" Advertised weekly rent for these listings ranges from AUD {min(r['weekly_rent'] for r in cards):g} to {max(r['weekly_rent'] for r in cards):g}."
    if brief.get('budget_amount') and brief.get('budget_period')!='week': summary+=' Monthly budgets and budgets with an unconfirmed period are excluded from weekly rent comparisons. Confirm the weekly amount.'
    return {'basis':basis,'recommended_listing_id':recommended,'items':items,'summary':summary}


def prepare_enquiry(row):
    questions=list(QUESTIONS)
    return {'listing_id':row['listing_id'],'address':row['address'],'subject':'Property enquiry: '+row['address'],
        'body':'Hello, I would like to enquire about '+row['address']+'.\n'+'\n'.join(f'{i}. {q}' for i,q in enumerate(questions,1))+'\nPlease let me know the inspection arrangements. Thank you.',
        'questions':questions,'source_url':row['source_url']}
