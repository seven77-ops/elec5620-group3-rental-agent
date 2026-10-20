"""Reproducible local acceptance scenario; not a team review or live-LLM test."""
from copy import deepcopy
import json
from pathlib import Path
from .bridge import AGENT2
from .cli import ConversationUI, export_case, task_summary
from .comparison import compare_current, task_history
from .fields import flatten
from .handover import HandoverService
from .llm import ManualOnly
from .service import PreferenceAgent


def run_acceptance_demo(store):
    agent = PreferenceAgent(store, ManualOnly())
    handover = HandoverService(store)
    case = agent.startCollection()['case_id']
    ui = ConversationUI(agent, handover, case, 'SCRIPTED_ACCEPTANCE_ACTOR')
    data = json.loads((AGENT2 / 'data/demo/listings.json').read_text(encoding='utf-8'))
    values = flatten(json.loads((AGENT2 / 'data/demo/profiles/commute.json').read_text(encoding='utf-8')))
    root = Path(__file__).resolve().parents[1] / 'reports' / ('acceptance-' + case)
    checks = {}

    def require(name, condition):
        if not condition:
            raise AssertionError('Acceptance check failed: ' + name)
        checks[name] = 'passed'

    def must_block(name, action):
        try:
            action()
        except ValueError:
            checks[name] = 'passed'
        else:
            raise AssertionError('Expected blocked action: ' + name)

    def confirm_and_search():
        review = agent.reviewDraft(case)
        agent.confirmProfile(case, review['confirmation_token'], 'SCRIPTED_ACCEPTANCE_ACTOR')
        return handover.submitConfirmed(case, data)

    agent.setFields(case, values)
    must_block('unconfirmed_search_blocked', lambda: handover.submitConfirmed(case, data))
    first = confirm_and_search()
    require('normal_counts', first['report']['counts'] ==
            {'input': 30, 'eligible': 15, 'pending': 9, 'excluded': 5, 'duplicates': 1})
    require('commute_top1', first['report']['recommendations'][0]['listing_id'] == 'DEMO-006')
    previous = deepcopy(store.profile(case, 1))
    unchanged = deepcopy(agent.showDraft(case))
    must_block('pasted_prompt_rejected', lambda: ui.execute('You > /search'))
    ui.execute('accidentally pasted output')
    require('offline_text_preserves_session', agent.showDraft(case) == unchanged)
    repeat = handover.submitConfirmed(case, data)
    require('duplicate_request_reused', repeat == first and repeat['attempts'] == 1)
    export_case(store, case, root / 'v1-commute')

    agent.setFields(case, {'weights.commute': 0.15, 'weights.cost': 0.6,
                           'weights.housing': 0.15, 'weights.amenities': 0.1})
    must_block('revision_requires_confirmation', lambda: handover.submitConfirmed(case, data))
    require('old_result_marked_outdated', task_history(store, case)[0]['binding'] == 'outdated_for_current_draft')
    second = confirm_and_search()
    comparison = compare_current(store, case)
    require('budget_top1', second['report']['recommendations'][0]['listing_id'] == 'DEMO-012')
    row = next(r for r in comparison['raw_comparison']['rows'] if r['listing_id'] == 'DEMO-002')
    require('demo002_rank_9_to_3', (row['before_rank'], row['after_rank']) == (9, 3))
    require('all_candidates_compared', len(comparison['raw_comparison']['rows']) == 30)
    export_case(store, case, root / 'v2-budget-priority')

    agent.setFields(case, {'budget.maximum': 500})
    third = confirm_and_search()
    comparison3 = compare_current(store, case)
    require('tight_budget_loses_eligibility', any(r['before_status'] == 'eligible' and r['after_status'] == 'excluded'
                                               for r in comparison3['raw_comparison']['rows']))
    export_case(store, case, root / 'v3-tight-budget')

    agent.setFields(case, {'destination_id': 'new-campus'})
    fourth = confirm_and_search()
    comparison4 = compare_current(store, case)
    require('missing_route_becomes_pending', any(r['before_status'] == 'eligible' and r['after_status'] == 'pending'
                                                and r['after_score'] is None and r['after_rank'] is None
                                                for r in comparison4['raw_comparison']['rows']))
    require('original_version_preserved', store.profile(case, 1) == previous)
    export_case(store, case, root / 'v4-new-campus')
    result = {'mode': 'scripted_acceptance_no_live_llm', 'case_id': case, 'checks': checks,
              'tasks': [task_summary(t) for t in (first, second, third, fourth)],
              'output_directory': str(root.resolve()),
              'scope': 'Local synthetic scenario only. Joint testing and Sprint Review remain pending.'}
    (root / 'acceptance-summary.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
