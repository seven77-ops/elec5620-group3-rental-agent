"""Translate confirmed preferences into supported advertisement facts, without inventing costs."""
POLICY = 'confirmed-facts-1.5-usyd-duration'


def preference_context(profile, catalog, legacy=False):
    if legacy:
        from .profile import supplied_profile
        profile = supplied_profile(profile)
    housing = profile.get('housing_preferences') or {}
    filters = {key:housing[key] for key in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces')
               if housing.get(key) is not None}
    notes = ['Availability, move-in date, lease term and capacity remain unverified.',
             'Campus travel times use per-listing scheduled routes or road-network estimates. Private rooms, bathrooms, furnishings and facilities still need checks. No invented aggregate scores are used.',
             'Rental mode and advertised rent scope remain unverified. Whole-property advertisements are not automatically treated as room or per-person prices.']
    student=profile.get('student_commute')
    if student:
        filters.update(usyd_mode=student['mode'],usyd_max_minutes=student['maximum_minutes'])
        for key in ('max_transfers',):
            if student.get(key) is not None:filters['usyd_'+key]=student[key]
        notes.insert(0,'Campus commute filters use each listing reference route or estimated range. These are approximate durations, independent of class times or specific services.')
    budget = profile.get('budget',{})
    if 'maximum' not in budget:
        notes.insert(0,'No budget limit is supplied. Listings are not excluded by price.')
    elif budget.get('hard_limit') is not False and housing.get('budget_match_mode','advertised_amount') == 'advertised_amount':
        filters['max_weekly_rent'] = budget['maximum']
        notes.insert(0, f"Preferences use AUD {budget['maximum']:g}/week to filter advertised rent provisionally. Rent scope and bills remain unverified; this does not establish a personal or bills-inclusive budget match.")
    elif budget.get('hard_limit') is not False:
        notes.insert(0,'Budget filtering requires matching rent scopes. Advertisement scopes are unknown, so the budget limit is not applied and all remain unverified.')
    else:
        notes.insert(0,'The maximum budget is flexible, so above-budget advertisements are retained. Rent scope and bills remain unverified.')
    return {'filters':catalog.filters(filters), 'unverified_preferences':notes, 'mapping_policy':POLICY}
