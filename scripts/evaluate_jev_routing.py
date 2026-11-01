"""Validate synthetic routing fixtures or explicitly measure Jev against reviewed labels."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.local_ai_env import load_ai_env
from server.app.routing.jev import JevProvider, JevError, ROUTES


def load_cases(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    cases = value['cases']
    if (not isinstance(cases, list) or not cases or len(cases) > 1000
        or len({c['id'] for c in cases}) != len(cases)
        or any(c['expected_route'] not in ROUTES or not isinstance(c['message'], str)
               or not 0 < len(c['message']) <= 3000 for c in cases)):
        raise ValueError('Fixtures need unique IDs, supported labels and bounded messages')
    return value, cases


def metrics(rows):
    successful = [r for r in rows if r.get('predicted') in ROUTES]
    count = len(rows)
    per_class = {}
    for label in ROUTES:
        tp = sum(r['expected'] == label and r.get('predicted') == label for r in rows)
        actual = sum(r['expected'] == label for r in rows)
        predicted = sum(r.get('predicted') == label for r in rows)
        per_class[label] = {'precision': tp / predicted if predicted else 0,
                            'recall': tp / actual if actual else 0, 'count': actual}
    delays = sorted(r['duration_ms'] for r in successful)
    return {'count': count, 'completed': len(successful),
            'accuracy_including_failures': sum(r['expected'] == r.get('predicted') for r in rows) / count if count else None,
            'accepted_fraction': sum(bool(r.get('accepted')) for r in rows) / count if count else None,
            'p95_request_ms': delays[max(0, math.ceil(.95 * len(delays)) - 1)] if delays else None,
            'known_cost_usd': sum(r['cost'] for r in rows if r.get('cost') is not None),
            'cost_observed_calls': sum(r.get('cost') is not None for r in rows), 'per_class': per_class}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', default=str(ROOT / 'data/evaluation/jev-routing.json'))
    parser.add_argument('--run', action='store_true', help='Explicitly make paid OpenRouter requests; requires its separate key')
    parser.add_argument('--output', help='New JSON result file; existing files are not overwritten')
    args = parser.parse_args()
    try:
        fixture, cases = load_cases(args.fixtures)
        if not args.run:
            print(json.dumps({'status': 'fixtures_validated_only', 'count': len(cases),
                'labels': dict(Counter(c['expected_route'] for c in cases)),
                'label_status': fixture.get('label_status'), 'model_requests': 0}, ensure_ascii=False, indent=2))
            return 0
        if not args.output:
            raise ValueError('--run requires --output to retain evaluation evidence')
        target = Path(args.output)
        if target.exists() or target.is_symlink():
            raise ValueError('Evaluation output already exists; choose a new file')
        provider = JevProvider(load_ai_env(ROOT / '.env', dict(os.environ)))
        if not provider.configured:
            raise ValueError('Fill OPENROUTER_API_KEY first; the Alibaba key is not used')
        rows = []
        for case in cases:
            row = {'id': case['id'], 'expected': case['expected_route']}
            try:
                decision = provider.classify({'message': case['message'], 'conversation': case.get('conversation', {})})
                probabilities = sorted(decision['probabilities'].values(), reverse=True)
                row.update(predicted=decision['route'], confidence=decision['confidence'],
                    accepted=decision['route'] != 'unclear_or_other' and decision['confidence'] >= provider.min_confidence
                        and probabilities[0] - probabilities[1] >= provider.min_margin,
                    duration_ms=decision['duration_ms'], cost=decision['usage'].get('cost'), model=decision['model'])
            except JevError as error:
                row.update(predicted=None, accepted=False, error=error.code)
            rows.append(row)
        report = {'label_status': fixture.get('label_status'), 'configuration': provider.public_config(),
                  'metrics': metrics(rows), 'results': rows,
                  'limitations': 'Synthetic label baseline; review labels and use held-out data. This measures routing, not end-to-end task success.'}
        with target.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report['metrics'], ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
