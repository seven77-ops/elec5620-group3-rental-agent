"""Durable, opt-in in-app inbox; every poll recomputes eligibility inside the write transaction."""
from hashlib import sha256
from .contracts import instant

TERMINAL = {'Resolved', 'Withdrawn'}


def desired_reminders(case):
    if not case['reminders_enabled'] or (case['bond'] and case['bond']['state'] in TERMINAL):
        return []
    result = []
    plan = case['plan']
    if plan and plan['state'] == 'Active' and plan['pending_schedule'] is None:
        result += [('plan:' + t['task_id'], t['due_at'], t['title'])
                   for t in plan['tasks'] if t['status'] == 'todo']
    bond = case['bond']
    if bond and bond['state'] in {'AwaitingOutcome', 'UnderReview'} and bond['follow_up_at']:
        result.append(('bond', bond['follow_up_at'], 'Check your bond record; record any actual outcome yourself'))
    return result


def sync_reminders(case):
    wanted = {}
    for owner, due, title in desired_reminders(case):
        key = 'rm-' + sha256((case['case_id'] + '|' + owner + '|' + due).encode()).hexdigest()[:20]
        wanted[key] = {'reminder_id': key, 'owner': owner, 'due_at': due, 'title': title,
                       'state': 'scheduled', 'delivered_at': None}
    old = {r['reminder_id']: r for r in case['reminders']}
    for key, reminder in old.items():
        if key not in wanted:
            reminder['state'] = 'suppressed'
        elif reminder['state'] == 'suppressed':
            reminder['state'] = 'delivered' if reminder['delivered_at'] else 'scheduled'
    for key, reminder in wanted.items():
        old.setdefault(key, reminder)
    case['reminders'] = list(old.values())


def deliver_due(case, now):
    sync_reminders(case)
    delivered = []
    for reminder in case['reminders']:
        if reminder['state'] == 'scheduled' and instant(reminder['due_at']) <= instant(now):
            reminder.update(state='delivered', delivered_at=now)
            delivered.append(dict(reminder))
    return delivered
