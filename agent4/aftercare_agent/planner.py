"""Property-specific practical milestones. Offsets are preferences, never legal periods."""
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from .contracts import day
from .errors import require

SYDNEY = ZoneInfo('Australia/Sydney')


def due_on(move_out, offset):
    return datetime.combine(day(move_out) + timedelta(days=offset), time(9), SYDNEY).isoformat()


def build_plan(tenancy, move_out, confirmed, now):
    day(move_out)
    tasks = []
    def add(task_id, title, zone, offset, refs=()):
        tasks.append({'task_id': task_id, 'title': title, 'zone': zone, 'offset_days': offset,
                      'due_at': due_on(move_out, offset), 'status': 'todo', 'evidence_refs': [],
                      'baseline_refs': list(refs)})
    refs = tenancy['baseline_evidence_refs']
    gaps = []
    questions = []
    if not refs:
        gaps.append('Baseline condition report unavailable: supply records or document current condition.')
        add('baseline', 'Locate incoming condition records; record missing evidence', 'property', -14)
    if tenancy['rooms'] is None:
        questions.append('Room layout is unknown: confirm rooms before property-specific cleaning is finalised.')
    for room in tenancy['rooms'] or []:
        add('clean-' + room['id'], f"Clean {room['name']} and record its condition", room['id'], -2, refs)
    if tenancy['carpeted'] is True:
        add('carpet', 'Check and clean carpet as appropriate; document existing marks', 'property', -2, refs)
    elif tenancy['carpeted'] is None:
        questions.append('Confirm whether carpeted areas exist.')
    if tenancy['outdoor'] is True:
        add('outdoor', 'Clear belongings and tidy the supplied outdoor areas', 'outdoor', -2, refs)
    elif tenancy['outdoor'] is None:
        questions.append('Confirm whether outdoor areas exist.')
    if tenancy['furnished'] is True:
        if not tenancy['inventory'] or not tenancy['inventory_confirmed']:
            questions.append('Furnished inventory is unavailable or unconfirmed: verify it before finalising.')
            add('verify-inventory', 'Verify supplied furniture inventory and discrepancies', 'property', -7, refs)
        for item in tenancy['inventory'] or []:
            add('inventory-' + item['id'], f"Check supplied inventory: {item['name']}", item['room_id'], -2, refs)
    elif tenancy['furnished'] is None:
        questions.append('Confirm whether the property is furnished.')
    add('belongings', 'Remove belongings and arrange personal service/address changes', 'property', -1)
    add('inspection', 'Prepare final inspection photos and compare available condition records', 'property', -1, refs)
    add('keys', 'Arrange key return and retain a dated receipt', 'property', 0)
    require(confirmed is not True or not questions, 'needs_clarification', '; '.join(questions))
    return {'state': 'Active' if confirmed else 'Draft', 'move_out_date': move_out,
            'schedule_confirmed': confirmed, 'tasks': tasks, 'evidence_gaps': gaps,
            'clarification_requests': questions, 'pending_schedule': None, 'revisions': [], 'created_at': now,
            'notice_status': 'unverified_no_legal_countdown',
            'notice_question': 'Check applicable notice requirements and triggering facts against current official guidance.',
            'schedule_basis': 'User-confirmed practical planning offsets, not statutory deadlines.'}


def propose_schedule(plan, move_out):
    require(plan['state'] != 'Cancelled', 'invalid_state', 'The plan is cancelled')
    require(plan['pending_schedule'] is None, 'invalid_state', 'Confirm or reject the existing date proposal first')
    require(move_out != plan['move_out_date'], 'invalid_input', 'The date has not changed')
    plan['pending_schedule'] = {'move_out_date': move_out, 'changes': [
        {'task_id': t['task_id'], 'old_due_at': t['due_at'], 'new_due_at': due_on(move_out, t['offset_days'])}
        for t in plan['tasks']]}


def confirm_schedule(plan, accepted, now):
    pending = plan['pending_schedule']
    require(pending is not None, 'invalid_state', 'No proposed schedule')
    if accepted:
        plan['revisions'].append({'move_out_date': plan['move_out_date'], 'tasks': [dict(t) for t in plan['tasks']], 'at': now})
        plan['move_out_date'] = pending['move_out_date']
        for task in plan['tasks']:
            task['due_at'] = due_on(plan['move_out_date'], task['offset_days'])
    plan['pending_schedule'] = None
