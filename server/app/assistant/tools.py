"""Bounded deterministic tools: cards and explanatory facts come from the catalogue."""
from ..real_data.preferences import preference_context
from ..real_data.market import MarketData
from .comparison import build_comparison,verification_checklist

CLARIFY = 'Confirm whether your budget is weekly or monthly, per person or for the whole property, and add your suburb, bedroom, bathroom and parking requirements or a listing ID.'
CLARIFICATION_TEMPLATES = {
    'multiple_tasks': 'This message covers several tasks. Which should we handle first: finding a rental, contracts or aftercare? I will follow your chosen order.',
    'budget_units': 'Confirm whether the budget is weekly or monthly, per person, per room or for the whole property, and whether it includes bills.',
    'reference': 'Provide the listing ID or select one of the displayed cards.',
    'unknown_fact': 'Verified noise, soundproofing, commute, bills and availability data are unavailable. The checklist provides questions for the agent and inspection; you can also compare known bedrooms, bathrooms, parking and weekly rent.',
    'missing_preferences': 'Add your suburb, budget and rent scope, occupant count, and bedroom, bathroom and parking requirements.',
    'conflicting_preferences': 'Some preferences conflict. Check that your preferred budget does not exceed the maximum, and review commute limits and move-in dates.',
}


def known_listings(conversation,preview=False):
    # Repeated cards regain their current display recency before the context bound.
    identifiers={}
    for message in conversation['messages']:
        rows=message['listings']
        if preview:rows=rows[:12]
        for row in rows:
            identifiers.pop(row['listing_id'],None)
            identifiers[row['listing_id']]=True
    return list(identifiers)


def reference_listings(conversation):
    return next((m['listings'] for m in reversed(conversation['messages']) if m['listings']),[])


def execute(intent,case,conversation,catalog,requested_ids,ctx=None):
    name=intent['intent']; cards=[]; actions=[]
    if name=='workflow':
        from .workflow import execute_workflow
        return execute_workflow(intent,case,conversation,catalog,requested_ids,ctx=ctx)
    agent={'update_preferences':'agent1','search':'agent2','compare':'agent2','explain':'agent2','market':'agent2','select':'agent2',
           'contract':'agent3','aftercare':'agent4','followup':'agent2','draft_contract':'agent3'}.get(name,'assistant')
    ids=requested_ids or intent.get('listing_ids',[])
    if not ids and name in ('compare','explain','select'):
        return {'intent':'clarify','agent':agent,'content':'Provide the listing ID or select a listing card to discuss.','listings':[],'actions':[]}
    if name=='outside_scope':
        return {'intent':name,'agent':'assistant','content':'Rental discovery currently serves University of Sydney Camperdown / Darlington students. Other universities, campuses and workplace commutes are outside its coverage. Continue with your budget, property requirements and travel time to USYD.','listings':[],'actions':[]}
    if name=='search':
        # Unconfirmed drafts are context only; never silently used as confirmed filters.
        filters=preference_context(case['confirmations'][-1]['profile'],catalog,
            legacy=case.get('requirements_contract')!='supplied-only-v1')['filters'] if (
            case['confirmations'] and case['confirmations'][-1]['fingerprint']==case['draft']['fingerprint'] and
            case['confirmations'][-1]['draft_revision']==case['draft']['revision']) else {}
        filters={**filters,**(conversation.get('last_search_filters') or {}),**intent.get('filters',{})}
        return search_answer(catalog,filters,ctx=ctx,case_id=case["case_id"])
    elif name in ('compare','explain','select'):
        cards=[catalog.get(i) for i in ids]
        if name=='compare' and len(cards)<2:
            return {'intent':'clarify','agent':agent,'content':'Select at least two displayed listings to compare.','listings':[],'actions':[]}
        lines=[f"{r['address']} ({r['listing_id']}): {r['bedroom_label']} bedrooms, {r['bathrooms']:g} bathrooms, {r['car_spaces']:g} parking spaces, advertised rent AUD {r['weekly_rent']:g}/week." for r in cards]
        if name=='compare': lines.append(f"The first two listings differ by AUD {abs(cards[0]['weekly_rent']-cards[1]['weekly_rent']):g} per week. Rent scope is unverified, so this does not establish a difference in personal total costs.")
        if name=='select':
            actions=[{'type':'navigate','label':'Open candidates to confirm and save','page':'recommendations'}]
            lines.append('Generate a report on the candidates page using current confirmed preferences, then explicitly confirm saving.')
        content='\n'.join(lines)
    elif name=='followup':
        selection=case.get('selection')
        current=(selection and case['confirmations'] and
            selection.get('profile_fingerprint')==case['draft']['fingerprint'] and
            case['confirmations'][-1]['fingerprint']==case['draft']['fingerprint'] and
            case['confirmations'][-1]['draft_revision']==case['draft']['revision'])
        if not current:
            content='Save a listing candidate matching your confirmed requirements before preparing an inspection and enquiry.'
            actions=[{'type':'navigate','label':'Save a listing candidate first','page':'recommendations'}]
        else:
            from ..adapters.candidate_followup import enquiry_questions, DEFAULT_FACTS
            content='For your saved listing '+selection['listing_snapshot']['address']+', start with these questions:\n'
            content+='\n'.join(f'{i}. {q}' for i,q in enumerate(enquiry_questions(selection,DEFAULT_FACTS),1))
            content+='\nReview the inspection checklist or complete and review a contract. This checklist has not been sent to the agent.'
            actions=[{'type':'navigate','label':'View inspection checklist','page':'recommendations?followup=1'},
                {'type':'navigate','label':'Review an existing contract','page':'contract?mode=review'}]
    elif name=='market':
        market=intent.get('market')
        if market is None:
            content='Provide the postcode, bedroom count and verified rent scope. Rent cannot be compared when the listing rent scope is unknown.'
        else:
            result=MarketData().lookup(**market)
            if result['status']=='available':
                lines=[f"Historical reference: postcode {market['postcode']}, {market['bedrooms']}-bedroom whole-property apartments."]
                for r in result['benchmarks']:
                    lines.append(f"Historical median weekly rent for this listing category: AUD {r['median']:g}; source: {r['source_url']}")
                content='\n'.join(lines)+'\n'+' '.join(result['limitations'])
            else: content='Historical reference data do not cover this postcode, bedroom count or rent scope. Coverage: '+', '.join(result['coverage']['postcodes'])+'; only whole-property one- and two-bedroom apartments are supported.'
    elif name=='draft_contract':
        content='Prepare an unsigned draft for an ordinary NSW whole-property residential tenancy. Review the property, proposed rent, party names and term in the contract assistant. Leave unknown fields blank and confirm before saving.'
        actions=[{'type':'navigate','label':'Prepare lease draft','page':'contract?mode=draft'}]
    elif name in ('contract','aftercare'):
        content='Agent3 handles contract reviews. Open Contracts to provide documents and confirmations.' if name=='contract' else 'Agent4 handles aftercare. Open Aftercare to review and confirm the specific action.'
        actions=[{'type':'navigate','label':'Open contract review' if name=='contract' else 'Open Aftercare','page':'contract?mode=review' if name=='contract' else name}]
    else: content=CLARIFICATION_TEMPLATES.get(intent.get('clarification_reason'),CLARIFY) if name=='clarify' else 'I can collect preferences, search live listings, compare properties and guide contract and aftercare tasks. Tell me what you need.'
    result={'intent':name,'agent':agent,'content':content,'listings':cards,'actions':actions}
    if name=='compare':
        result['comparison']=build_comparison(cards,case,conversation)
        result['content']+='\n'+result['comparison']['summary']
    if name=='clarify' and intent.get('clarification_reason')=='unknown_fact':
        result['verification_checklist']=verification_checklist()
    return result


def query_text(filters):
    parts=[filters.get('suburb') or 'Any suburb']
    for key,label in (('min_bedrooms','bedrooms'),('min_bathrooms','bathrooms'),('min_car_spaces','parking spaces')):
        if key in filters: parts.append(f"At least {filters[key]} {label}" if filters[key] else label+' unrestricted')
    if 'max_weekly_rent' in filters: parts.append(f"Listing weekly rent limit AUD {filters['max_weekly_rent']:g}")
    return ', '.join(parts)


def search_answer(catalog,filters,ctx=None,case_id=None):
    if ctx is not None and case_id and filters.get("usyd_max_minutes") is not None:
        from ..commute.matching import matching_for_case
        matched=matching_for_case(ctx,case_id,filters)
        result={"items":matched,"total":len(matched),"filters":catalog.filters(filters)}
    else:
        f=catalog.filters(filters);matched=catalog.matching(f)
        result={"items":matched,"total":len(matched),"filters":f}
    f=result['filters']; cards=result['items']; actions=[]
    if cards:
        content=f"Found {result['total']} listings with these requirements. "+query_text(f)+'.'
    else:
        content='For '+query_text(f)+', no listings match in the current catalogue.'
        if 'max_weekly_rent' in f:
            without_budget={k:v for k,v in f.items() if k!='max_weekly_rent'}
            rows=catalog.matching({**without_budget,'sort':'rent_asc'})
            if rows:
                lowest=rows[0]['weekly_rent']; delta=lowest-f['max_weekly_rent']
                content+=f"\nKeeping your suburb, bedroom, bathroom and parking requirements, the lowest weekly rent is AUD {lowest:g}, which is AUD {delta:g} above your limit."
                alternative={**f,'max_weekly_rent':lowest}
                actions.append({'type':'suggestion','label':f'Preview options at {lowest:g} per week',
                    'message':'Preview listings only: '+query_text(alternative)+'. Keep saved preferences unchanged.'})
        if 'suburb' in f:
            elsewhere={k:v for k,v in f.items() if k!='suburb'}
            rows=catalog.matching(elsewhere)
            if rows:
                examples=', '.join(list(dict.fromkeys(row['suburb'] for row in rows))[:3])
                content+=f"\nKeeping your budget, bedroom, bathroom and parking requirements, expanding to other suburbs gives {len(rows)} listings, for example {examples}."
                actions.append({'type':'suggestion','label':f'Explore more suburbs ({len(rows)} listings)',
                    'message':'Preview listings only: '+query_text(elsewhere)+'. Keep saved preferences unchanged.'})
        if actions: content+='\nWould you prefer to adjust the budget or expand the suburb range? Choose how to continue.'
        else: content+='\nChanging only budget or suburb currently gives no matches. Which requirement would you prefer to adjust first?'
    from .recommendation_options import metadata
    return {'intent':'search','agent':'agent2','content':content,'listings':cards,'actions':actions,'_search_filters':f,
            **metadata(catalog,f,total=len(cards))}


def preference_summary(profile):
    """Review supplied values only. Missing information is never a default preference."""
    b=profile.get('budget',{}); h=profile.get('housing_preferences',{}); c=profile.get('commute',{})
    labels={'per_person':'per person','per_room':'per room','whole_property':'whole property',
        'private_room':'private room','shared_room':'shared room','student_accommodation':'student accommodation',
        'commute':'commute','cost':'cost','housing':'housing','amenities':'facilities',
        'private_bedroom':'private bedroom','private_bathroom':'private bathroom','furnished':'furnishings',
        'laundry':'laundry','kitchen_access':'kitchen','public_transport':'public transport',
        'walk':'walking','drive':'driving','bike':'cycling'}
    result=[]
    budget=[]
    for key,name in (('preferred','preferred'),('maximum','maximum')):
        if key in b: budget.append(f"{name} {b[key]:g} AUD/week")
    if 'scope' in b: budget.append(labels[b['scope']])
    if 'includes_bills' in b: budget.append('bills included' if b['includes_bills'] else 'bills excluded')
    if 'hard_limit' in b: budget.append('hard limit' if b['hard_limit'] else 'flexible')
    if budget: result.append('Budget: '+'; '.join(budget)+'.')
    living=[]
    if 'occupants' in profile: living.append(f"{profile['occupants']} occupants")
    if 'rental_mode' in profile: living.append(labels.get(profile['rental_mode'],profile['rental_mode']))
    if living: result.append('Housing: '+'; '.join(living)+'.')
    rooms=[]
    if 'suburb' in h: rooms.append(h['suburb'] or 'Any suburb')
    for key,name in (('min_bedrooms','bedrooms'),('min_bathrooms','bathrooms'),('min_car_spaces','parking spaces')):
        if h.get(key) is not None: rooms.append(f"{name} unrestricted" if h[key]==0 else f"At least {h[key]} {name}")
    if rooms: result.append('Property requirements: '+'; '.join(rooms)+'.')
    commute=[]
    if 'destination_id' in profile: commute.append('Destination '+profile['destination_id'])
    if 'modes' in c: commute.append(', '.join(labels[k] for k in c['modes']))
    for key,name in (('preferred_minutes','preferred'),('maximum_minutes','maximum')):
        if key in c: commute.append(f"{name} {c[key]:g} minutes")
    if 'hard_limit' in c: commute.append('hard limit' if c['hard_limit'] else 'flexible')
    if commute: result.append('Commute: '+'; '.join(commute)+'.')
    dates=profile.get('move_in_window',{})
    if dates: result.append('Move-in: '+dates.get('from','Not supplied')+' to '+dates.get('to','Not supplied')+'.')
    if 'lease_months' in profile: result.append(f"Lease term: {profile['lease_months']:g} months.")
    if 'hard_requirements' in profile:
        result.append('Required features: '+(', '.join(labels[k] for k in profile['hard_requirements']) or 'No additional requirements')+'.')
    for key,name in (('soft_preferences','Preferences'),('weights','weight')):
        if profile.get(key): result.append(name+': '+', '.join(labels.get(k,k)+f' {v:g}' for k,v in profile[key].items())+'.')
    if profile.get('student_commute'):
        from ..commute.usyd import MODE_LABELS
        student=profile['student_commute']
        parts=[MODE_LABELS[student['mode']],f"At most {student['maximum_minutes']} minutes one way"]
        if student.get('travel_day'):parts.append('Weekdays' if student['travel_day']=='weekday' else 'Weekends')
        if student.get('travel_date'):parts.append(student['travel_date'])
        if student.get('max_transfers') is not None:parts.append(f"At most {student['max_transfers']} transfers")
        result.append('USYD main campus: '+', '.join(parts)+'.')
    result.append('Unspecified details are left blank and do not constrain the search.')
    return result


def filter_summary(filters):
    labels={'suburb':'Suburb','min_bedrooms':'Minimum bedrooms','min_bathrooms':'Minimum bathrooms','min_car_spaces':'Minimum parking spaces','max_weekly_rent':'Maximum listing weekly rent AUD','sort':'Sort','usyd_mode':'Travel mode','usyd_max_minutes':'Maximum minutes to USYD','usyd_arrival_time':'Arrival time','usyd_travel_day':'Travel day','usyd_travel_date':'Travel date','usyd_max_transfers':'Maximum transfers'}
    orders={'rent_asc':'Weekly rent: low to high','rent_desc':'Weekly rent: high to low','bedrooms_desc':'Bedrooms: high to low'}
    from ..commute.usyd import MODE_LABELS
    return ', '.join(labels[k]+' '+(orders[v] if k=='sort' else MODE_LABELS.get(v,str(v)) if k=='usyd_mode' else {'weekday':'Weekdays','weekend':'Weekends'}.get(v,str(v)) if k=='usyd_travel_day' else str(v)) for k,v in filters.items()) or 'All listings'


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
        if row.get('usyd_commute'):
            record=row['usyd_commute']
            result[-1]['usyd_commute']={'destination':record['destination']['label'],
                'straight_line_distance_m':record['straight_line_distance_m'],
                'reference_arrival_at':record.get('reference_arrival_at'),
                'modes':{key:{'minutes':r['duration_minutes'],'basis':r['status']} for key,r in record['modes'].items()}}
    return result


def history_context(conversation,identifiers):
    allowed=set(identifiers)
    return [{'role':m['role'],'content':m['content'][:3000],
        'listing_ids':[r['listing_id'] for r in m['listings'] if r['listing_id'] in allowed],
        'display_order':[{'position':index+1,'listing_id':r['listing_id']}
            for index,r in enumerate(m['listings']) if r['listing_id'] in allowed]}
        for m in conversation['messages'][-20:]]
