from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from aftercare_agent.contracts import ROOT, load_json, validate
from aftercare_agent.errors import AftercareError
from aftercare_agent.report import export_case, render_markdown


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.store = self.out / 'test.sqlite3'

    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'aftercare_agent', *map(str, args)], cwd=ROOT,
                              capture_output=True, text=True, env={**os.environ, 'AGENT4_OPERATOR_IDS': ''})

    def create(self):
        result = self.cli('run', '--request', ROOT / 'data/demo/requests/01-create.json', '--store', self.store)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_run_show_and_no_overwrite(self):
        self.create()
        prefix = self.out / 'case'
        result = self.cli('show', '--store', self.store, '--case-id', 'aftercare-demo-1', '--actor-id', 'demo-tenant', '--output', prefix)
        self.assertEqual(result.returncode, 0, result.stderr)
        document = load_json(str(prefix) + '.json')
        validate('aftercare-case', document)
        self.assertIn('M4 Aftercare', Path(str(prefix) + '.md').read_text())
        result = self.cli('show', '--store', self.store, '--case-id', 'aftercare-demo-1', '--actor-id', 'demo-tenant', '--output', prefix)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)['error']['code'], 'output_exists')

    def test_duplicate_json_key_is_rejected(self):
        path = self.out / 'bad.json'
        path.write_text('{"operation":"create","operation":"withdraw"}')
        result = self.cli('run', '--store', self.store, '--request', path)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)['error']['code'], 'invalid_input')

    def test_non_finite_json_is_rejected(self):
        path = self.out / 'bad.json'
        path.write_text('{"value":NaN}')
        result = self.cli('run', '--store', self.store, '--request', path)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)['error']['code'], 'invalid_input')

    def test_missing_file_has_structured_error(self):
        result = self.cli('run', '--store', self.store, '--request', self.out / 'missing.json')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)['error']['code'], 'io_or_input_error')

    def test_demo_generates_reproducible_snapshots_and_expected_block(self):
        out = self.out / 'demo'
        result = self.cli('demo', '--output', out)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual((summary['commands_committed'], summary['expected_blocked_commands'], summary['final_state']), (17, 1, 'Resolved'))
        snapshots = sorted(out.glob('*.json'))
        self.assertEqual(len(snapshots), 10)
        for path in snapshots:
            if path.name != 'scenario-log.json':
                validate('aftercare-case', load_json(path))
        self.assertEqual(load_json(out / '05-dispute.json')['bond']['state'], 'UnderReview')
        closed = load_json(out / '09-closed-reminders.json')
        self.assertEqual(closed['bond']['state'], 'Resolved')
        self.assertTrue(all(r['state'] == 'suppressed' for r in closed['reminders']))
        self.assertEqual(self.cli('demo', '--output', out).returncode, 2)

    def test_read_cannot_disclose_foreign_case(self):
        self.create()
        result = self.cli('show', '--store', self.store, '--case-id', 'aftercare-demo-1', '--actor-id', 'other')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)['error']['code'], 'access_denied')
        self.assertNotIn('Example Street', result.stderr + result.stdout)

    def test_all_example_commands_validate(self):
        for path in (ROOT / 'data/demo/requests').glob('*.json'):
            with self.subTest(path=path):
                validate('command', load_json(path))

    def test_markdown_escapes_imported_links_and_pipe(self):
        self.create()
        result = self.cli('show', '--store', self.store, '--case-id', 'aftercare-demo-1', '--actor-id', 'demo-tenant')
        case = json.loads(result.stdout)
        case['tenancy']['address'] = '[click](https://example.invalid)|<img>'
        text = render_markdown(case)
        self.assertIn('\\[click\\]', text)
        self.assertIn('\\|\\<img\\>', text)
        self.assertNotIn('[click](https', text)

    def test_no_partial_export_if_second_path_is_existing(self):
        self.create()
        result = self.cli('show', '--store', self.store, '--case-id', 'aftercare-demo-1', '--actor-id', 'demo-tenant')
        prefix = self.out / 'partial'
        Path(str(prefix) + '.md').write_text('Original')
        with self.assertRaises(AftercareError):
            export_case(json.loads(result.stdout), prefix)
        self.assertFalse(Path(str(prefix) + '.json').exists())
        self.assertEqual(Path(str(prefix) + '.md').read_text(), 'Original')
