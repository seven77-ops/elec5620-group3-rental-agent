"""Read-only case progress: which agent produced what, and what each handoff carried (SR01/SR02).

The founder/operator and the tenant can see the whole one-person-company pipeline in one place.
Nothing here changes a case; each step only reports saved state and its references.
"""
from ..settings import TENANT

DONE, ACTIVE, WAITING, TODO = 'done', 'in_progress', 'waiting', 'not_started'
LISTING_PAGE = 'recommendations'


def _step(key, agent, title, status, summary, refs=(), page=None):
    return {'key': key, 'agent': agent, 'title': title, 'status': status, 'summary': summary,
            'refs': [r for r in refs if r], 'page': page}


class ProgressAdapter:
    def __init__(self, ctx):
        self.ctx = ctx

    def progress(self, case_id: str):
        repo = self.ctx.repo
        with repo.transaction() as db:
            case = self.ctx.get(db, 'case', case_id)
            reviews = [repo.get(db, 'review', r['review_id']) for r in case.get('reviews') or []]
            drafts = repo.get(db, 'lease_draft_index', case_id) or []
        steps = []
        confirmations = case.get('confirmations') or []
        latest = confirmations[-1] if confirmations else None
        steps.append(_step(
            'requirements', 'Agent 1 · 需求顾问', '确认租房需求',
            DONE if latest else ACTIVE,
            f"已确认需求 v{len(confirmations)}（{latest.get('confirmed_at', '')[:10]}）" if latest
            else '等待租客填写并确认需求；未回答的项保持未知，不会被自动补全。',
            [f"profile v{len(confirmations)}", f"search {case.get('search_id')}" if latest else None],
            'assistant'))

        runs = case.get('evaluations') or []
        selection = case.get('selection')
        steps.append(_step(
            'listings', 'Agent 2 · 房源分析', '筛选并比较房源',
            DONE if runs else (TODO if not latest else ACTIVE),
            f"已基于需求 v{runs[-1].get('profile_version')} 生成 {len(runs)} 次推荐；广告事实保留来源，未核实项不会当作已确认。"
            if runs else '需求确认后，按预算、房型和到悉大通勤时间筛选 1000 套真实房源快照。',
            [runs[-1].get('run_id') if runs else None], LISTING_PAGE))

        if selection:
            snapshot = selection.get('listing_snapshot') or {}
            summary = (f"租客已明确选定 {snapshot.get('address', selection.get('listing_id'))}"
                       f"（需求 v{selection.get('profile_version')}）；选定不代表已核实在租或已签约。")
            steps.append(_step('selection', '租客决定', '选定跟进房源', DONE, summary,
                               [selection.get('listing_id'), selection.get('recommendation_run_id')], LISTING_PAGE))
        else:
            steps.append(_step('selection', '租客决定', '选定跟进房源', WAITING if runs else TODO,
                               '由租客本人选定房源；系统不会替租客做选择。', (), LISTING_PAGE))

        review = reviews[-1]['review'] if reviews and reviews[-1] else None
        if review:
            high = [f for f in review.get('findings', []) if f.get('severity') == 'high']
            status = {'Reviewed': DONE, 'Questions Ready': DONE, 'Awaiting Human Review': WAITING}.get(review['status'], ACTIVE)
            summary = (f"合同复核 v{review['version']}：{review['status']}，发现 {len(review.get('findings', []))} 项"
                       f"（高风险 {len(high)} 项），规则包 {review.get('rule_pack', {}).get('version')}。")
            refs = [f"{review['review_id']}@v{review['version']}"]
        elif drafts:
            status, summary, refs = ACTIVE, f'已保存 {len(drafts)} 份未签署租约草稿；上传合同并单独同意后进行复核。', ()
        else:
            status = TODO if not selection else WAITING
            summary, refs = '选定房源后，可按 NSW 官方模板生成草稿，或在单独同意后上传合同复核。', ()
        steps.append(_step('contract', 'Agent 3 · 合同助手', '合同草稿与复核', status, summary, refs, 'contract'))

        aftercare_id = case.get('aftercare_case_id')
        record = self.ctx.aftercare.get(aftercare_id, TENANT) if aftercare_id else None
        open_reviews = [r for r in (record or {}).get('reviews', []) if r['status'] == 'open']
        pending_contract = [r for r in reviews if r and r['review']['status'] == 'Awaiting Human Review']
        waiting = len(open_reviews) + len(pending_contract)
        steps.append(_step(
            'operator', '运营者（唯一的人类）', '人工审核与放行',
            WAITING if waiting else (DONE if (record and record.get('reviews')) or reviews else TODO),
            f'有 {waiting} 项待人工处理：合同高风险 {len(pending_contract)} 项，押金/退租争议 {len(open_reviews)} 项。'
            if waiting else '争议、证据冲突和高风险合同会进入这里；只有运营者明确放行才解除门禁。',
            (), 'operator'))

        if record:
            plan, bond = record.get('plan'), record.get('bond')
            parts = [f"租约资料 v{record['tenancy']['source_version']}（来源：{record['tenancy']['source_ref']}）"]
            if plan:
                done = sum(t['status'] == 'done' for t in plan['tasks'])
                parts.append(f"退租计划 {plan['state']}，{done}/{len(plan['tasks'])} 项完成")
            if bond:
                parts.append(f"押金跟进 {bond['state']}")
            closed = bool(bond and bond['state'] in ('Resolved', 'Withdrawn'))
            steps.append(_step('aftercare', 'Agent 4 · 租后与退租', '退租计划与押金跟进',
                               DONE if closed else ACTIVE, '；'.join(parts) + '。',
                               [f"{aftercare_id}@v{record['version']}"], 'aftercare?tab=moveout'))
        else:
            steps.append(_step('aftercare', 'Agent 4 · 租后与退租', '退租计划与押金跟进', TODO,
                               '租客明确确认实际租约资料后创建；可从合同复核或已选房源带入，已入住的租客也可以直接进入。',
                               (), 'aftercare?tab=moveout'))
        return {'case_id': case_id, 'steps': steps,
                'note': '每一步只读取已保存的结果；交接以案例编号、版本和用户确认为准，不在 Agent 之间自由对话。'}
