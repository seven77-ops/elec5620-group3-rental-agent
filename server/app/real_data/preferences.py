"""Translate confirmed preferences into supported advertisement facts, without inventing costs."""
POLICY = 'confirmed-facts-1.1'


def preference_context(profile, catalog):
    housing = profile.get('housing_preferences') or {}
    filters = {key:housing[key] for key in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces')
               if housing.get(key) is not None}
    notes = ['是否仍在租、入住日期、租期与可容纳人数待核实。',
             '通勤时间、独立卧卫、家具和设施未完成核实；四维权重尚不用于综合评分。',
             '租赁方式和广告计价对象待核实；不把整租广告自动认定为单间或按人报价。']
    budget = profile['budget']
    if budget['hard_limit'] and housing.get('budget_match_mode','advertised_amount') == 'advertised_amount':
        filters['max_weekly_rent'] = budget['maximum']
        notes.insert(0, f"偏好默认按预算金额 AUD {budget['maximum']:g}/周粗筛广告标价；计价对象与账单待核实，不代表已满足个人或含账单预算。")
    elif budget['hard_limit']:
        notes.insert(0,'选择仅在计价对象一致时筛预算；当前广告计价对象未知，暂不应用预算上限，全部列为待核实。')
    else:
        notes.insert(0,'最高预算为可协商条件，暂不排除超预算广告；计价对象与账单待核实。')
    return {'filters':catalog.filters(filters), 'unverified_preferences':notes, 'mapping_policy':POLICY}
