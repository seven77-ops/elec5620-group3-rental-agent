"""Reproducible synthetic workflow and snapshots; never calls a network provider."""
from pathlib import Path
import json
from .contracts import ROOT, load_json
from .errors import AftercareError, require
from .report import export_case
from .store import AftercareAgent


def run_demo(directory):
    out = Path(directory)
    require(not out.exists() and not out.is_symlink(), 'output_exists', 'Choose a new demo output directory')
    out.mkdir(parents=True)
    agent = AftercareAgent(out / 'demo.sqlite3', operator_ids={'demo-operator'})
    log = []
    for step in load_json(ROOT / 'data/demo/scenario.json')['commands']:
        request = step['request']
        try:
            response = agent.submit(request)
        except AftercareError as exc:
            if step.get('expect_error') != exc.code:
                raise
            log.append({'request_id': request['request_id'], 'expected_error': exc.code})
            continue
        require('expect_error' not in step, 'demo_failure', 'Expected a blocked operation')
        if 'snapshot' in step:
            export_case(response['case'], out / step['snapshot'])
        log.append({'request_id': request['request_id'], 'operation': request['operation'],
                    'version': response['version'], 'bond_state': (response['case']['bond'] or {}).get('state'),
                    'delivered_count': len(response['result'].get('delivered', []))})
    (out / 'scenario-log.json').write_text(json.dumps(log, indent=2) + '\n', encoding='utf-8')
    return {'status': 'completed', 'data_kind': 'synthetic', 'output': str(out),
            'commands_committed': len([item for item in log if 'version' in item]),
            'expected_blocked_commands': len([item for item in log if 'expected_error' in item]),
            'final_state': agent.get('aftercare-demo-1', 'demo-tenant')['bond']['state']}
