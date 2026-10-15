"""Auditable Markdown rendering and the optional preference-comparison feature."""

import html

from .validation import DIMENSIONS, ValidationError


LABELS = {'commute': '通勤', 'cost': '费用', 'housing': '居住', 'amenities': '便利'}
STATES = {'eligible': '合格', 'pending': '待确认', 'excluded': '排除', 'duplicate': '重复'}


def safe(value):
    """Treat source text as text, never Markdown/HTML instructions or links."""
    value = str(value).replace('\n', ' ').replace('\r', ' ')
    # Escape each original character once; never re-escape an inserted entity.
    return ''.join(f'&#{ord(char)};' if char in '|`*_[]#\\' else html.escape(char, quote=True)
                   for char in value)


def numeric(value):
    return '未知' if value is None else f'{value:.2f}'


def comparison_details(a, b, before_weights, after_weights):
    """Explain displayed assessments; never turn partial contributions into a score."""
    reasons = [f"资格：{STATES[a['status']]} → {STATES[b['status']]}。"]
    left_checks, right_checks = a.get('hard_checks', {}), b.get('hard_checks', {})
    check_labels = {'pass': '满足', 'fail': '不满足', 'unknown': '待确认'}
    for key in sorted(left_checks.keys() | right_checks.keys()):
        left, right = left_checks.get(key), right_checks.get(key)
        if left != right:
            old = '未启用' if left is None else f"{check_labels[left['status']]}（{left['reason']}）"
            new = '未启用' if right is None else f"{check_labels[right['status']]}（{right['reason']}）"
            reasons.append(f'硬条件 {key}：{old} → {new}。')

    contributions = {}
    for key in DIMENSIONS:
        av, bv = a.get('score_breakdown', {}).get(key), b.get('score_breakdown', {}).get(key)
        aw, bw = before_weights[key], after_weights[key]
        # Unknown data has no contribution estimate unless its weight is zero.
        ac = 0.0 if aw == 0 else (None if av is None else round(av * aw, 4))
        bc = 0.0 if bw == 0 else (None if bv is None else round(bv * bw, 4))
        delta = None if ac is None or bc is None else round(bc - ac, 4)
        contributions[key] = {'before': ac, 'after': bc, 'change': delta}
        if a['status'] != 'duplicate' and (av != bv or aw != bw):
            change = '不可比较' if delta is None else f'{delta:+.4f}'
            reasons.append(f'{LABELS[key]}：分项 {numeric(av)} → {numeric(bv)}；'
                           f'有效权重 {aw:.1%} → {bw:.1%}；'
                           f'加权贡献 {numeric(ac)} → {numeric(bc)}（变化 {change}）。')

    if b['status'] in ('pending', 'excluded'):
        blockers = [f"{key}：{value['reason']}" for key, value in sorted(right_checks.items())
                    if value['status'] != 'pass'] + b.get('issues', [])
        if blockers:
            reasons.append('当前未排名依据：' + '；'.join(dict.fromkeys(blockers)) + '。')
        reasons.append('当前没有正式总分和排名；已知分项贡献不能代替完整评分。')
    elif b['status'] == 'duplicate':
        reasons.append('同来源且事实一致的重复记录，不独立评分或排名。')
    if a['rank'] is not None and b['rank'] is not None:
        if a['rank'] == b['rank']:
            reasons.append('名次不变；总分变化不必然导致名次变化。')
        else:
            reasons.append(f"名次 {a['rank']} → {b['rank']}；排名由全部合格候选的相对得分及 ID 决定。")
            if a['score'] == b['score']:
                reasons.append('本房源展示总分不变；名次变化需结合其他候选的资格和得分变化，不能归因为自身涨分。')
    return reasons, contributions


def compare_reports(before, after):
    """Compare all candidates, not only Top 5; do not mutate either evaluation."""
    if before['search_id'] != after['search_id']:
        raise ValidationError('comparison: 只能比较同一租房任务的偏好版本')
    if any(before[key] != after[key] for key in ('dataset_fingerprint', 'as_of', 'scoring_version', 'data_mode')):
        raise ValidationError('comparison: 只能比较同一数据快照、时点与评分版本')

    def index(report):
        rows = {r['listing_id']: r for group in ('eligible', 'pending_confirmation', 'excluded') for r in report[group]}
        rows.update({r['listing_id']: {'status': 'duplicate', 'rank': None, 'score': None} for r in report['duplicates']})
        return rows

    left, right = index(before), index(after)
    rows = []
    for identifier in sorted(left.keys() | right.keys()):
        a, b = left[identifier], right[identifier]
        rank_change = None if a['rank'] is None or b['rank'] is None else a['rank'] - b['rank']
        delta = None if a['score'] is None or b['score'] is None else round(b['score'] - a['score'], 4)
        reasons, contributions = comparison_details(a, b, before['effective_weights'], after['effective_weights'])
        rows.append({'listing_id': identifier, 'before_status': a['status'], 'after_status': b['status'],
                     'before_rank': a['rank'], 'after_rank': b['rank'], 'rank_change': rank_change,
                     'before_score': a['score'], 'after_score': b['score'], 'score_change': delta,
                     'change_reasons': reasons, 'score_contributions': contributions})
    changes = []

    def diff(a, b, prefix=''):
        for key in sorted(a.keys() | b.keys()):
            path = f'{prefix}.{key}' if prefix else key
            av, bv = a.get(key), b.get(key)
            if isinstance(av, dict) and isinstance(bv, dict):
                diff(av, bv, path)
            elif av != bv:
                changes.append({'field': path, 'before': av, 'after': bv})

    diff(before['profile'], after['profile'])
    return {'before_profile_version': before['profile_version'], 'after_profile_version': after['profile_version'],
            'before_run_id': before['recommendation_run_id'], 'after_run_id': after['recommendation_run_id'],
            'before_weights': dict(before['effective_weights']), 'after_weights': dict(after['effective_weights']),
            'changed_fields': changes, 'rows': rows,
            'note': '排名变化=原排名−新排名，正数表示上升；比较覆盖全部候选，仅合格项有正式排名。'
                    '加权贡献按报告展示的分项分数计算并舍入，合计与未舍入总分可能有微小差异；未知不等于零。'}


def render_markdown(report):
    p = report['profile']
    lines = ['# 悉尼租房评估报告（模拟数据）', '',
             '> 仅供课程演示；房源、通勤、设施和证据全部虚构，不可据此租房或签约。', '',
             f"评估快照：{safe(report['as_of'])}；评分版本：{safe(report['scoring_version'])}；偏好版本：{p['profile_version']}。", '',
             f"推荐批次 ID：{safe(report['recommendation_run_id'])}", '',
             '## 需求与结果概况', '',
             f"预算：AUD {p['budget']['preferred']:g}–{p['budget']['maximum']:g}/周，计价对象 {safe(p['budget']['scope'])}；含账单口径：{p['budget']['includes_bills']}。", '',
             f"目的地：{safe(p['destination_id'])}；到达时段：{safe(p['arrival_time'])}；期望/上限通勤：{p['commute']['preferred_minutes']:g}/{p['commute']['maximum_minutes']:g} 分钟。", '',
             '权重：' + '、'.join(f'{LABELS[k]} {report["effective_weights"][k]:.1%}' for k in DIMENSIONS) + '。', '',
             '数量：' + '；'.join(f'{k}={v}' for k, v in report['counts'].items()) + '。', '',
             '## Top 5 推荐', '',
             '| 排名 | 房源 | 可比周费用 AUD | 模拟通勤/分钟 | 超市直线距离/米 | 通勤/费用/居住/便利分 | 总分 |',
             '|---|---|---:|---:|---:|---|---:|']
    for row in report['recommendations']:
        scores = ' / '.join(numeric(row['score_breakdown'][k]) for k in DIMENSIONS)
        lines.append(f"| {row['rank']} | {safe(row['listing_id'])} | {numeric(row['weekly_cost'])} | {numeric(row['commute_minutes'])} | {numeric(row['supermarket_distance_m'])} | {scores} | {numeric(row['score'])} |")
    if not report['recommendations']:
        lines.extend(['', '没有满足完整条件的候选；未自动放宽预算、通勤或其他要求。'])
    for row in report['recommendations']:
        lines.extend(['', f"### {row['rank']}. {safe(row['listing_id'])}", '',
                      '- 推荐依据：' + safe('；'.join(row['reasons'])),
                      f"- 模拟路线补充：步行 {numeric(row['walking_minutes'])} 分钟；换乘 {row['transfers'] if row['transfers'] is not None else '未知'} 次。步行已包含在总通勤中，不重复加总。",
                      '- 取舍：' + safe('；'.join(row['tradeoffs']) or '已知评分项未超过舒适阈值；不代表房屋没有其他风险。'),
                      '- 最近来源核对：' + safe(row['last_checked_at'])])
    lines.extend(['', '## 待确认（不进入正式排名）', '',
                  '| 房源 | 分数可能范围 | 已知评分权重比例 | 硬条件待确认项 / 信息问题 |',
                  '|---|---|---:|---|'])
    for row in report['pending_confirmation']:
        why = [f"{k}: {v['reason']}" for k, v in row['hard_checks'].items() if v['status'] == 'unknown'] + row['issues']
        lines.append(f"| {safe(row['listing_id'])} | {row['score_range'][0]:.2f}–{row['score_range'][1]:.2f} | {row['evidence_coverage']:.0%} | {safe('；'.join(why))} |")
    lines.extend(['', '区间仅反映缺失评分项的可能贡献，不是统计置信区间；已知权重比例也不是可信概率。', '',
                  '## 排除', '', '| 房源 | 已知不满足的条件 |', '|---|---|'])
    for row in report['excluded']:
        why = [f"{k}: {v['reason']}" for k, v in row['hard_checks'].items() if v['status'] == 'fail']
        lines.append(f"| {safe(row['listing_id'])} | {safe('；'.join(why))} |")
    lines.extend(['', '## 重复记录', ''])
    lines.extend(f"- {safe(r['listing_id'])} → {safe(r['duplicate_of'])}：{safe(r['reason'])}" for r in report['duplicates'])
    if not report['duplicates']:
        lines.append('无。')
    lines.extend(['', '## 需要确认的问题', ''])
    lines.extend('- ' + safe(message) for message in report['clarification_requests'])
    if not report['clarification_requests']:
        lines.append('当前模拟快照没有阻止排名的待确认事项。')
    if 'comparison' in report:
        comp = report['comparison']
        lines.extend(['', '## 偏好调整前后', '', safe(comp['note']), '',
                      '本报告 Top 5 使用调整后的偏好；原始文件未被修改。', '',
                      '| 修改字段 | 调整前 | 调整后 |', '|---|---|---|'])
        for change in comp['changed_fields']:
            lines.append(f"| {safe(change['field'])} | {safe(change['before'])} | {safe(change['after'])} |")
        lines.extend(['', '| 房源 | 状态变化 | 原排名 | 新排名 | 排名变化 | 原分数 | 新分数 | 变化原因 |',
                      '|---|---|---:|---:|---:|---:|---:|---|'])
        for row in comp['rows']:
            reasons = row.get('change_reasons', ['旧报告未记录变化原因；请用原始偏好与快照重新生成比较。'])
            lines.append(f"| {safe(row['listing_id'])} | {STATES[row['before_status']]} → {STATES[row['after_status']]} | {row['before_rank'] or '—'} | {row['after_rank'] or '—'} | {row['rank_change'] if row['rank_change'] is not None else '—'} | {numeric(row['before_score'])} | {numeric(row['after_score'])} | {safe('；'.join(reasons))} |")
    lines.extend(['', '## 模拟证据索引', '',
                  'fixture: 是本地模拟记录定位符，不是真实网页。每个已使用字段的观测时间和来源也保存在同名 JSON 报告的 evidence_refs 中。', '',
                  '| 房源 | 已使用的字段证据 |', '|---|---|'])
    for row in report['eligible'] + report['pending_confirmation'] + report['excluded']:
        refs = '；'.join(e['source_ref'] for _, e in sorted(row['evidence_refs'].items()))
        lines.append(f"| {safe(row['listing_id'])} | {safe(refs)} |")
    lines.extend(['', '## 数据限制', ''])
    lines.extend('- ' + safe(message) for message in report['data_limitations'])
    return '\n'.join(lines) + '\n'
