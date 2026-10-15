"""Export reproducible SCRUM-22 acceptance evidence using synthetic inputs only.

Run from agent2/: python3 tools/verify_scrum22.py --output reports/my-scrum22
Each case saves its exact input, actual output, and independently stated expectations.
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rental_agent.contracts import validate_contract
from rental_agent.engine import evaluate, fingerprint
from rental_agent.report import render_markdown
from rental_agent.validation import ValidationError


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    base = json.loads((ROOT / 'data/demo/listings.json').read_text(encoding='utf-8'))
    profile = json.loads((ROOT / 'data/demo/profiles/commute.json').read_text(encoding='utf-8'))
    results = []

    def item(identifier='AC-A', **changes):
        row = deepcopy(base['listings'][0])
        row.update(listing_id=identifier, source_listing_id=identifier, **changes)
        for key in row['evidence']:
            row['evidence'][key]['source_ref'] = f'fixture:{identifier}#{key}'
        return row

    def data(*rows):
        return {k: deepcopy(v) for k, v in base.items() if k != 'listings'} | {'listings': list(rows)}

    def case(name, source, expected, checks, *, alternative_profile=None, rejected=False):
        folder = output / name
        folder.mkdir()
        p = deepcopy(profile if alternative_profile is None else alternative_profile)
        original = deepcopy((p, source))
        save(folder / 'input.json', {'profile': p, 'dataset': source})
        actual = {}
        try:
            if rejected:
                try:
                    evaluate(p, source)
                except ValidationError as exc:
                    actual = {'rejected': True, 'error': str(exc)}
                else:
                    actual = {'rejected': False}
                assert actual['rejected'], 'Invalid input was accepted'
                save(folder / 'actual.json', actual)
            else:
                report = evaluate(p, source)
                save(folder / 'actual.json', report)
                (folder / 'actual.md').write_text(render_markdown(report), encoding='utf-8')
                validate_contract('RecommendationReport', report)
                # Raw quotes/ranges, source IDs, observation timestamps and all duplicate
                # references remain available even when only one fact is used to score.
                audit = {
                    'data_mode': source['data_mode'], 'as_of': report['as_of'],
                    'dataset_fingerprint': fingerprint(source),
                    'recommendation_run_id': report['recommendation_run_id'],
                    'source_records': deepcopy(source['listings']),
                    'note': '原始价格区间仅保留，不取中点、不推断租金周期；不是已核实的实时房源。',
                }
                save(folder / 'source-audit.json', audit)
                assert audit['dataset_fingerprint'] == report['dataset_fingerprint']
                assert audit['source_records'] == original[1]['listings']
                actual = {'counts': report['counts'],
                          'ranked_ids': [r['listing_id'] for r in report['eligible']],
                          'top5_ids': [r['listing_id'] for r in report['recommendations']],
                          'rules': report['scoring_version'], 'as_of': report['as_of']}
                checks(report, p, source)
            assert (p, source) == original, 'Evaluation mutated input'
            result = {'case': name, 'status': 'PASS', 'expected': expected, 'actual': actual}
        except AssertionError as exc:
            result = {'case': name, 'status': 'FAIL', 'expected': expected, 'actual': actual, 'failure': str(exc)}
        save(folder / 'result.json', result)
        results.append(result)
        print(f"{result['status']}: {name} — {expected}")

    def require(condition, message):
        assert condition, message

    def state(expected_state, count=1):
        key = {'eligible': 'eligible', 'pending': 'pending_confirmation', 'excluded': 'excluded'}[expected_state]
        def check(report, p, source):
            require(len(report[key]) == count, f'Expected {count} {expected_state}')
            if expected_state != 'eligible':
                require(not report['recommendations'], 'Non-eligible input was recommended')
                require(all(r['score'] is None and r['rank'] is None for r in report[key]), 'Non-eligible input was scored/ranked')
        return check

    def baseline(report, p, source):
        require(report['counts'] == {'input': 30, 'eligible': 15, 'pending': 9, 'excluded': 5, 'duplicates': 1}, 'Unexpected fixture distribution')
        require(len(report['recommendations']) == 5 and len(report['eligible']) == 15, 'Top5/full ranking missing')
        require(report['recommendations'][0]['listing_id'] == 'DEMO-006', 'Unexpected top recommendation')
        require(all(r['reasons'] and r['evidence_refs'] for r in report['eligible']), 'Eligible evidence/reasons missing')
        require(any(r['tradeoffs'] for r in report['eligible']), 'Tradeoffs missing')
        require(all(any(c['status'] == 'fail' for c in r['hard_checks'].values()) for r in report['excluded']), 'Excluded reason missing')
        require(report['clarification_requests'], 'Clarifications missing')
    case('01-baseline', deepcopy(base), '30输入→15合格/9待确认/5排除/1重复；Top5且保留15条完整排名与解释', baseline)

    a, b = item(), item('AC-B')
    b['source_listing_id'] = a['source_listing_id']
    b['evidence']['rent_amount']['observed_at'] = '2026-09-17T08:30:00+10:00'
    def duplicate(report, p, source):
        require(report['counts']['eligible'] == 1 and report['counts']['duplicates'] == 1, 'Same source facts were not merged')
        require(report['eligible'][0]['evidence_refs']['rent_amount'] == source['listings'][1]['evidence']['rent_amount'], 'Freshest original reference lost')
        require(report['duplicates'][0]['duplicate_of'] == 'AC-A', 'Duplicate trace missing')
    case('02-duplicate', data(a, b), '同源同ID同事实合并；使用最新有效证据；审计保留两份原始引用', duplicate)
    conflict = deepcopy(b)
    conflict['rent_amount'] = 400
    def conflicting(report, p, source):
        state('pending', 2)(report, p, source)
        require(all(r['hard_checks']['conflicts']['status'] == 'unknown' for r in report['pending_confirmation']), 'Conflict gate missing')
    case('03-conflict', data(a, conflict), '同源同ID租金冲突→两条pending，不排名；原始两份报价可追溯', conflicting)

    def unknown_rent(report, p, source):
        state('pending')(report, p, source)
        require(report['pending_confirmation'][0]['weekly_cost'] is None, 'Unknown quote was converted')
        require(any('rent_period' in text for text in report['pending_confirmation'][0]['issues']), 'Unknown period reason missing')
    case('04-unknown-period', data(item(rent_period=None)), '周期未知→pending；周费用为空，不猜测week', unknown_rent)
    range_row = item(rent_amount=None)
    range_row['rent_range'] = {'minimum': 480, 'maximum': 540}
    range_row['evidence']['rent_range'] = deepcopy(range_row['evidence']['rent_amount'])
    range_row['evidence']['rent_range']['source_ref'] = 'fixture:AC-A#rent_range'
    def range_check(report, p, source):
        state('pending')(report, p, source)
        require(report['pending_confirmation'][0]['weekly_cost'] is None, 'Range was collapsed to a point')
    case('05-price-range', data(range_row), '原始480–540报价区间和周期/计价对象保留在审计；不取中点，缺精确报价保持pending', range_check)
    case('06-missing-evidence', data(item() | {'evidence': {}}), '有值但无字段证据→pending，不排名', state('pending'))
    case('07-missing-positive-weight', data(item(supermarket_distance_m=None)), '正权重设施输入缺失→pending，总分和排名为空', state('pending'))
    case('08-gate-undecided', data(item(source_permission=False)), '权限门禁未明确→pending，不排名', state('pending'))
    case('09-hard-fail-precedence', data(item(rent_amount=900, supermarket_distance_m=None)), '硬预算失败且软信息缺失→excluded；硬失败优先', state('excluded'))
    case('10-zero-eligible', data(item(rent_amount=900), item('AC-B', listing_status='unavailable')), '全部硬失败→零合格是有效报告；无推荐，不自动放宽条件', state('excluded', 2))
    def empty(report, p, source):
        require(report['counts']['input'] == 0 and not report['recommendations'] and report['clarification_requests'], 'Empty result invalid')
    case('11-empty-input', data(), '空房源集→有效零推荐及澄清建议', empty)

    def deterministic(report, p, source):
        require(report == evaluate(deepcopy(p), deepcopy(source)), 'Fixed input/as_of/rules changed output')
    case('12-repeat', deepcopy(base), '固定输入、评估时间、rules-1.0重跑：完整报告及批次ID完全相同', deterministic)
    def ties(report, p, source):
        require([r['listing_id'] for r in report['eligible']] == [f'AC-{i}' for i in range(8)], 'Tie order is unstable')
        require(len(report['recommendations']) == 5 and len(report['eligible']) == 8, 'Top5/all candidates not retained')
        reverse = deepcopy(source)
        reverse['listings'].reverse()
        require(report['eligible'] == evaluate(p, reverse)['eligible'], 'Input order changed ranks')
    case('13-stable-ties', data(*[item(f'AC-{i}') for i in reversed(range(8))]), '8条同分候选按ID稳定排序；输入倒序不改排名；只展示5条且保留8条', ties)
    def normalized(report, p, source):
        state('eligible', 3)(report, p, source)
        require(all(r['weekly_cost'] == 520 for r in report['eligible']), 'Period conversion mismatch')
    case('14-period-normalization', data(item(), item('AC-B', rent_amount=1040, rent_period='fortnight'), item('AC-C', rent_amount=520 * 52 / 12, rent_period='month')), '同计价对象下周/双周/月报价均归一为520 AUD/week', normalized)
    case('15-scope-mismatch', data(item(rent_scope='whole_property')), '整租与每人计价不匹配→pending，不按人数平分', state('pending'))
    zero_profile = deepcopy(profile)
    zero_profile['weights']['amenities'] = 0
    case('16-zero-weight-missing', data(item(supermarket_distance_m=None)), '仅零权重设施未知且其他条件完整→可合格', state('eligible'), alternative_profile=zero_profile)
    stale = item(last_checked_at='2026-09-14T08:00:00+10:00')
    case('17-stale', data(stale), '过期快照→pending，不把执行日期当来源刷新时间', state('pending'))
    case('18-invalid-period', data(item(rent_period='unknown')), '非法周期字符串拒绝整批并指明字段；不默认为week', None, rejected=True)
    case('19-real-data-rejected', data(item(data_kind='real')), '当前原型拒绝真实/混合房源模式', None, rejected=True)

    summary = {'task': 'SCRUM-22', 'data_mode': 'synthetic_demo', 'cases': results,
               'passed': sum(r['status'] == 'PASS' for r in results), 'total': len(results),
               'integration_status': '未执行 Member 1 真实联调；上游适配代码尚未在共享仓库提供。'}
    save(output / 'summary.json', summary)
    lines = ['# SCRUM-22 场景验收结果', '', '全部使用合成数据；快照时点固定为2026-09-17，不代表当前真实房源。', '', '|场景|预期|实际|', '|---|---|---|']
    lines += [f"|[{r['case']}]({r['case']}/result.json)|{r['expected']}|{r['status']}|" for r in results]
    lines += ['', f"通过：{summary['passed']}/{summary['total']}。", '', summary['integration_status'], '', '每个场景包含input.json和actual.json；有效输入另含actual.md和source-audit.json。价格区间为原始附加元数据，只保留，不进行区间评分。']
    (output / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"RESULT: {summary['passed']}/{summary['total']} PASS")
    return 0 if summary['passed'] == summary['total'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='新的证据目录；拒绝覆盖')
    args = parser.parse_args()
    raise SystemExit(run(args.output))
