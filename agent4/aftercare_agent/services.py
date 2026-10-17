"""Deterministic UC07/UC08 rules. Storage commits the whole result atomically."""
from copy import deepcopy
from .contracts import day, instant
from .errors import require
from .model_gateway import draft_follow_up
from .planner import SYDNEY, build_plan, confirm_schedule, due_on, propose_schedule
from .reminders import TERMINAL, deliver_due, sync_reminders


def check_refs(case, refs):
    known = {e['evidence_id'] for e in case['evidence']}
    require(set(refs) <= known, 'missing_evidence', 'An evidence reference is not registered in this case')


def check_tenancy(case, tenancy):
    require(tenancy['tenant_id'] == case['tenant_id'], 'case_mismatch', 'Tenancy belongs to another tenant')
    rooms = tenancy['rooms'] or []
    items = tenancy['inventory'] or []
    require(len({r['id'] for r in rooms}) == len(rooms), 'invalid_input', 'Room IDs must be unique')
    require(len({i['id'] for i in items}) == len(items), 'invalid_input', 'Inventory IDs must be unique')
    require(all(i['room_id'] in {r['id'] for r in rooms} for i in items), 'case_mismatch', 'Inventory references an unknown room')
    require(tenancy['furnished'] is not False or not items, 'invalid_input', 'An unfurnished property cannot include supplied furniture')
    check_refs(case, tenancy['baseline_evidence_refs'])


def add_evidence(case, item, now):
    require(instant(item['recorded_at']) <= instant(now), 'invalid_input', 'Evidence cannot be dated in the future')
    existing = next((e for e in case['evidence'] if e['evidence_id'] == item['evidence_id']), None)
    require(existing is None or existing == item, 'evidence_conflict', 'Evidence IDs are immutable; use a new ID/version for corrections')
    if existing is None:
        case['evidence'].append(deepcopy(item))


def invalidate_drafts(case, reason):
    if case['bond']:
        for draft in case['bond']['drafts']:
            if draft['status'] == 'current':
                draft.update(status='superseded', invalidation_reason=reason)


def pending_reviews(case):
    return [r for r in case['reviews'] if r['status'] == 'open']


def ensure_review(case, key, reason, refs, now):
    previous = next((r for r in pending_reviews(case) if r['reason_key'] == key), None)
    if previous:
        return previous
    review = {'review_id': f"review-{len(case['reviews'])+1}", 'reason_key': key,
              'reason': reason, 'source_refs': refs, 'status': 'open', 'created_at': now,
              'decisions': [], 'closed_at': None}
    case['reviews'].append(review)
    invalidate_drafts(case, 'Review gate opened')
    if case['bond'] and case['bond']['state'] not in TERMINAL | {'Draft'}:
        case['bond']['state'] = 'UnderReview'
    return review


def bond_open(case, active=True):
    bond = case['bond']
    require(bond is not None, 'invalid_state', 'Open a bond case first')
    require(bond['state'] not in TERMINAL, 'case_closed', 'Closed bond cases are read-only')
    require(not active or bond['state'] != 'Draft', 'invalid_state', 'Activate the bond case first')
    return bond


def record_entry(case, entry, now):
    bond = case['bond']
    require(instant(entry['occurred_at']) <= instant(now), 'invalid_input', 'Reported event cannot be in the future')
    check_refs(case, entry['evidence_refs'])
    incoming = entry['claims']
    ids = {c['claim_id'] for c in bond['claims']}
    require(len({c['claim_id'] for c in incoming}) == len(incoming), 'invalid_input', 'Duplicate claim IDs in update')
    require(not ids.intersection(c['claim_id'] for c in incoming), 'duplicate_claim', 'Claim IDs are immutable; reference corrections in a new dated update')
    saved = deepcopy(entry)
    saved.update(entry_id=f"entry-{len(bond['history'])+1}", recorded_at=now)
    bond['history'].append(saved)
    for claim in incoming:
        check_refs(case, claim['evidence_refs'])
        saved_claim = deepcopy(claim)
        saved_claim.update(classification='reported_claim', entry_id=saved['entry_id'], currency='AUD')
        bond['claims'].append(saved_claim)
        if claim['disputed']:
            ensure_review(case, 'claim:' + claim['claim_id'], 'Tenant disputes reported deduction: ' + claim['reason'],
                          ['claim:' + claim['claim_id']] + claim['evidence_refs'], now)
    if entry['conflicting_evidence']:
        ensure_review(case, 'conflict:' + saved['entry_id'], 'Tenant reports conflicting evidence',
                      ['history:' + saved['entry_id']] + entry['evidence_refs'], now)
    bond['state'] = 'UnderReview' if pending_reviews(case) else 'AwaitingOutcome'
    invalidate_drafts(case, 'A new reported update was recorded')


def new_case(command):
    p = command['payload']
    case = {'schema_version': '1.0', 'case_id': command['case_id'], 'tenant_id': command['actor_id'],
            'version': 0, 'tenancy': deepcopy(p['tenancy']), 'evidence': [], 'plan': None, 'bond': None,
            'reviews': [], 'reminders_enabled': False, 'reminders': [], 'audit': [],
            'created_at': command['as_of'], 'updated_at': command['as_of'], 'data_mode': 'local_prototype'}
    for item in p['evidence']:
        add_evidence(case, item, command['as_of'])
    check_tenancy(case, case['tenancy'])
    return case


def apply(case, command, *, gateway=None, property_only=False):
    """Mutate an in-memory transaction copy; never persist partially completed work."""
    op, p, now = command['operation'], command['payload'], command['as_of']
    require(instant(now) >= instant(case['updated_at']), 'stale_time', 'as_of precedes the last committed command')
    if case['bond'] and case['bond']['state'] in TERMINAL:
        require(op == 'poll_reminders', 'case_closed', 'Closed cases are retained read-only')
    result = {'operation': op}
    if op == 'create':
        pass
    elif op == 'add_evidence':
        add_evidence(case, p['evidence'], now)
        invalidate_drafts(case, 'New evidence was registered')
    elif op == 'revise_tenancy':
        require(case['plan'] is None or case['plan']['state'] == 'Draft', 'invalid_state', 'Revise tenancy only before plan confirmation')
        require(case['bond'] is None or case['bond']['state'] == 'Draft', 'invalid_state', 'Active bond context cannot be replaced')
        check_tenancy(case, p['tenancy'])
        require(p['tenancy']['tenancy_id'] == case['tenancy']['tenancy_id'] and
                (p['tenancy']['source_version'] > case['tenancy']['source_version'] or
                 property_only and p['tenancy']['source_version'] == case['tenancy']['source_version']),
                'case_mismatch', 'Keep tenancy_id and increase source_version (M3 property-only enrichment preserves confirmation version)')
        case['tenancy'] = deepcopy(p['tenancy'])
        if case['plan']:
            old = case['plan']
            updated = build_plan(case['tenancy'], old['move_out_date'], False, now)
            by_id = {t['task_id']: t for t in old['tasks']}
            for task in updated['tasks']:
                if task['task_id'] in by_id:
                    task['status'] = by_id[task['task_id']]['status']
                    task['evidence_refs'] = by_id[task['task_id']]['evidence_refs']
            updated['revisions'] = old['revisions'] + [{'tasks': old['tasks'], 'at': now, 'reason': 'tenancy correction'}]
            case['plan'] = updated
    elif op == 'create_plan':
        require(case['plan'] is None, 'invalid_state', 'A plan already exists; edit it instead')
        case['plan'] = build_plan(case['tenancy'], p['move_out_date'], p['schedule_confirmed'], now)
    elif op in {'confirm_plan', 'edit_task', 'propose_date', 'confirm_date', 'cancel_plan'}:
        plan = case['plan']
        require(plan is not None and plan['state'] != 'Cancelled', 'invalid_state', 'No editable plan')
        if op == 'confirm_plan':
            require(not plan['clarification_requests'], 'needs_clarification', '; '.join(plan['clarification_requests']))
            plan.update(state='Active', schedule_confirmed=True)
        elif op == 'edit_task':
            task = next((t for t in plan['tasks'] if t['task_id'] == p['task_id']), None)
            require(task is not None, 'invalid_input', 'Unknown plan task')
            check_refs(case, p['evidence_refs'])
            task['status'] = p['status']
            task['evidence_refs'] = sorted(set(task['evidence_refs'] + p['evidence_refs']))
            if 'title' in p:
                task['title'] = p['title']
            if 'due_date' in p:
                require(plan['pending_schedule'] is None, 'invalid_state', 'Resolve the pending schedule before editing dates')
                task['offset_days'] = (day(p['due_date']) - day(plan['move_out_date'])).days
                task['due_at'] = due_on(plan['move_out_date'], task['offset_days'])
            if p.get('review_reason'):
                ensure_review(case, 'plan:' + task['task_id'], p['review_reason'], task['evidence_refs'], now)
        elif op == 'propose_date':
            propose_schedule(plan, p['move_out_date'])
        elif op == 'confirm_date':
            confirm_schedule(plan, p['accepted'], now)
        else:
            plan.update(state='Cancelled', cancellation={'at': now, 'reason': p['reason']})
        invalidate_drafts(case, 'Plan or schedule changed')
    elif op == 'open_bond':
        require(case['bond'] is None or case['bond']['state'] == 'Draft', 'invalid_state', 'Bond case is already active')
        if p['deposit_evidence_ref']:
            check_refs(case, [p['deposit_evidence_ref']])
            item = next(e for e in case['evidence'] if e['evidence_id'] == p['deposit_evidence_ref'])
            require(item['kind'] == 'deposit_record', 'invalid_input', 'Deposit evidence must be a deposit_record')
        if case['bond'] is None:
            case['bond'] = {'state': 'Draft', 'history': [], 'claims': [], 'drafts': [],
                            'follow_up_at': None, 'outcome': None, 'closed_at': None}
        case['bond'].update(bond_reference=p['bond_reference'], deposit_evidence_ref=p['deposit_evidence_ref'])
    elif op in {'activate_bond', 'bond_update'}:
        bond = bond_open(case, active=op == 'bond_update')
        if op == 'activate_bond':
            require(bond['state'] == 'Draft', 'invalid_state', 'Already activated')
            require(bond['bond_reference'] or bond['deposit_evidence_ref'], 'needs_clarification', 'A bond reference or deposit record is required')
        record_entry(case, p['entry'], now)
    elif op == 'request_draft':
        bond = bond_open(case)
        require(bond['state'] != 'UnderReview' and not pending_reviews(case), 'review_required', 'Affected guidance is blocked pending explicit operator release')
        draft = draft_follow_up(case, use_model=p['use_model'], allow_external_ai=p['allow_external_ai'], gateway=gateway)
        invalidate_drafts(case, 'A newer draft was requested')
        draft.update(draft_id=f"draft-{len(bond['drafts'])+1}", created_at=now,
                     based_on_version=case['version'], saved_at_version=case['version']+1, status='current')
        bond['drafts'].append(draft)
        result['draft'] = deepcopy(draft)
    elif op == 'operator_decision':
        review = next((r for r in pending_reviews(case) if r['review_id'] == p['review_id']), None)
        require(review is not None, 'invalid_state', 'No open review with that ID')
        require(p['decision'] == 'release' or p['gate_resolved'] is False, 'invalid_input', 'Only release can resolve a gate')
        require(p['decision'] != 'release' or p['gate_resolved'] is True, 'review_required', 'Explicit resolved gate is required for release')
        review['decisions'].append({**deepcopy(p), 'operator_id': command['actor_id'], 'at': now})
        if p['decision'] == 'release':
            review.update(status='released', closed_at=now)
        if case['bond'] and case['bond']['state'] not in {'Draft'} | TERMINAL:
            case['bond']['state'] = 'UnderReview' if pending_reviews(case) else 'AwaitingOutcome'
        invalidate_drafts(case, 'Operator recorded a review decision')
    elif op in {'confirm_outcome', 'withdraw'}:
        bond = bond_open(case, active=op == 'confirm_outcome')
        if op == 'confirm_outcome':
            check_refs(case, p['evidence_refs'])
        bond.update(state='Resolved' if op == 'confirm_outcome' else 'Withdrawn',
                    outcome={**deepcopy(p), 'recorded_at': now, 'actor_id': command['actor_id']}, closed_at=now)
        for review in pending_reviews(case):
            review.update(status='closed_by_tenant', closed_at=now, closure_reason=op)
        invalidate_drafts(case, 'Tenant confirmed closure')
    elif op == 'reminder_preferences':
        if p['follow_up_at']:
            bond_open(case)
            require(instant(p['follow_up_at']) >= instant(now), 'invalid_input', 'Choose a future follow-up time')
        case['reminders_enabled'] = p['enabled']
        if case['bond']:
            case['bond']['follow_up_at'] = instant(p['follow_up_at']).astimezone(SYDNEY).isoformat() if p['follow_up_at'] else None
    elif op == 'poll_reminders':
        result['delivered'] = deliver_due(case, now)
    else:
        require(False, 'invalid_input', 'Unsupported operation')
    sync_reminders(case)
    case['version'] += 1
    case['updated_at'] = now
    case['audit'].append({'request_id': command['request_id'], 'operation': op, 'actor_id': command['actor_id'],
                          'actor_role': command['actor_role'], 'at': now, 'version': case['version']})
    return result
