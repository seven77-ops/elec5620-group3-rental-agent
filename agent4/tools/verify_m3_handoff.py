"""Reproduce the five M3 handoff scenarios with explicit synthetic confirmation doubles.

Run from the repository root. Never overwrites an earlier report directory.
"""
import argparse
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import importlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'agent4'))
sys.path.insert(0, str(REPO))
from aftercare_agent.contracts import load_json
from aftercare_agent.handoff import FIELDS, fingerprint
from aftercare_agent.report import export_document, export_case
from aftercare_agent.store import AftercareAgent

TENANT = 'DEMO-TENANT-001'
NOW = '2026-10-17T19:01:00+11:00'


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='NEW report directory, normally agent4/reports/m3-m4-<run>')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    runtime = REPO / 'agent4/runs' / output.name
    runtime.mkdir(parents=True, exist_ok=False)
    (runtime / 'temp').mkdir()
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
           'PYTHONPATH': os.pathsep.join(str(REPO / name) for name in ('agent4', 'agent3', 'agent2')) + os.pathsep + str(REPO),
           'TEMP': str(runtime / 'temp'), 'TMP': str(runtime / 'temp')}
    fixtures = REPO / 'agent4/data/demo/m3-handoff/snapshots'
    execution, scenarios, suites = [], [], []

    def run(name, argv, expected=0):
        result = subprocess.run(argv, cwd=REPO, env=env, capture_output=True, text=True, encoding='utf-8')
        (output / (name + '.stdout.txt')).write_text(result.stdout, encoding='utf-8')
        (output / (name + '.stderr.txt')).write_text(result.stderr, encoding='utf-8')
        execution.append({'name': name, 'argv': list(map(str, argv)), 'cwd': str(REPO),
                          'command': shlex.join(list(map(str, argv))), 'exit_code': result.returncode,
                          'expected_exit_code': expected})
        if result.returncode != expected:
            write_json(output / 'failed-execution.json', execution)
            raise AssertionError(f'{name}: expected {expected}, got {result.returncode}; see stderr log')
        return result

    normal = load_json(fixtures / 'normal-confirmation-stub-packet.json')
    database = runtime / 'five-scenarios.sqlite3'

    def receive(name, packet, store, status, code=None):
        input_file = output / (name + '.input.json')
        write_json(input_file, packet)
        result = run(name, [sys.executable, '-m', 'aftercare_agent', 'receive', '--packet', str(input_file),
                           '--store', str(store), '--actor-id', TENANT, '--as-of', NOW,
                           '--output', str(output / name)], 3 if status == 'paused' else 0)
        response = json.loads(result.stdout)
        assert response['status'] == status, response
        if code:
            assert response['code'] == code, response
        agent = AftercareAgent(store)
        with closing(agent.connect()) as db:
            count = db.execute('SELECT COUNT(*) FROM cases').fetchone()[0]
            mappings = db.execute('SELECT COUNT(*) FROM m3_handoffs').fetchone()[0]
        scenarios.append({'name': name, 'status': response['status'], 'code': response.get('code'),
                          'case_id': response.get('case_id'), 'tenancy_id': response.get('tenancy_id'),
                          'review_id': packet['review']['review_id'], 'review_version': packet['review']['version'],
                          'snapshot_revision': packet['review']['snapshot_revision'],
                          'confirmation_snapshot_revision': (packet['confirmation'] or {}).get('review_snapshot_revision'),
                          'confirmation_id': (packet['confirmation'] or {}).get('confirmation_id'),
                          'confirmation_version': (packet['confirmation'] or {}).get('confirmation_version'),
                          'case_count': count, 'mapping_count': mappings, 'newly_created': response['newly_created']})
        return response

    first = receive('01-normal-stub', normal, database, 'created')
    again = receive('02-repeat', normal, database, 'duplicate')
    assert again['case_id'] == first['case_id'] and again['tenancy_id'] == first['tenancy_id']
    assert scenarios[-1]['case_count'] == 1
    receive('03-unconfirmed', load_json(fixtures / 'missing-confirmation-packet.json'),
            runtime / 'unconfirmed.sqlite3', 'paused', 'confirmation_required')
    receive('04-human-review', load_json(fixtures / 'human-review-packet.json'),
            runtime / 'human-review.sqlite3', 'paused', 'review_blocked')
    version_packet = load_json(fixtures / 'v2-old-confirmation-packet.json')
    receive('05-version-change', version_packet, database, 'paused', 'review_version_mismatch')
    receive('06-old-version-replay', normal, database, 'paused', 'stale_snapshot')
    assert scenarios[-1]['case_count'] == 1
    # Reconfirmation is a test double too; M3 has not implemented the real producer.
    v2 = deepcopy(version_packet)
    v2['request_id'] = 'm3:confirmation-stub:v2-reconfirmed'
    c, r = v2['confirmation'], v2['review']
    c.update(confirmation_id='DEMO-M3-CONFIRMATION-STUB-V2', confirmation_version=1,
             review_id=r['review_id'], review_version=r['version'], review_snapshot_revision=r['snapshot_revision'],
             review_sha256=fingerprint(r), document_sha256=r['document']['sha256'])
    c['confirmed_fields'].update({k: r['fields'][k]['value'] for k in FIELDS})
    receive('07-v2-reconfirmed-fresh', v2, runtime / 'v2-fresh.sqlite3', 'created')
    receive('08-v2-reconfirmed-existing', v2, database, 'paused', 'existing_tenancy_requires_reconciliation')
    # Dedicated, current v1 DB proves that actual tenancy confirmation cannot create a move-out plan.
    plan_db = runtime / 'separate-date.sqlite3'
    registered = receive('09-separate-date-setup', normal, plan_db, 'created')
    agent = AftercareAgent(plan_db)
    case = agent.get(registered['case_id'], TENANT)
    export_case(case, output / '10-before-date-confirmation')
    def command(request_id, operation, payload):
        return {'schema_version': '1.0', 'request_id': request_id, 'case_id': case['case_id'], 'actor_id': TENANT,
                'actor_role': 'tenant', 'expected_version': case['version'], 'as_of': NOW, 'operation': operation, 'payload': payload}
    unconfirmed_plan = command('date-not-confirmed', 'create_plan', {'move_out_date': '2028-02-02', 'schedule_confirmed': False})
    write_json(output / '11-unconfirmed-date.input.json', unconfirmed_plan)
    blocked = run('11-unconfirmed-date', [sys.executable, '-m', 'aftercare_agent', 'run', '--store', str(plan_db),
                                        '--request', str(output / '11-unconfirmed-date.input.json')], 2)
    assert json.loads(blocked.stderr)['error']['code'] == 'move_out_confirmation_required'
    assert agent.get(case['case_id'], TENANT)['plan'] is None
    tenancy = deepcopy(case['tenancy'])
    tenancy.update(rooms=[{'id': 'demo-room', 'name': 'User-confirmed synthetic room'}],
                   carpeted=False, outdoor=False, furnished=False, inventory=[], inventory_confirmed=True)
    write_json(output / '12-property-details.input.json', command('property-details', 'revise_tenancy', {'tenancy': tenancy}))
    run('12-property-details', [sys.executable, '-m', 'aftercare_agent', 'run', '--store', str(plan_db),
                               '--request', str(output / '12-property-details.input.json')])
    case = agent.get(case['case_id'], TENANT)
    write_json(output / '13-confirmed-date.input.json', command('date-explicitly-confirmed', 'create_plan',
                                                               {'move_out_date': '2028-02-02', 'schedule_confirmed': True}))
    run('13-confirmed-date', [sys.executable, '-m', 'aftercare_agent', 'run', '--store', str(plan_db),
                             '--request', str(output / '13-confirmed-date.input.json'), '--output', str(output / '13-confirmed-date')])
    final = agent.get(case['case_id'], TENANT)
    assert final['plan']['state'] == 'Active' and final['plan']['move_out_date'] == '2028-02-02'
    assert final['bond'] is None
    write_json(output / '14-saved-handoff-snapshot.json', agent.get_handoff(case['case_id'], TENANT))

    # Real M3 state transitions at one fixed second. Sequence/confirmation assignment
    # is an explicitly synthetic persistence double until M3 implements that entry.
    from agent3.contract_agent.document import load_document
    m3 = importlib.import_module('agent3.contract_agent.review')
    agreement = runtime / 'synthetic-risk-with-signed-date.txt'
    agreement.write_text((REPO / 'agent3/data/demo/agreements/selection-demo.txt').read_text(encoding='utf-8')
                         .replace('Bond: $2000', 'Bond: $2500'), encoding='utf-8')
    with patch.object(m3, '_now', return_value='2026-10-17T18:00:00+11:00'):
        pending = m3.review_agreement(load_document(agreement, consent=True), consent=True,
                                     selection=normal['review']['selection_evidence'], as_of='2026-10-15')
        approved = m3.approve_review(pending, reviewer='DEMO-OPERATOR', decision='approve', note='Synthetic same-second test')
    assert pending['version'] == approved['version'] == 1
    assert pending['updated_at'] == approved['updated_at']
    pending['snapshot_revision'], approved['snapshot_revision'] = 1, 2
    before, after = deepcopy(normal), deepcopy(normal)
    before.update(request_id='same-second:pending', review=pending, confirmation=None)
    after.update(request_id='same-second:approved', review=approved)
    after['confirmation'].update(confirmation_id='DEMO-SAME-SECOND-CONFIRMATION', review_id=approved['review_id'],
                                review_snapshot_revision=2, review_sha256=fingerprint(approved), document_sha256=approved['document']['sha256'])
    after['confirmation']['confirmed_fields'].update({k: approved['fields'][k]['value'] for k in FIELDS})
    same_db = runtime / 'same-second.sqlite3'
    receive('15-same-second-pending', before, same_db, 'paused', 'review_blocked')
    released = receive('16-same-second-approved', after, same_db, 'created')
    receive('17-old-pending-replay', before, same_db, 'paused', 'stale_snapshot')
    conflict = deepcopy(after)
    conflict['request_id'] = 'same-revision:changed-content'
    conflict['review']['status_reason'] = 'Different content with the same snapshot revision'
    conflict['confirmation']['review_sha256'] = fingerprint(conflict['review'])
    receive('18-same-revision-conflict', conflict, same_db, 'paused', 'review_snapshot_conflict')
    mismatch = deepcopy(after)
    mismatch['request_id'] = 'wrong-confirmation-revision'
    mismatch['confirmation']['review_snapshot_revision'] = 1
    receive('19-confirmation-revision-mismatch', mismatch, runtime / 'mismatch.sqlite3', 'paused', 'review_snapshot_revision_mismatch')
    questions = deepcopy(after)
    questions.update(request_id='newer:questions', confirmation=None)
    questions['review'].update(snapshot_revision=3, status='Questions Ready')
    receive('20-newer-blocked-snapshot', questions, same_db, 'paused', 'review_blocked')
    receive('21-old-success-replay', after, same_db, 'paused', 'stale_snapshot')
    assert scenarios[-1]['case_count'] == 1
    assert AftercareAgent(same_db).get_handoff(released['case_id'], TENANT)['review']['snapshot_revision'] == 2

    for name, folder in (('m4-tests', 'agent4/tests'), ('m3-tests', 'agent3/tests'), ('upstream-integration-tests', 'integration/tests')):
        result = run(name, [sys.executable, '-m', 'unittest', 'discover', '-s', folder, '-v'])
        match = re.search(r'Ran (\d+) tests?', result.stderr)
        suites.append({'suite': name, 'tests': int(match[1]) if match else None, 'status': 'passed'})

    historical = REPO / 'agent4/reports/m3-m4-receive-20261017-03'
    previous_hashes = load_json(historical / 'sha256.json')
    assert all(sha256((historical / name).read_bytes()).hexdigest() == digest for name, digest in previous_hashes.items())
    refs = {name: subprocess.check_output(['git', 'rev-parse', name], cwd=REPO).decode().strip() for name in (
        'HEAD', 'origin/main', 'origin/codex/m3-m4-handoff-20261017', 'origin/codex/frontend-demo', 'origin/codex/m4-m3-receive-20261017')}
    metadata = {'data_mode': 'synthetic_demo', 'confirmation_producer': 'explicit_test_double_not_implemented_M3_entry',
                'sequence_producer': 'explicit_test_double_not_implemented_M3_persistence',
                'executed_at': datetime.now(timezone.utc).isoformat(), 'scenario_clock': NOW,
                'refs': refs, 'historical_report_hashes_verified': len(previous_hashes),
                'python': sys.version, 'dependencies': {n: importlib.metadata.version(n) for n in ('jsonschema', 'pypdf', 'tzdata')},
                'source_sha256': {p.relative_to(REPO).as_posix(): sha256(p.read_bytes()).hexdigest()
                                  for folder in ('aftercare_agent', 'tests', 'tools', 'schemas')
                                  for p in sorted((REPO / 'agent4' / folder).glob('*')) if p.is_file()},
                'fixture_sha256': {p.relative_to(fixtures.parent).as_posix(): sha256(p.read_bytes()).hexdigest()
                                   for p in fixtures.parent.rglob('*.json')},
                'environment': {k: env[k] for k in ('PYTHONPATH', 'PYTHONUTF8', 'PYTHONIOENCODING', 'TEMP', 'TMP')},
                'scenarios': scenarios, 'suites': suites, 'commands': execution,
                'limits': ['M3 actual confirmation producer remains unimplemented; synthetic doubles only.',
                           'HTTP/frontend adapter was inspected but not changed; no browser end-to-end claim.',
                           'Existing tenancy with new confirmed review pauses for explicit reconciliation.']}
    write_json(output / 'execution.json', metadata)
    rows = ['# M3 → M4 接收验证', '', '本次为 M4 消费端的合成数据预联调。M3 实际租约确认入口未实现，确认记录由明确标注的测试替身提供。', '',
            '快照序号同样由测试替身显式分配；同秒复核/人工放行调用真实 M3 状态函数。尚未验证 M3 事务计数器和确认持久化入口。', '',
            '| 场景 | 版本/序号 | 结果 | 结果码 | 案件数 |', '|---|---|---|---|---|']
    rows += [f"| {s['name']} | {s['review_version']}/{s['snapshot_revision']} | {s['status']} | {s['code'] or 'ok'} | {s['case_count']} |" for s in scenarios]
    rows += ['', '## 回归', ''] + [f"- {s['suite']}: {s['tests']} 项通过。" for s in suites]
    rows += ['', '## ID 与来源', '', f"- 正常 M4 案件：`{first['case_id']}`。", f"- 正常租约：`{first['tenancy_id']}`。",
             '- `02-repeat` 与 `01-normal-stub` 的案件和租约 ID 相同；数据库仍为一个案件。',
             '- `15/16` 在同一秒从序号 1 人工待审变为序号 2 放行，可创建；`17/21` 的旧包被拦截，`18` 同号异内容冲突，`19` 确认序号不匹配暂停。',
             '- 已核对旧报告 67 个文件的指纹，全部保持原样。',
             '- `05-version-change` 保存已知 v2，旧确认被拒绝；随后 v1 原请求重放也被拒绝。',
             '- 原租约来源仍为 v1，不自动覆盖、不创建第二案件；新版重新确认在新库可创建，在既有库要求明确核对。',
             '- `10-before-date-confirmation` 的 plan/bond 均为 null；第 11 步未确认日期被拦截，第 13 步独立确认后创建 Active 计划。',
             '- 完整业务上下文、合同、租期与确认快照见各场景 JSON 及 `14-saved-handoff-snapshot.json`。', '',
             '## 复现', '', '从仓库根目录，使用装有 agent3/agent4 requirements 的 Python：', '', '```sh',
             'python agent4/tools/verify_m3_handoff.py --output agent4/reports/m3-m4-<new-run-name>', '```', '',
             '输出目录必须使用新名字；完整命令、返回码、环境、依赖版本见 execution.json，stdout/stderr 逐条保存。', '',
             '仍需 M3 提供真实持久化确认记录，并由统一服务端绑定会话、案例和最新复核后调用 receive。前端页面与真实生产鉴权不在本次验证范围。', '']
    (output / 'README.md').write_text('\n'.join(rows), encoding='utf-8')
    hashes = {p.relative_to(output).as_posix(): sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file()}
    write_json(output / 'sha256.json', hashes)
    print(json.dumps({'status': 'passed', 'output': str(output), 'suites': suites, 'scenario_count': len(scenarios)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
