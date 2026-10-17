"""python -m aftercare_agent: commands, read-only export and a reproducible demo."""
import argparse
import json
import os
import sqlite3
import sys
from .contracts import load_json
from .errors import AftercareError
from .report import check_output, export_case, export_document, safe
from .store import AftercareAgent


def main(argv=None):
    parser = argparse.ArgumentParser(description='M4 move-out / bond aftercare local prototype')
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run', help='Apply one versioned JSON command')
    run.add_argument('--request', required=True)
    run.add_argument('--store', required=True)
    run.add_argument('--output', help='Optional JSON/Markdown export prefix; refuses overwrite')
    receive = sub.add_parser('receive', help='Consume a saved M3 review + tenancy confirmation (local demo identity)')
    receive.add_argument('--packet', required=True)
    receive.add_argument('--store', required=True)
    receive.add_argument('--actor-id', required=True, help='Coordinator/session tenant, simulated in CLI')
    receive.add_argument('--as-of', required=True, help='Coordinator clock with timezone')
    receive.add_argument('--output', help='NEW JSON/Markdown receipt and source snapshot prefix')
    show = sub.add_parser('show', help='Read a committed case without modifying it')
    show.add_argument('--store', required=True)
    show.add_argument('--case-id', required=True)
    show.add_argument('--actor-id', required=True)
    show.add_argument('--actor-role', choices=['tenant', 'operator'], default='tenant')
    show.add_argument('--output', help='JSON/Markdown prefix')
    demo = sub.add_parser('demo', help='Run fixed synthetic UC07/UC08/OF04 scenarios')
    demo.add_argument('--output', required=True, help='A NEW output directory')
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            from .demo import run_demo
            summary = run_demo(args.output)
        else:
            if args.output:
                check_output(args.output)
            agent = AftercareAgent(args.store, operator_ids=[s.strip() for s in os.getenv('AGENT4_OPERATOR_IDS', '').split(',') if s.strip()])
            if args.command == 'receive':
                packet = load_json(args.packet)
                summary = agent.receive(packet, actor_id=args.actor_id, as_of=args.as_of)
                if args.output:
                    markdown = '\n'.join(['# M3 → M4 接收结果', '',
                        '本地原型 / 模拟身份；请核对 JSON 中的确认来源。演示 stub 文件不是 M3 已实现的确认入口输出。', '',
                        f"状态：{safe(summary['status'])}", '',
                        f"结果码：{safe(summary.get('code', 'ok'))}", '',
                        f"上游案例：{safe(packet['context']['case_id'])}", '',
                        f"复核：{safe(packet['review']['review_id'])} / v{packet['review']['version']}", '',
                        f"M4 案件：{safe(summary.get('case_id', '未创建'))}", '',
                        f"租约：{safe(summary.get('tenancy_id', '未创建'))}", '',
                        f"说明：{safe(summary.get('message', summary.get('next_action', '')))}", '',
                        'JSON 保存完整输入、确认来源与原子提交收据。租约确认不确认退租日期，也不证明押金已支付。', ''])
                    export_document({'input': packet, 'response': summary}, markdown, args.output)
                print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
                return 3 if summary['status'] == 'paused' else 0
            elif args.command == 'run':
                response = agent.submit(load_json(args.request))
                case = response['case']
                summary = {k: response[k] for k in ('request_id', 'case_id', 'version', 'task', 'result')}
            else:
                case = agent.get(args.case_id, args.actor_id, args.actor_role)
                summary = case
            if args.output:
                export_case(case, args.output)
        print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except AftercareError as exc:
        error = {'code': exc.code, 'message': str(exc)}
    except (OSError, ValueError, UnicodeError, sqlite3.Error) as exc:
        error = {'code': 'io_or_input_error', 'message': str(exc)}
    print(json.dumps({'error': error}, ensure_ascii=False), file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
