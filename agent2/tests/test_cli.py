import copy
import html
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_engine import ROOT, dataset, listing, profile
from rental_agent.engine import evaluate


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'rental_agent/report.py').exists(), '报告模块尚未实现')
        from rental_agent.report import compare_reports, render_markdown
        self.render = render_markdown
        self.compare = compare_reports

    def test_markdown_contains_report_and_evidence(self):
        report = evaluate(profile(), dataset(listing(), listing('B', rent_amount=900), listing('C', bills_included=None)))
        output = self.render(report)
        for value in ['模拟数据', 'Top 5', '88.60', '待确认', '排除', 'fixture:A#rent_amount', '通勤', '预算', '2026-09-17']:
            self.assertIn(value, html.unescape(output))
        self.assertEqual(output, self.render(report))

    def test_markdown_escapes_untrusted_text(self):
        item = listing('X|<script>\n标题')
        output = self.render(evaluate(profile(), dataset(item)))
        self.assertNotIn('<script>', output)
        self.assertIn('&#124;', output)

    def test_valid_route_walk_and_transfers_are_visible(self):
        report = evaluate(profile(), dataset(listing()))
        row = report['recommendations'][0]
        self.assertEqual(row.get('walking_minutes'), 5)
        self.assertEqual(row.get('transfers'), 0)
        output = self.render(report)
        self.assertIn('步行 5.00 分钟', output)
        self.assertIn('换乘 0 次', output)

    def test_escape_roundtrip(self):
        from rental_agent.report import safe
        original = "X|_'#<script>&[link](url)`*"
        self.assertEqual(html.unescape(safe(original)), original)

    def test_compare_changes_and_input_not_mutated(self):
        data = json.loads((ROOT / 'data/demo/listings.json').read_text(encoding='utf-8'))
        p = json.loads((ROOT / 'data/demo/profiles/commute.json').read_text(encoding='utf-8'))
        q = json.loads((ROOT / 'data/demo/profiles/budget.json').read_text(encoding='utf-8'))
        before, after = evaluate(p, data), evaluate(q, data)
        original = copy.deepcopy(before)
        comparison = self.compare(before, after)
        self.assertTrue(any(row['rank_change'] for row in comparison['rows']))
        self.assertEqual(len(comparison['rows']), 30)
        self.assertEqual(before, original)
        after['comparison'] = comparison
        self.assertIn('偏好调整前后', self.render(after))

    def test_compare_mismatched_data_or_time_rejected(self):
        from rental_agent.validation import ValidationError
        before = evaluate(profile(), dataset(listing()))
        for field in ['dataset_fingerprint', 'as_of']:
            other = copy.deepcopy(before)
            other[field] = 'different'
            with self.assertRaises(ValidationError):
                self.compare(before, other)

    def test_no_matches_rendered_without_fabrication(self):
        report = evaluate(profile(), dataset(listing(rent_amount=999)))
        output = self.render(report)
        self.assertIn('没有满足完整条件的候选', output)
        self.assertIn('未自动放宽', output)

    def test_uc04_tighter_budget_changes_eligibility(self):
        data = dataset(listing())
        p, q = profile(), profile()
        q['budget']['maximum'] = 500
        comparison = self.compare(evaluate(p, data), evaluate(q, data))
        row = comparison['rows'][0]
        self.assertEqual((row['before_status'], row['after_status']), ('eligible', 'excluded'))
        self.assertIsNone(row['rank_change'])

    def test_uc04_unchanged_profile_keeps_ranking(self):
        report = evaluate(profile(), dataset(listing()))
        comparison = self.compare(report, report)
        self.assertEqual(comparison['changed_fields'], [])
        self.assertEqual(comparison['rows'][0]['rank_change'], 0)
        self.assertEqual(comparison['rows'][0]['score_change'], 0)

    def test_uc04_new_destination_does_not_reuse_old_route(self):
        p = profile()
        before = evaluate(p, dataset(listing()))
        p['destination_id'] = 'new-campus'
        comparison = self.compare(before, evaluate(p, dataset(listing())))
        self.assertEqual(comparison['rows'][0]['after_status'], 'pending')

    def test_saved_examples_match_current_code(self):
        data = json.loads((ROOT / 'data/demo/listings.json').read_text(encoding='utf-8'))
        expected = {}
        for name in ['commute', 'budget', 'housing']:
            p = json.loads((ROOT / f'data/demo/profiles/{name}.json').read_text(encoding='utf-8'))
            expected[name] = evaluate(p, data)
        expected['comparison'] = copy.deepcopy(expected['budget'])
        expected['comparison']['comparison'] = self.compare(expected['commute'], expected['budget'])
        for name, report in expected.items():
            with self.subTest(name=name):
                self.assertEqual(json.loads((ROOT / f'reports/{name}.json').read_text(encoding='utf-8')), report)
                self.assertEqual((ROOT / f'reports/{name}.md').read_text(encoding='utf-8'), self.render(report))


class CLITests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'rental_agent/__main__.py').exists(), '命令行入口尚未实现')

    def command(self, *args):
        return subprocess.run([sys.executable, '-m', 'rental_agent', *args], cwd=ROOT,
                              text=True, capture_output=True)

    def test_uc03_uc04_export_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = str(Path(temp) / 'result')
            args = ['--profile', 'data/demo/profiles/commute.json', '--listings', 'data/demo/listings.json', '--output', prefix]
            first = self.command(*args)
            self.assertEqual(first.returncode, 0, first.stderr)
            saved = Path(prefix + '.md').read_bytes()
            report = json.loads(Path(prefix + '.json').read_text(encoding='utf-8'))
            self.assertEqual(len(report['recommendations']), 5)
            self.assertEqual(sum(report['counts'][k] for k in ['eligible', 'pending', 'excluded', 'duplicates']), 30)
            second = self.command(*args)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(Path(prefix + '.md').read_bytes(), saved)

    def test_uc04_optional_compare(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = str(Path(temp) / 'comparison')
            result = self.command('--profile', 'data/demo/profiles/commute.json', '--listings', 'data/demo/listings.json',
                                  '--compare-profile', 'data/demo/profiles/budget.json', '--output', prefix)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(Path(prefix + '.json').read_text(encoding='utf-8'))
            self.assertIn('comparison', report)
            self.assertNotEqual(report['comparison']['before_weights'], report['comparison']['after_weights'])

    def test_bad_json_returns_error_without_output(self):
        with tempfile.TemporaryDirectory() as temp:
            invalid = Path(temp) / 'invalid.json'
            invalid.write_text('{bad json', encoding='utf-8')
            prefix = str(Path(temp) / 'result')
            result = self.command('--profile', str(invalid), '--listings', 'data/demo/listings.json', '--output', prefix)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse(Path(prefix + '.json').exists())

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            invalid = Path(temp) / 'invalid.json'
            invalid.write_text('{"schema_version":"1.0", "schema_version":"2.0"}', encoding='utf-8')
            result = self.command('--profile', str(invalid), '--listings', 'data/demo/listings.json', '--output', str(Path(temp) / 'result'))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('重复', result.stderr)

    def test_help(self):
        result = self.command('--help')
        self.assertEqual(result.returncode, 0)
        self.assertIn('--compare-profile', result.stdout)


if __name__ == '__main__':
    unittest.main()
