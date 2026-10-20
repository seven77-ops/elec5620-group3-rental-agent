"""ConversationUI: terminal interface suitable for PyCharm's Run console."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from .bridge import AGENT2
from .report import render_english_report
from .fields import FIELDS
from .handover import HandoverService, coordination_envelope
from .llm import LLMService, ManualOnly, load_env
from .service import PreferenceAgent
from .store import Store
from .comparison import compare_current, render_comparison, task_history

ROOT = Path(__file__).resolve().parents[1]
HELP = '''
Describe your rental requirements (requires a configured LLM). For offline entry, use /set or /load.
/show                       Show the current draft
/fields                     Show supported fields and value types
/set budget.maximum 550     Edit a field; use JSON values and double-quoted strings
/set budget.period "week"   Specify the budget period
/set preferred_locations null  Explicitly mark a preference as undecided
/load examples/demo-draft.json Load the example as a draft; this does not confirm it
/review                     Validate and show the draft, limitations and confirmation token
/confirm TOKEN              Confirm and save the reviewed revision; this does not start a search
/search [DATASET.json]       Submit the confirmed version; defaults to the fixed Agent2 demo dataset
/retry                      Reconcile and retry the current task using the same task ID
/history                    Show saved tasks and whether their results are current or historical
/compare [BEFORE_VERSION]    Compare an earlier report with the current confirmed result
/recover-confirmed          Dismiss a failed input if the confirmed draft is unchanged
/feedback                   Explain a zero-eligible result without changing preferences
/revise                     Start a revision after a zero-eligible result; preserve the old version
/export [NEW_DIRECTORY]     Export the confirmed profile, handover metadata and results
/cancel                     Cancel this session and block further collection or searches
/quit                       Exit; resume later with --case CASE_ID
/help                       Show this help
'''


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def pretty(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)


def export_case(store, case_id, directory):
    session, _ = store.load(case_id)
    if not session['latest_version']:
        raise ValueError('No confirmed profile to export.')
    record = store.profile(case_id, session['latest_version'])
    task = store.task(session['latest_task_id']) if session['latest_task_id'] else None
    envelope = coordination_envelope(record, task) if task else None
    history = task_history(store, case_id)
    comparison = None
    comparison_error = None
    if session['state'] == 'Confirmed' and task and task['status'] == 'completed':
        try:
            comparison = compare_current(store, case_id, optional=True)
        except ValueError as exc:
            comparison_error = str(exc)
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'rental-profile.json').write_text(pretty(record['profile']), encoding='utf-8')
    (folder / 'confirmation.json').write_text(pretty(record), encoding='utf-8')
    (folder / 'export-context.json').write_text(pretty({
        'session_state': session['state'], 'exported_confirmed_version': record['profileVersion'],
        'tasks': history, 'comparison_error': comparison_error}), encoding='utf-8')
    if task:
        (folder / 'handoff.json').write_text(pretty(envelope), encoding='utf-8')
        (folder / 'handover.json').write_text(pretty({k: v for k, v in task.items() if k not in ('dataset', 'report')}), encoding='utf-8')
        if task['status'] == 'completed':
            (folder / 'recommendations.json').write_text(pretty(task['report']), encoding='utf-8')
            (folder / 'recommendations.md').write_text(render_english_report(task['report']), encoding='utf-8')
    if comparison:
        (folder / 'comparison.json').write_text(pretty(comparison['raw_comparison']), encoding='utf-8')
        (folder / 'comparison.en.json').write_text(pretty(comparison['english_comparison']), encoding='utf-8')
        (folder / 'comparison.md').write_text(render_comparison(comparison), encoding='utf-8')
    result = str(folder.resolve())
    if comparison_error:
        result += '\nComparison unavailable: ' + comparison_error
    return result


def task_summary(task):
    result = {'task_id': task['task_id'], 'status': task['status'],
              'receipt_acknowledged': task['accepted_at'] is not None, 'attempts': task['attempts']}
    if task['status'] == 'completed':
        result.update(counts=task['report']['counts'],
                      recommendations=[{'listing_id': r['listing_id'], 'score': r['score']}
                                       for r in task['report']['recommendations']])
    else:
        result['error'] = task['last_error']
    return result


class ConversationUI:
    def __init__(self, agent, handover, case_id, tenant):
        self.agent, self.handover, self.case_id, self.tenant = agent, handover, case_id, tenant

    def execute(self, line):
        if line.strip().startswith(('You >', 'Agent1 >', 'Operation not completed:')):
            raise ValueError('Paste commands only, without You > or Agent1 > prompts. Preferences are unchanged.')
        command, _, arg = line.strip().partition(' ')
        arg = arg.strip()
        if command == '/help':
            return HELP
        if command == '/fields':
            return pretty(FIELDS)
        if command == '/history':
            return pretty(task_history(self.agent.store, self.case_id))
        if command == '/compare':
            try:
                version = int(arg) if arg else None
            except ValueError:
                raise ValueError('Usage: /compare [EARLIER_VERSION_NUMBER]') from None
            return render_comparison(compare_current(self.agent.store, self.case_id, version))
        if command == '/recover-confirmed':
            return self.agent.recoverConfirmed(self.case_id)
        if command == '/show':
            s = self.agent.showDraft(self.case_id)
            s['draft'].pop('evidence', None)
            return pretty({k: s[k] for k in ('case_id', 'state', 'latest_version', 'draft')})
        if command == '/set':
            field, sep, raw = arg.partition(' ')
            if not sep:
                raise ValueError('Usage: /set FIELD JSON_VALUE')
            return self.agent.setFields(self.case_id, {field: json.loads(raw)})['reply']
        if command == '/load':
            path = Path(arg)
            if not path.is_absolute() and not path.exists():
                path = ROOT / path
            return self.agent.setFields(self.case_id, load_json(path))['reply']
        if command == '/review':
            review = self.agent.reviewDraft(self.case_id)
            review['draft'].pop('evidence', None)
            return pretty(review)
        if command == '/confirm':
            record = self.agent.confirmProfile(self.case_id, arg, self.tenant)
            return f"Confirmed version {record['profileVersion']} saved. Use /search to submit it to local Agent2."
        if command == '/search':
            path = Path(arg) if arg else AGENT2 / 'data/demo/listings.json'
            return pretty(task_summary(self.handover.submitConfirmed(self.case_id, load_json(path))))
        if command in ('/retry', '/feedback', '/revise'):
            s = self.agent.showDraft(self.case_id)
            task_id = s['latest_task_id']
            if not task_id:
                raise ValueError('No task exists for this confirmed version.')
            if command == '/retry':
                return pretty(task_summary(self.handover.reconcileRetry(task_id)))
            return pretty(self.agent.reviseAfterNoMatch(self.case_id, task_id, accept=command == '/revise'))
        if command == '/export':
            directory = arg or ROOT / 'reports' / (self.case_id + '-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
            return export_case(self.agent.store, self.case_id, directory)
        if command == '/cancel':
            return self.agent.cancel(self.case_id)
        if command.startswith('/'):
            raise ValueError('Unknown command. Use /help.')
        return self.agent.processMessage(self.case_id, line)['reply']

    def run(self):
        print('Agent1 - Tenant Advice and Preferences (local course prototype)')
        print(f'Case: {self.case_id}\nResume later with --case {self.case_id}.')
        print(HELP)
        while True:
            try:
                line = input('You > ').strip()
                if line == '/quit':
                    break
                if line:
                    print('Agent1 >', self.execute(line))
            except (EOFError, KeyboardInterrupt):
                print('\nYour session has been retained.')
                break
            except (ValueError, OSError, sqlite3.Error) as exc:
                print('Operation not completed:', exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Member 1 preference collection and Agent2 local integration')
    parser.add_argument('--db', default=str(ROOT / 'state/agent1.sqlite3'))
    parser.add_argument('--case', help='Resume a case printed by a previous run')
    parser.add_argument('--tenant', default='local-tenant', help='Local label only, not authenticated identity')
    parser.add_argument('--manual', action='store_true', help='Offline manual input; no natural-language extraction')
    parser.add_argument('--demo', action='store_true', help='Scripted synthetic demonstration; no LLM calls')
    parser.add_argument('--acceptance-demo', action='store_true', help='Offline confirmation, retry and version-comparison checks')
    args = parser.parse_args(argv)
    load_env(ROOT / '.env')
    store = Store(args.db)
    if args.acceptance_demo:
        from .acceptance_demo import run_acceptance_demo
        print(pretty(run_acceptance_demo(store)))
        return 0
    if args.demo:
        from .demo import run_demo
        print(pretty(run_demo(store)))
        return 0
    agent = PreferenceAgent(store, ManualOnly() if args.manual else LLMService())
    case_id = args.case or agent.startCollection()['case_id']
    agent.showDraft(case_id)  # fail early if a requested case does not exist
    ConversationUI(agent, HandoverService(store), case_id, args.tenant).run()
    return 0
