"""Regression tests for pasted input, version comparisons and late reports."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preference_agent.acceptance_demo import run_acceptance_demo
from preference_agent.bridge import AGENT2, compare_reports, evaluate
from preference_agent.cli import ConversationUI, export_case
from preference_agent.comparison import compare_current, compare_tasks, render_comparison, task_history
from preference_agent.fields import flatten
from preference_agent.handover import HandoverService, LocalSupervisor
from preference_agent.llm import ExtractionError, ManualOnly
from preference_agent.service import PreferenceAgent
from preference_agent.store import Store


class ComparisonRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'state.sqlite3')
        self.agent = PreferenceAgent(self.store, ManualOnly())
        self.case = self.agent.startCollection()['case_id']
        self.values = flatten(json.loads((AGENT2 / 'data/demo/profiles/commute.json').read_text(encoding='utf-8')))
        self.data = json.loads((AGENT2 / 'data/demo/listings.json').read_text(encoding='utf-8'))
        self.handover = HandoverService(self.store)
        self.ui = ConversationUI(self.agent, self.handover, self.case, 'TEST_ACTOR')
        self.agent.setFields(self.case, self.values)

    def confirm(self):
        review = self.agent.reviewDraft(self.case)
        return self.agent.confirmProfile(self.case, review['confirmation_token'], 'TEST_ACTOR')

    def search(self, data=None):
        return self.handover.submitConfirmed(self.case, data or self.data)

    def test_pasted_output_preserves_confirmation_and_cached_task(self):
        self.confirm()
        task = self.search()
        before = self.store.load(self.case)
        for line in ('You > /search', 'Agent1 > {', 'Operation not completed: example'):
            with self.assertRaisesRegex(ValueError, 'Paste commands only'):
                self.ui.execute(line)
        for line in ('{', '"task_id": "example",', '}', 'change my budget to 900'):
            self.ui.execute(line)
        self.assertEqual(self.store.load(self.case), before)
        self.assertEqual(self.search(), task)

    def test_offline_text_preserves_review_and_does_not_confirm_revision(self):
        self.confirm()
        self.agent.setFields(self.case, {'budget.maximum': 500})
        self.agent.reviewDraft(self.case)
        before = self.store.load(self.case)
        self.ui.execute('accidental text')
        self.assertEqual(self.store.load(self.case), before)
        with self.assertRaises(ValueError):
            self.search()

    def test_recover_legacy_error_preserves_version_and_task(self):
        original = self.confirm()
        task = self.search()
        with patch.object(self.agent.llm, 'extractRequirements', side_effect=ExtractionError('unused')):
            session, serial = self.store.load(self.case)
            session.update(state='ProcessingError', last_error='Offline input rejected')
            self.store.save(session, serial)
        self.ui.execute('/recover-confirmed')
        self.assertEqual(self.store.profile(self.case, 1), original)
        self.assertEqual(self.agent.showDraft(self.case)['latest_version'], 1)
        self.assertEqual(self.search(), task)

    def test_recovery_cannot_discard_revised_draft(self):
        self.confirm()
        self.agent.setFields(self.case, {'budget.maximum': 500})
        session, serial = self.store.load(self.case)
        session['state'] = 'ProcessingError'
        self.store.save(session, serial)
        with self.assertRaisesRegex(ValueError, 'contains revisions'):
            self.ui.execute('/recover-confirmed')
        with self.assertRaises(ValueError):
            self.search()

    def test_weight_comparison_export_is_english_and_reports_immutable(self):
        self.confirm()
        first = self.search()
        budget = json.loads((AGENT2 / 'data/demo/profiles/budget.json').read_text(encoding='utf-8'))
        self.agent.setFields(self.case, flatten(budget))
        with self.assertRaises(ValueError):
            self.ui.execute('/compare')
        self.confirm()
        second = self.search()
        bundle = compare_current(self.store, self.case, 1)
        rows = bundle['raw_comparison']['rows']
        self.assertEqual(len(rows), 30)
        row = next(r for r in rows if r['listing_id'] == 'DEMO-002')
        self.assertEqual((row['before_rank'], row['after_rank']), (9, 3))
        self.assertEqual(second['report']['recommendations'][0]['listing_id'], 'DEMO-012')
        text = self.ui.execute('/compare 1')
        self.assertIn('DEMO-030', text)
        self.assertIn('Dimension contributions', text)
        self.assertIsNone(re.search(r'[\u3400-\u9fff]', text))
        self.assertEqual(text, render_comparison(bundle))
        target = Path(self.tmp.name) / 'export'
        export_case(self.store, self.case, target)
        self.assertEqual(json.loads((target / 'comparison.json').read_text(encoding='utf-8')), bundle['raw_comparison'])
        self.assertIsNone(re.search(r'[\u3400-\u9fff]', (target / 'comparison.en.json').read_text(encoding='utf-8')))
        self.assertEqual(self.store.task(first['task_id']), first)
        self.assertEqual(self.store.task(second['task_id']), second)

    def test_tight_budget_and_missing_route_do_not_rank_ineligible_candidates(self):
        self.confirm()
        self.search()
        self.agent.setFields(self.case, {'budget.maximum': 500})
        self.confirm()
        self.search()
        row = next(r for r in compare_current(self.store, self.case)['english_comparison']['rows']
                   if r['listing_id'] == 'DEMO-001')
        self.assertEqual((row['before_status'], row['after_status']), ('eligible', 'excluded'))
        self.assertIsNone(row['after_rank'])
        self.assertIsNone(row['after_score'])
        self.assertIn('budget', ' '.join(row['change_reasons']))
        self.agent.setFields(self.case, {'destination_id': 'new-campus'})
        self.confirm()
        self.search()
        row = next(r for r in compare_current(self.store, self.case)['english_comparison']['rows']
                   if r['listing_id'] == 'DEMO-006')
        self.assertEqual((row['before_status'], row['after_status']), ('eligible', 'pending'))
        self.assertIsNone(row['after_score'])
        self.assertIsNone(row['after_rank'])
        self.assertIn('commute', ' '.join(row['change_reasons']))

    def test_cross_snapshot_error_is_visible_in_cli_and_export(self):
        self.confirm()
        self.search()
        self.agent.setFields(self.case, {'budget.maximum': 500})
        self.confirm()
        other = deepcopy(self.data)
        other['as_of'] = '2026-09-18T09:00:00+10:00'
        self.search(other)
        with self.assertRaisesRegex(ValueError, 'different data snapshot'):
            self.ui.execute('/compare 1')
        folder = Path(self.tmp.name) / 'different-snapshot'
        self.assertIn('Comparison unavailable', export_case(self.store, self.case, folder))
        self.assertFalse((folder / 'comparison.json').exists())
        context = json.loads((folder / 'export-context.json').read_text(encoding='utf-8'))
        self.assertIn('different data snapshot', context['comparison_error'])

    def test_cross_search_and_assessment_time_are_rejected(self):
        self.confirm()
        task = self.search()
        before = task['report']
        after = deepcopy(before)
        after['search_id'] = 'another-search'
        with self.assertRaisesRegex(ValueError, 'different searches'):
            compare_reports(before, after)
        after = deepcopy(before)
        after['as_of'] = '2026-09-18T09:00:00+10:00'
        with self.assertRaisesRegex(ValueError, 'assessment times'):
            compare_reports(before, after)
        other_case = self.agent.startCollection()['case_id']
        with self.assertRaisesRegex(ValueError, 'this case'):
            compare_tasks(self.store, other_case, task['task_id'], task['task_id'])

    def test_wrong_run_id_is_rejected_at_receiver(self):
        self.confirm()
        def wrong(profile, dataset):
            report = evaluate(profile, dataset)
            report['recommendation_run_id'] = 'rr-' + '0' * 64
            return report
        task = HandoverService(self.store, LocalSupervisor(self.store, wrong)).submitConfirmed(self.case, self.data)
        self.assertEqual(task['status'], 'failed')
        self.assertIsNone(task['report'])

    def test_tampered_saved_report_is_not_compared(self):
        self.confirm()
        first = self.search()
        self.agent.setFields(self.case, {'budget.maximum': 500})
        self.confirm()
        self.search()
        bad = deepcopy(first)
        bad['report']['recommendation_run_id'] = 'rr-' + '0' * 64
        with self.store.transaction() as db:
            self.store.save_task(bad, db)
        with self.assertRaises(ValueError):
            compare_current(self.store, self.case)

    def test_late_old_result_remains_historical_after_new_version_completes(self):
        self.confirm()
        new_tasks = []
        def delayed(profile, dataset):
            self.agent.setFields(self.case, {'budget.maximum': 500})
            self.confirm()
            new_tasks.append(self.search())
            return evaluate(profile, dataset)
        old = HandoverService(self.store, LocalSupervisor(self.store, delayed)).submitConfirmed(self.case, self.data)
        new = new_tasks[0]
        session = self.agent.showDraft(self.case)
        self.assertEqual(session['latest_task_id'], new['task_id'])
        self.assertEqual(session['latest_version'], 2)
        bindings = {r['task_id']: r['binding'] for r in task_history(self.store, self.case)}
        self.assertEqual(bindings[old['task_id']], 'historical')
        self.assertEqual(bindings[new['task_id']], 'current_confirmed_version')
        self.assertEqual(compare_current(self.store, self.case)['after_task_id'], new['task_id'])

    def test_acceptance_demo_runs_end_to_end(self):
        fake_path = str(Path(self.tmp.name) / 'preference_agent' / 'acceptance_demo.py')
        with patch('preference_agent.acceptance_demo.__file__', fake_path):
            result = run_acceptance_demo(self.store)
        self.assertTrue(all(v == 'passed' for v in result['checks'].values()))
        self.assertTrue((Path(result['output_directory']) / 'v4-new-campus/comparison.md').is_file())


if __name__ == '__main__':
    unittest.main()
