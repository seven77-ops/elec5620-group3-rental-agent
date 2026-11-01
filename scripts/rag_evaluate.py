"""Compare annotated NSW passage retrieval; optional explicit cloud ranking/generation.

Defaults to a temporary offline keyword index. External runs copy the existing
persisted public index; the live index and application runtime are never changed.
Exit 0 means report written, not legal quality passed. Use --strict for CI gates.
"""
import argparse
import json
import os
import sqlite3
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.app.rag.evaluation import MODES, evaluate, write_report
from server.app.rag.index import KnowledgeIndex
from server.app.rag.provider import RetrievalProvider
from scripts.local_ai_env import load_ai_env


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=ROOT/'data/knowledge/evaluation.en.json')
    parser.add_argument('--corpus', type=Path, default=ROOT/'data/knowledge/en/documents.json')
    parser.add_argument('--runtime', type=Path, default=ROOT/'.runtime', help='Read-only source for the existing public rag.sqlite3')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/frontend/2026-10-30-rag-quality-offline.json')
    parser.add_argument('--external', action='store_true', help='Send only annotated synthetic public questions/source passages to configured embedding and rerank endpoints')
    parser.add_argument('--generate', action='store_true', help='Also send retrieved public passages to chat model for production validated answers; requires --external')
    parser.add_argument('--generation-mode', action='append', choices=MODES, help='Repeat to generate with multiple modes (default hybrid_rerank only)')
    parser.add_argument('--concurrency', type=int, choices=(1, 2), default=2)
    parser.add_argument('--limit', type=int, help='First N cases; report records subset fingerprint')
    parser.add_argument('--ids', nargs='+', help='Evaluate only these case ids')
    parser.add_argument('--as-of', type=date.fromisoformat, default=datetime.now(ZoneInfo('Australia/Sydney')).date(), help='Freshness policy date YYYY-MM-DD')
    parser.add_argument('--strict', action='store_true', help='Exit 1 for passage misses, failed answer checks, or requested cloud modes skipped/degraded; no human support verdict implied')
    args = parser.parse_args(argv)
    if args.generate and not args.external:
        parser.error('--generate requires --external')
    if args.generation_mode and not args.generate:
        parser.error('--generation-mode requires --generate')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    cases = json.loads(args.cases.read_text()); corpus = json.loads(args.corpus.read_text())
    if args.ids:
        selected = set(args.ids)
        missing = selected - {c['id'] for c in cases}
        if missing: parser.error('Unknown case ids: ' + ', '.join(sorted(missing)))
        cases = [c for c in cases if c['id'] in selected]
    if args.limit: cases = cases[:args.limit]
    env = load_ai_env(ROOT/'.env', os.environ) if args.external else {}
    provider = RetrievalProvider(env)
    ai_provider = None
    if args.generate:
        from server.app.ai.provider import ModelProvider
        ai_provider = ModelProvider(env)
        if not ai_provider.public_config()['configured']:
            parser.error('Generation is not configured; no generation requests made')
    with tempfile.TemporaryDirectory(prefix='rag-quality-') as folder:
        expected = KnowledgeIndex(Path(folder)/'expected.sqlite3'); expected.publish(corpus)
        if args.external:
            source = (args.runtime/'rag.sqlite3').resolve()
            if not source.is_file(): parser.error('Existing semantic index missing; run scripts/rag_index.py --embed first')
            # SQLite backup includes a consistent snapshot even when a WAL exists.
            path = Path(folder)/'evaluation.sqlite3'
            with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as original, sqlite3.connect(path) as target:
                original.backup(target)
            index = KnowledgeIndex(path)
            if index.status()['index_version'] != expected.status()['index_version']:
                parser.error('Persisted index differs from --corpus; rebuild it explicitly before comparison')
        else:
            index = expected
        report = evaluate(index, cases, provider=provider, external=args.external, generate=args.generate,
                          ai_provider=ai_provider, generation_modes=tuple(args.generation_mode or ['hybrid_rerank']),
                          concurrency=args.concurrency, as_of=args.as_of)
        report['inputs'] = {'cases': str(args.cases), 'corpus': str(args.corpus),
                            'persisted_index_copied': args.external,
                            'generation_modes_requested': args.generation_mode or ['hybrid_rerank'] if args.generate else []}
        output = write_report(report, args.output)
    summary = {'report': str(output), 'review_sheet': str(output.with_suffix('.review.json')),
               'case_count': report['case_count'], 'human_review_completed': False,
               'modes': {name: {'status': mode['status'], 'summary': mode['summary'], 'failed_cases': mode.get('failed_cases', [])}
                         for name, mode in report['modes'].items()},
               'external_calls': report['external_calls'], 'timings_ms': report['timings_ms']}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    failed = any(mode.get('failed_cases') for mode in report['modes'].values())
    if args.external: failed |= any(mode['status'] != 'completed' for mode in report['modes'].values())
    return 1 if args.strict and failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
