"""Read-only case progress: which agent produced what, and what each handoff carried (SR01/SR02).

The founder/operator and the tenant can see the whole one-person-company pipeline in one place.
Nothing here changes a case; each step only reports saved state and its references.
"""
from ..settings import TENANT

DONE, ACTIVE, WAITING, TODO = 'done', 'in_progress', 'waiting', 'not_started'
LISTING_PAGE = 'recommendations'
STATE_NAMES = {'Reviewed': 'Reviewed', 'Questions Ready': 'Questions ready', 'Awaiting Human Review': 'Awaiting human review',
               'Awaiting Resubmission': 'Awaiting resubmission', 'Degraded Summary Only': 'Limited summary only',
               'Draft': 'Draft', 'Active': 'Active', 'Cancelled': 'Cancelled', 'AwaitingOutcome': 'Awaiting outcome',
               'UnderReview': 'Under review', 'Resolved': 'Outcome confirmed', 'Withdrawn': 'Withdrawn'}


def _name(state):
    return STATE_NAMES.get(state, state)


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
            'requirements', 'Agent 1 · Rental adviser', 'Confirm rental requirements',
            DONE if latest else ACTIVE,
            f"Confirmed requirements v{len(confirmations)} ({latest.get('confirmed_at', '')[:10]})" if latest
            else 'Waiting for the tenant to complete and confirm requirements. Unanswered fields remain unknown.',
            [f"profile v{len(confirmations)}", f"search {case.get('search_id')}" if latest else None],
            'assistant'))

        runs = case.get('evaluations') or []
        selection = case.get('selection')
        steps.append(_step(
            'listings', 'Agent 2 · Listing analysis', 'Filter and compare listings',
            DONE if runs else (TODO if not latest else ACTIVE),
            f"Generated {len(runs)} recommendation runs using requirements v{runs[-1].get('profile_version')}. Advertisement facts retain their sources and unverified details remain unconfirmed."
            if runs else 'After requirements are confirmed, filter 1000 live listing snapshots by budget, property requirements and commute to USYD.',
            [runs[-1].get('run_id') if runs else None], LISTING_PAGE))

        if selection:
            snapshot = selection.get('listing_snapshot') or {}
            summary = (f"The tenant explicitly selected {snapshot.get('address', selection.get('listing_id'))}"
                       f" (requirements v{selection.get('profile_version')}). Selection does not establish verified availability or a signed tenancy.")
            steps.append(_step('selection', 'Tenant decision', 'Select follow-up property', DONE, summary,
                               [selection.get('listing_id'), selection.get('recommendation_run_id')], LISTING_PAGE))
        else:
            steps.append(_step('selection', 'Tenant decision', 'Select follow-up property', WAITING if runs else TODO,
                               'The tenant selects the property personally. The system does not choose for them.', (), LISTING_PAGE))

        review = reviews[-1]['review'] if reviews and reviews[-1] else None
        if review:
            high = [f for f in review.get('findings', []) if f.get('severity') == 'high']
            status = {'Reviewed': DONE, 'Questions Ready': DONE, 'Awaiting Human Review': WAITING}.get(review['status'], ACTIVE)
            summary = (f"Contract review v{review['version']}: {_name(review['status'])}, {len(review.get('findings', []))} findings"
                       f" ({len(high)} high risk), rule pack {review.get('rule_pack', {}).get('version')}.")
            refs = [f"{review['review_id']}@v{review['version']}"]
        elif drafts:
            status, summary, refs = ACTIVE, f'Saved {len(drafts)} unsigned lease drafts. Upload a contract and provide separate consent for review.', ()
        else:
            status = TODO if not selection else WAITING
            summary, refs = 'After selecting a property, generate a draft using the official NSW template, or upload a contract for review with separate consent.', ()
        steps.append(_step('contract', 'Agent 3 · Contract assistant', 'Contract drafts and review', status, summary, refs, 'contract'))

        aftercare_id = case.get('aftercare_case_id')
        record = self.ctx.aftercare.get(aftercare_id, TENANT) if aftercare_id else None
        open_reviews = [r for r in (record or {}).get('reviews', []) if r['status'] == 'open']
        pending_contract = [r for r in reviews if r and r['review']['status'] == 'Awaiting Human Review']
        waiting = len(open_reviews) + len(pending_contract)
        steps.append(_step(
            'operator', 'Operator (human reviewer)', 'Human review and approval',
            WAITING if waiting else (DONE if (record and record.get('reviews')) or reviews else TODO),
            f'{waiting} items await human review: {len(pending_contract)} high-risk contract items and {len(open_reviews)} bond or move-out disputes.'
            if waiting else 'Disputes, conflicting evidence and high-risk contracts appear here. Only explicit operator approval clears the gate.',
            (), 'operator'))

        if record:
            plan, bond = record.get('plan'), record.get('bond')
            parts = [f"Tenancy details v{record['tenancy']['source_version']} (source: {record['tenancy']['source_ref']})"]
            if plan:
                done = sum(t['status'] == 'done' for t in plan['tasks'])
                parts.append(f"Move-out plan {_name(plan['state'])}, {done}/{len(plan['tasks'])} tasks completed")
            if bond:
                parts.append(f"Bond follow-up {_name(bond['state'])}")
            closed = bool(bond and bond['state'] in ('Resolved', 'Withdrawn'))
            steps.append(_step('aftercare', 'Agent 4 · Aftercare and move-out', 'Move-out plan and bond follow-up',
                               DONE if closed else ACTIVE, '; '.join(parts) + '.',
                               [f"{aftercare_id}@v{record['version']}"], 'aftercare?tab=moveout'))
        else:
            steps.append(_step('aftercare', 'Agent 4 · Aftercare and move-out', 'Move-out plan and bond follow-up', TODO,
                               'Created after the tenant explicitly confirms actual tenancy details. Import from contract review or the selected property, or enter directly for an existing tenancy.',
                               (), 'aftercare?tab=moveout'))
        return {'case_id': case_id, 'steps': steps,
                'note': 'Each step reads saved results only. Handoffs use case identifiers, versions and user confirmation rather than free-form agent conversations.'}
