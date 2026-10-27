"""Translate confirmed preferences into supported advertisement facts, without inventing costs."""
POLICY = 'confirmed-facts-1.4-usyd-ranges'


def preference_context(profile, catalog, legacy=False):
    if legacy:
        from .profile import supplied_profile
        profile = supplied_profile(profile)
    housing = profile.get('housing_preferences') or {}
    filters = {key:housing[key] for key in ('suburb','min_bedrooms','min_bathrooms','min_car_spaces')
               if housing.get(key) is not None}
    notes = ['是否仍在租、入住日期、租期与可容纳人数待核实。',
             '到校时间见逐套房源的计划时刻或路网估算；独立卧卫、家具和设施仍需核实，不使用虚构综合分数。',
             '租赁方式和广告计价对象待核实；不把整租广告自动认定为单间或按人报价。']
    student=profile.get('student_commute')
    if student:
        filters.update(usyd_mode=student['mode'],usyd_max_minutes=student['maximum_minutes'])
        for key in ('arrival_time','travel_day','travel_date','max_transfers'):
            if student.get(key) is not None:filters['usyd_'+key]=student[key]
        notes.insert(0,'到校通勤按每套房源的悉大主校区标注筛选；公共交通是所列工作日基准时刻，出行前请按课程时间复核。')
    budget = profile.get('budget',{})
    if 'maximum' not in budget:
        notes.insert(0,'尚未填写预算上限，暂不按价格排除房源。')
    elif budget.get('hard_limit') is not False and housing.get('budget_match_mode','advertised_amount') == 'advertised_amount':
        filters['max_weekly_rent'] = budget['maximum']
        notes.insert(0, f"偏好默认按预算金额 AUD {budget['maximum']:g}/周粗筛广告标价；计价对象与账单待核实，不代表已满足个人或含账单预算。")
    elif budget.get('hard_limit') is not False:
        notes.insert(0,'选择仅在计价对象一致时筛预算；当前广告计价对象未知，暂不应用预算上限，全部列为待核实。')
    else:
        notes.insert(0,'最高预算为可协商条件，暂不排除超预算广告；计价对象与账单待核实。')
    return {'filters':catalog.filters(filters), 'unverified_preferences':notes, 'mapping_policy':POLICY}
