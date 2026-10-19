"""Scripted integration demo. This is not a live-LLM quality test."""
import json
from pathlib import Path
from .bridge import AGENT2
from .cli import export_case, task_summary
from .fields import flatten
from .handover import HandoverService
from .service import PreferenceAgent


class ScriptedDemoLLM:
    def __init__(self, turns):
        self.turns = iter(turns)

    def extractRequirements(self, text, draft, history=()):
        values = next(self.turns)
        return {'updates': [{'field': k, 'value': v, 'evidence': text} for k, v in values.items()], 'issues': []}


def run_demo(store):
    values = flatten(json.loads((AGENT2 / 'data/demo/profiles/commute.json').read_text(encoding="utf-8-sig")))
    # Deliberately incomplete, then explicit clarification; no invented defaults.
    first = {k: v for k, v in values.items() if k != 'budget.period'}
    agent = PreferenceAgent(store, ScriptedDemoLLM([first, {'budget.period': 'week'}]))
    handover = HandoverService(store)
    case = agent.startCollection()['case_id']
    initial = agent.processMessage(case, 'SCRIPTED DEMO: all example preferences except budget period.')
    clarified = agent.processMessage(case, 'SCRIPTED DEMO: budget is per week.')
    review = agent.reviewDraft(case)
    saved = agent.confirmProfile(case, review['confirmation_token'], 'SCRIPTED_DEMO_ACTOR_NOT_A_REAL_TENANT')
    data = json.loads((AGENT2 / 'data/demo/listings.json').read_text(encoding="utf-8-sig"))
    task = handover.submitConfirmed(case, data)
    retry = handover.reconcileRetry(task['task_id'])
    assert task['task_id'] == retry['task_id'] and retry['attempts'] == 1
    root = Path(__file__).resolve().parents[1] / 'reports' / ('demo-' + case)
    export_case(store, case, root / 'v1')
    agent.setFields(case, {'budget.preferred': 1, 'budget.maximum': 1})
    review2 = agent.reviewDraft(case)
    agent.confirmProfile(case, review2['confirmation_token'], 'SCRIPTED_DEMO_ACTOR_NOT_A_REAL_TENANT')
    no_match = handover.submitConfirmed(case, data)
    feedback = agent.reviseAfterNoMatch(case, no_match['task_id'], accept=True)
    assert feedback['revision_started']
    export_case(store, case, root / 'v2')
    assert store.profile(case, 1) == saved
    return {'mode': 'scripted_demo_no_live_llm', 'case_id': case,
            'first_turn_state': initial['state'], 'clarified_state': clarified['state'],
            'v1_task': task_summary(task), 'v2_task': task_summary(no_match),
            'no_match_feedback': feedback, 'original_version_preserved': True,
            'output_directory': str(root)}
