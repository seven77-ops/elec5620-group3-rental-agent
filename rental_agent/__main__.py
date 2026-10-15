"""Run with: python3 -m rental_agent --profile ... --listings ... --output ..."""

import argparse
import json
from pathlib import Path
import sys

from .engine import evaluate
from .contracts import validate_contract
from .handoff import build_selected_listing_evidence
from .report import compare_reports, render_markdown
from .validation import ValidationError


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f'JSON 重复字段：{key}')
        result[key] = value
    return result


def invalid_constant(value):
    raise ValidationError(f'JSON 非有限数字：{value}')


def load_json(path):
    with Path(path).open(encoding='utf-8') as stream:
        return json.load(stream, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description='悉尼租房评估课程原型：仅模拟数据，无网络和 API 密钥。')
    parser.add_argument('--profile', required=True, help='已确认客户偏好 JSON')
    parser.add_argument('--listings', required=True, help='包含 as_of 的模拟房源 JSON')
    parser.add_argument('--output', required=True, help='输出文件前缀（自动添加 .json / .md；拒绝覆盖）')
    parser.add_argument('--compare-profile', help='可选功能：调整后的偏好 JSON，与原偏好比较')
    parser.add_argument('--as-of', help='显式覆盖评估时点，例如 2026-09-17T09:00:00+10:00')
    parser.add_argument('--select-listing', help='用户明确选中的合格房源ID；仅构建本地交接证据包')
    parser.add_argument('--selected-at', help='选择发生的带时区时间；必须与 --select-listing 一起提供')
    args = parser.parse_args(argv)
    if (args.select_listing is None) != (args.selected_at is None):
        parser.error('--select-listing 和 --selected-at 必须一起提供')
    try:
        profile, listings = load_json(args.profile), load_json(args.listings)
        report = evaluate(profile, listings, as_of=args.as_of)
        if args.compare_profile:
            after = evaluate(load_json(args.compare_profile), listings, as_of=args.as_of)
            after['comparison'] = compare_reports(report, after)
            report = after
        validate_contract('RecommendationReport', report)
        packet = None
        if args.select_listing is not None:
            packet = build_selected_listing_evidence(report, listings, args.select_listing,
                                                     selected_at=args.selected_at, user_confirmed=True)
        json_path, md_path = Path(args.output + '.json'), Path(args.output + '.md')
        paths = [json_path, md_path]
        if packet is not None:
            paths.append(Path(args.output + '.selection.json'))
        if any(path.exists() or path.is_symlink() for path in paths):
            raise ValidationError('输出文件已存在；请使用新的 --output 前缀，不会覆盖已有文件')
        contents = [json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', render_markdown(report)]
        if packet is not None:
            contents.append(json.dumps(packet, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        json_path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation protects existing files even if another process races us.
        for path, content in zip(paths, contents):
            with path.open('x', encoding='utf-8') as stream:
                stream.write(content)
        print(f'已生成（仅模拟）：{md_path}\n结构化报告：{json_path}')
        print(f"推荐批次：{report['recommendation_run_id']}")
        if packet is not None:
            print(f'选房证据包（未发送）：{paths[2]}')
        print('结果：' + ', '.join(f'{key}={value}' for key, value in report['counts'].items()))
        return 0
    except (ValidationError, OSError, ValueError, UnicodeError) as exc:
        print(f'输入或输出错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
