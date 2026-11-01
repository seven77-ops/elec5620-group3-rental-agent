"""Reviewable passage evaluation. Mechanical checks do not establish legal correctness.

No live index publication, private documents, hidden model judge, or network call by
implicit default. External adapters are injected and query embeddings shared.
"""
import copy
from collections import Counter
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from .provider import RetrievalError
from .scope import retrieval_source_types,retrieval_query

MODES = ('keyword', 'hybrid', 'hybrid_rerank')
LIMITS = (
    'Passage recall measures annotated section plus literal passage cues in the captured NSW corpus. '
    'It is not exhaustive relevance, legal accuracy, or a current-law verification. '
    'Exact-citation checks establish literal source membership only, not entailment. '
    'Regex condition checks are fallible review aids and may miss negation, exceptions, translation or unsupported reasoning. '
    'All claim-support and legal judgments remain pending human review. '
    'Unsupported questions are excluded from recall denominators; retrieved context alone is not an answer.'
)


def all_rows(index):
    with index.connect() as db:
        return {r['chunk_id']: r for (body,) in db.execute('SELECT body FROM chunks') for r in [json.loads(body)]}


def target_matches(target, row):
    return (target['document_id'] == row.get('document_id') and target['section'] == row.get('section')
            and all(cue in row.get('text', '') for cue in target['text_contains']))


def validate_cases(cases, index):
    rows = list(all_rows(index).values()); seen = set()
    if not cases:
        raise ValueError('No evaluation cases selected')
    for case in cases:
        identifier = case.get('id')
        if not isinstance(identifier, str) or identifier in seen:
            raise ValueError('Cases need unique string ids')
        seen.add(identifier)
        for field in ('question', 'language', 'category', 'answerability'):
            if not isinstance(case.get(field), str) or not case[field]:
                raise ValueError(f'{identifier}: missing {field}')
        if case['language'] not in ('en', 'zh') or len(case['question']) > 2000:
            raise ValueError(f'{identifier}: invalid question or language')
        for field in ('targets', 'required_claim_patterns', 'forbidden_claim_patterns', 'expected_conditions', 'manual_review'):
            if not isinstance(case.get(field), list):
                raise ValueError(f'{identifier}: missing {field}')
        if not case['expected_conditions'] or not case['manual_review']:
            raise ValueError(f'{identifier}: missing review annotations')
        if bool(case['targets']) != (case['answerability'] == 'supported'):
            raise ValueError(f'{identifier}: answerability and target mismatch')
        for target in case['targets']:
            if (not isinstance(target.get('text_contains'), list) or not target['text_contains']
                    or not all(isinstance(cue, str) and cue for cue in target['text_contains'])
                    or not any(target_matches(target, row) for row in rows)):
                raise ValueError(f'{identifier}: target passage does not exist in this corpus')
        for pattern in case['required_claim_patterns'] + case['forbidden_claim_patterns']:
            re.compile(pattern)


def score_retrieval(case, rows):
    targets = case['targets']; ranks = []
    for target in targets:
        ranks.append(next((i + 1 for i, row in enumerate(rows) if target_matches(target, row)), None))
    return {
        **{f'recall_at_{k}': sum(rank is not None and rank <= k for rank in ranks) / len(targets) if targets else None for k in (1, 3, 6)},
        'reciprocal_rank': 1 / min(r for r in ranks if r is not None) if any(ranks) else (0.0 if targets else None),
        'target_ranks': ranks,
        'all_targets_at_6': all(rank is not None and rank <= 6 for rank in ranks) if targets else None,
        'retrieved_on_unsupported': bool(rows) if not targets else None,
    }


def score_answer(case, answer, source_rows):
    claims = answer.get('claims', []); citations = answer.get('citations', [])
    def exact(item):
        row = source_rows.get(item.get('evidence_id'))
        return bool(row and isinstance(item.get('quote'), str) and item['quote'].strip() and item['quote'] in row['text'])
    # Empty citation lists must not pass an answered claim. Check the claim's own
    # quote and its matching returned citation rather than any quote in the batch.
    exact_citations = all(exact(c) for c in citations) and all(
        exact(claim) and any(c.get('evidence_id') == claim.get('evidence_id') and c.get('quote') == claim.get('quote') for c in citations)
        for claim in claims)
    if answer.get('status') == 'answered' and not claims:
        exact_citations = False
    text = '\n'.join(c.get('text', '') for c in claims)
    missing = [p for p in case['required_claim_patterns'] if not re.search(p, text, re.I)]
    forbidden = [p for p in case['forbidden_claim_patterns'] if re.search(p, text, re.I)]
    unsupported = case['answerability'] != 'supported'
    abstained = not claims and answer.get('status') != 'answered'
    condition_ok = not missing and not forbidden
    answered = bool(claims) and answer.get('status') == 'answered'
    return {'exact_citations': exact_citations, 'condition_heuristics_passed': condition_ok,
            'generation_outcome': answer.get('generation_outcome'),
            'requested_language_not_delivered': bool(answer.get('answer_language') not in (None,case['language']) and claims),
            'missing_required_patterns': missing, 'matched_forbidden_patterns': forbidden,
            'abstained': abstained, 'has_unknowns': bool(answer.get('unknowns')),
            'automated_checks_passed': exact_citations and not forbidden and (abstained if unsupported else answered and condition_ok),
            'support_judgment': 'pending_human_review'}


def _fresh(row, as_of):
    age = (as_of - date.fromisoformat(row['checked_at'])).days
    return 0 <= age <= 90


def _fuse(rankings):
    scores = {}; rows = {}
    for ranking in rankings:
        for rank, row in enumerate(ranking, 1):
            key = row['chunk_id']; rows[key] = row
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    return [rows[key] for key in sorted(scores, key=lambda key: scores[key], reverse=True)[:30]]


def _summary(results):
    scored = [r for r in results if r['retrieval']['recall_at_6'] is not None]
    generated = [r for r in results if 'answer_checks' in r]
    times = sorted(r['elapsed_ms'] for r in results)
    return {'evaluated': len(results), 'supported_cases': len(scored), 'unsupported_cases': len(results) - len(scored),
            **{f'mean_recall_at_{k}': round(sum(r['retrieval'][f'recall_at_{k}'] for r in scored) / len(scored), 4) if scored else None for k in (1, 3, 6)},
            'mean_reciprocal_rank': round(sum(r['retrieval']['reciprocal_rank'] for r in scored) / len(scored), 4) if scored else None,
            'all_targets_at_6_count': sum(r['retrieval']['all_targets_at_6'] is True for r in scored),
            'degraded_cases': sum(bool(r['degradation']) for r in results),
            'generated_cases': len(generated),
            'automated_answer_checks_passed': sum(r['answer_checks']['automated_checks_passed'] for r in generated),
            'exact_citation_failures': sum(not r['answer_checks']['exact_citations'] for r in generated),
            'model_abstentions': sum(r.get('generation_observation', {}).get('valid_model_abstention', False) for r in generated),
            'generation_provider_failures': sum(bool(r.get('generation_observation', {}).get('error_code')) for r in generated),
            'generation_outcomes': dict(Counter(r['answer_checks'].get('generation_outcome') or 'unrecorded' for r in generated)),
            'requested_language_not_delivered': sum(r['answer_checks'].get('requested_language_not_delivered',False) for r in generated),
            'human_support_pass_rate': None,
            'retrieval_latency_ms_p50': times[len(times) // 2] if times else None,
            'retrieval_latency_ms_p95': times[min(len(times)-1, int(len(times)*.95))] if times else None}


def evaluate(index, cases, *, provider=None, external=False, generate=False, ai_provider=None,
             generation_modes=('hybrid_rerank',), concurrency=2, as_of=None):
    """Compare fixed retrieval modes, optionally generating answers through production validation.

    Query vectors are requested once per unique question in batches of 10. Two
    workers maximum for embedding batches, reranking and generation. The original
    persisted index is read only throughout this function.
    """
    if generate and (not external or ai_provider is None):
        raise ValueError('Generation requires explicit external consent and an AI provider')
    if any(mode not in MODES for mode in generation_modes):
        raise ValueError('Unknown generation mode')
    if not 1 <= concurrency <= 2:
        raise ValueError('Concurrency must be 1 or 2')
    as_of = as_of or datetime.now().date(); started = time.monotonic()
    validate_cases(cases, index)
    index_status = index.status(); rows = all_rows(index)
    version = index_status['index_version']; provider_status = provider.status() if provider else {}
    compatible = bool(provider and any(v['model'] == provider.model and v['dimensions'] == provider.dimensions and v['chunks'] == len(rows)
                                      for v in index_status['vector_indexes']))
    reason = ('external_disabled' if not external else 'embedding_not_configured' if not provider_status.get('embedding_configured')
              else 'complete_compatible_vector_index_missing' if not compatible else None)
    report = {'schema_version': 2, 'created_at': datetime.now(timezone.utc).isoformat(), 'as_of': as_of.isoformat(),
              'dataset_sha256': hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
              'case_count': len(cases), 'index': {**index_status, 'stale_chunks': sum(not _fresh(r, as_of) for r in rows.values())},
              'models': {k: v for k, v in provider_status.items() if k in ('embedding_model', 'rerank_model', 'dimensions')},
              'external_enabled': external, 'generation_enabled': generate, 'concurrency': concurrency,
              'external_calls': {'embedding_requests': 0, 'rerank_requests': 0, 'generation_attempts': 0},
              'timings_ms': {}, 'modes': {}, 'human_review_completed': False, 'limitations': LIMITS}
    if generate:
        config = ai_provider.public_config()
        report['models']['generation_model'] = config.get('model')
    vectors = {}; errors = {}; query_times = {}; query_started = time.monotonic()
    if reason is None:
        questions = list(dict.fromkeys(c['question'] for c in cases))
        batches = [questions[n:n+10] for n in range(0, len(questions), 10)]
        def embed_batch(batch):
            tick = time.monotonic()
            try:
                result = provider.embed(batch, timeout=30)
                return batch, result, None, (time.monotonic()-tick)*1000
            except RetrievalError as error:
                return batch, None, str(error), (time.monotonic()-tick)*1000
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            for batch, result, error, elapsed in pool.map(embed_batch, batches):
                report['external_calls']['embedding_requests'] += 1
                for i, question in enumerate(batch):
                    query_times[question] = elapsed / len(batch)
                    if error: errors[question] = 'embedding:' + error
                    else: vectors[question] = result[i]
    report['timings_ms']['query_embeddings_wall'] = round((time.monotonic()-query_started)*1000, 2)
    keyword = {}; hybrid = {}
    for mode in MODES:
        skip = reason if mode != 'keyword' else None
        if mode == 'hybrid_rerank' and not skip and not provider_status.get('rerank_configured'):
            skip = 'rerank_not_configured'
        if skip:
            report['modes'][mode] = {'status': 'skipped', 'reason': skip, 'cases': [], 'summary': _summary([])}
            continue
        mode_started = time.monotonic()
        def retrieve(case):
            question = case['question']; tick = time.monotonic(); degradation = []
            semantic_used = False; rerank_used = False
            if mode == 'keyword':
                hits = [r for r in index.search(retrieval_query(question),source_types=retrieval_source_types(question)) if _fresh(r, as_of)]
                keyword[case['id']] = hits
            else:
                if mode == 'hybrid':
                    semantic = []
                    if question in vectors:
                        semantic = [r for r in index.vector_search(vectors[question], provider.model, provider.dimensions,source_types=retrieval_source_types(question)) if _fresh(r, as_of)]
                        semantic_used = True
                    else: degradation.append(errors.get(question, 'embedding:unavailable'))
                    hits = _fuse([keyword[case['id']], semantic]); hybrid[case['id']] = (hits, semantic_used, list(degradation))
                else:
                    hits, semantic_used, degradation = hybrid[case['id']]
                    hits = list(hits); degradation = list(degradation)
                    if hits:
                        try:
                            hits = [hits[i] for i in provider.rerank(question, [r.get('embedding_text',r['text']) for r in hits])]
                            rerank_used = True
                        except RetrievalError as error: degradation.append('rerank:' + str(error))
            elapsed = (time.monotonic()-tick)*1000
            # Include shared embedding cost in both hybrid modes. Rerank mode also
            # includes fusion time; wall totals separately record actual run cost.
            if mode != 'keyword': elapsed += query_times.get(question, 0)
            if mode == 'hybrid_rerank': elapsed += next(r['fusion_elapsed_ms'] for r in report['modes']['hybrid']['cases'] if r['id'] == case['id'])
            result = {'id': case['id'], 'question': question, 'language': case['language'], 'category': case['category'],
                      'answerability': case['answerability'], 'targets': case['targets'], 'expected_conditions': case['expected_conditions'],
                      'manual_review': case['manual_review'], 'required_claim_patterns': case['required_claim_patterns'],
                      'forbidden_claim_patterns': case['forbidden_claim_patterns'],
                      'retrieved': hits[:6], 'retrieval': score_retrieval(case, hits[:6]),
                      'semantic_used': semantic_used, 'rerank_used': rerank_used, 'degradation': degradation,
                      'elapsed_ms': round(elapsed, 2), 'fusion_elapsed_ms': round((time.monotonic()-tick)*1000, 2)}
            return result
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            results = list(pool.map(retrieve, cases))
        if mode == 'hybrid_rerank':
            report['external_calls']['rerank_requests'] += sum(bool(hybrid[c['id']][0]) for c in cases)
        report['timings_ms'][mode + '_retrieval_wall'] = round((time.monotonic()-mode_started)*1000, 2)
        if generate and mode in generation_modes:
            from .service import KnowledgeService, ANSWER_SCHEMA
            from ..ai.provider import ProviderError
            from jsonschema import Draft202012Validator
            gen_started = time.monotonic()
            def generate_answer(pair):
                case, result = pair
                service = KnowledgeService.__new__(KnowledgeService)
                observation = {'attempted': False, 'valid_model_abstention': False}
                class RecordedChat:
                    def call(self, context):
                        observation['attempted'] = True
                        try:
                            raw, meta = ai_provider.call(context)
                            observation['raw_response'] = raw
                            observation['valid_model_abstention'] = not list(Draft202012Validator(ANSWER_SCHEMA).iter_errors(raw)) and not raw['claims']
                            return raw, meta
                        except ProviderError as error:
                            observation['error_code'] = error.code
                            raise
                service.index = index; service.ctx = SimpleNamespace(ai_provider=RecordedChat())
                service.retrieve = lambda question, external: {'evidence': copy.deepcopy(result['retrieved']), 'index_version': version,
                    'retrieval_methods': [mode], 'warnings': list(result['degradation'])}
                tick = time.monotonic()
                answer = service.answer(case['question'], True, case['language'])
                checks = score_answer(case, answer, {r['chunk_id']: r for r in result['retrieved']})
                if case['answerability'] != 'supported' and observation['attempted'] and not observation['valid_model_abstention']:
                    checks['automated_checks_passed'] = False
                return {**result, 'answer': answer, 'answer_checks': checks, 'generation_observation': observation,
                        'generation_elapsed_ms': round((time.monotonic()-tick)*1000, 2)}
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                results = list(pool.map(generate_answer, zip(cases, results)))
            report['external_calls']['generation_attempts'] += sum(bool(r['retrieved']) for r in results)
            report['timings_ms'][mode + '_generation_wall'] = round((time.monotonic()-gen_started)*1000, 2)
        report['modes'][mode] = {'status': 'degraded' if any(r['degradation'] for r in results) else 'completed',
                               'cases': results, 'summary': _summary(results),
                               'failed_cases': [r['id'] for r in results if r['retrieval']['all_targets_at_6'] is False
                                                or ('answer_checks' in r and not r['answer_checks']['automated_checks_passed'])]}
    if index.status()['index_version'] != version:
        raise ValueError('Index changed during evaluation; discard this comparison')
    report['timings_ms']['total_wall'] = round((time.monotonic()-started)*1000, 2)
    return report


def write_report(report, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    review = []
    for mode, data in report['modes'].items():
        for result in data['cases']:
            review.append({k: result[k] for k in ('id', 'question', 'language', 'category', 'answerability', 'targets', 'expected_conditions',
                                                 'manual_review', 'required_claim_patterns', 'forbidden_claim_patterns', 'retrieved', 'degradation')}
                          | {'mode': mode, 'answer': result.get('answer'), 'automated_checks': result.get('answer_checks'),
                             'generation_observation': result.get('generation_observation'),
                             'human_supported': None, 'human_conditions_preserved': None, 'human_abstention_appropriate': None,
                             'reviewer': None, 'reviewed_at': None, 'notes': ''})
    path.with_suffix('.review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
    return path
