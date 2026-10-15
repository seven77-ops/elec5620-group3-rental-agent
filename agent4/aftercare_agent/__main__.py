"""python -m aftercare_agent: commands, read-only export and a reproducible demo."""
import argparse
import json
import os
import sqlite3
import sys
from .contracts import load_json
from .errors import AftercareError
from .report import check_output, export_case
from .store import AftercareAgent


def main(argv=None):
    parser = argparse.ArgumentParser(description='M4 move-out / bond aftercare local prototype')
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run', help='Apply one versioned JSON command')
    run.add_argument('--request', required=True)
    run.add_argument('--store', required=True)
    run.add_argument('--output', help='Optional JSON/Markdown export prefix; refuses overwrite')
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
            if args.command == 'run':
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
