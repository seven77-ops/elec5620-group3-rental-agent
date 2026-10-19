"""Regression checks for English presentation and Windows text-file decoding."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from preference_agent.bridge import AGENT2, evaluate
from preference_agent.cli import HELP
from preference_agent.demo import run_demo
from preference_agent.fields import assess, flatten
from preference_agent.report import render_english_report
from preference_agent.store import Store


class EnglishReleaseTests(unittest.TestCase):
    def test_authored_source_and_documentation_are_english_and_reads_are_explicit(self):
        paths = list((ROOT / 'preference_agent').glob('*.py')) + list((ROOT / 'tests').glob('*.py'))
        paths += [ROOT / 'main.py'] + list(ROOT.glob('*.md'))
        for path in paths:
            with self.subTest(path=path.name):
                source = path.read_text(encoding='utf-8')
                self.assertIsNone(re.search(r'[\u3400-\u9fff]', source))
                if path.suffix == '.py':
                    for node in ast.walk(ast.parse(source)):
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                            if node.func.attr in ('read_text', 'write_text'):
                                self.assertTrue(any(k.arg == 'encoding' for k in node.keywords),
                                                f'{path.name}:{node.lineno} omits an encoding')
        self.assertIn('Show this help', HELP)

    def test_cross_field_error_is_english_at_agent1_boundary(self):
        profile = json.loads((AGENT2 / 'data/demo/profiles/commute.json').read_text(encoding='utf-8'))
        values = flatten(profile)
        values['budget.maximum'] = 1
        result = assess({'values': values, 'issues': []}, 'test-search', 1)
        self.assertFalse(result['valid'])
        self.assertIn('maximum budget', ' '.join(result['errors']))
        self.assertIsNone(re.search(r'[\u3400-\u9fff]', json.dumps(result, ensure_ascii=False)))

    def test_summary_is_english_and_does_not_change_upstream_report(self):
        profile = json.loads((AGENT2 / 'data/demo/profiles/commute.json').read_text(encoding='utf-8'))
        dataset = json.loads((AGENT2 / 'data/demo/listings.json').read_text(encoding='utf-8'))
        report = evaluate(profile, dataset)
        original = deepcopy(report)
        text = render_english_report(report)
        self.assertIsNone(re.search(r'[\u3400-\u9fff]', text))
        self.assertIn('DEMO-006', text)
        self.assertIn('92.75', text)
        self.assertIn('source text may use another language', text)
        self.assertEqual(report, original)

    def test_demo_runs_when_unspecified_text_reads_default_to_gbk(self):
        original_read = Path.read_text
        def windows_read(path, *args, **kwargs):
            if not args and 'encoding' not in kwargs:
                kwargs['encoding'] = 'gbk'
            return original_read(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp) / 'state.sqlite3')
            # Redirect demo exports into the temporary test directory.
            fake_module_path = str(Path(temp) / 'preference_agent' / 'demo.py')
            with patch('preference_agent.demo.__file__', fake_module_path), patch.object(Path, 'read_text', windows_read):
                result = run_demo(store)
            self.assertEqual(result['v1_task']['status'], 'completed')
            self.assertEqual(result['v2_task']['counts']['eligible'], 0)
            self.assertTrue(result['original_version_preserved'])
            self.assertIsNone(re.search(r'[\u3400-\u9fff]', json.dumps(result, ensure_ascii=False)))


if __name__ == '__main__':
    unittest.main()
