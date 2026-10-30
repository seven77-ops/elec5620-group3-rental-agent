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
            raise ValidationError(f'Duplicate JSON field: {key}')
        result[key] = value
    return result


def invalid_constant(value):
    raise ValidationError(f'Non-finite JSON number: {value}')


def load_json(path):
    with Path(path).open(encoding='utf-8') as stream:
        return json.load(stream, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Sydney rental evaluation coursework prototype: synthetic data only, without network access or API keys.')
    parser.add_argument('--profile', required=True, help='Confirmed client preferences JSON')
    parser.add_argument('--listings', required=True, help='Synthetic listings JSON containing as_of')
    parser.add_argument('--output', required=True, help='Output file prefix (.json / .md appended automatically; existing files are not overwritten)')
    parser.add_argument('--compare-profile', help='Optional adjusted-preferences JSON to compare with the original preferences')
    parser.add_argument('--as-of', help='Explicit evaluation timestamp override, e.g. 2026-09-17T09:00:00+10:00')
    parser.add_argument('--select-listing', help='Eligible listing ID explicitly selected by the user; builds a local handoff evidence package only')
    parser.add_argument('--selected-at', help='Timezone-aware selection timestamp; must accompany --select-listing')
    args = parser.parse_args(argv)
    if (args.select_listing is None) != (args.selected_at is None):
        parser.error('--select-listing and --selected-at must be supplied together')
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
            raise ValidationError('An output file already exists. Use a new --output prefix; existing files will not be overwritten')
        contents = [json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', render_markdown(report)]
        if packet is not None:
            contents.append(json.dumps(packet, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        json_path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation protects existing files even if another process races us.
        for path, content in zip(paths, contents):
            with path.open('x', encoding='utf-8') as stream:
                stream.write(content)
        print(f'Generated (synthetic only): {md_path}\nStructured report: {json_path}')
        print(f"Recommendation run: {report['recommendation_run_id']}")
        if packet is not None:
            print(f'Selection evidence package (not sent): {paths[2]}')
        print('Results: ' + ', '.join(f'{key}={value}' for key, value in report['counts'].items()))
        return 0
    except (ValidationError, OSError, ValueError, UnicodeError) as exc:
        print(f'Input or output error:{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
