"""Prepare a local evidence packet after explicit selection; never send it automatically."""

from copy import deepcopy

from .contracts import validate_contract
from .engine import evaluate
from .validation import ValidationError, require, text, timestamp


def build_selected_listing_evidence(report, dataset, listing_id, *, selected_at, user_confirmed):
    require(user_confirmed is True, 'selection.user_confirmed', '必须有用户明确选择，不自动选择第一名')
    text(listing_id, 'selection.listing_id')
    selected_time = timestamp(selected_at, 'selection.selected_at')
    validate_contract('RecommendationReport', report)
    if 'comparison' in report:
        comparison = report['comparison']
        require(comparison['after_run_id'] == report['recommendation_run_id']
                and comparison['after_profile_version'] == report['profile_version']
                and comparison['after_weights'] == report['effective_weights'],
                'selection.comparison', '比较结果的目标批次、版本或权重与本报告不一致')
    require(selected_time >= timestamp(report['as_of'], 'report.as_of'),
            'selection.selected_at', '不能早于推荐快照时点')
    # Recompute the score/evidence snapshot; comparison history is not selected evidence.
    original = evaluate(report['profile'], dataset, as_of=report['as_of'])
    supplied = {k: v for k, v in report.items() if k != 'comparison'}
    require(supplied == original, 'selection.report', '报告与原始数据不一致；请重新评估，禁止修改分数或批次引用')
    require(any(row['listing_id'] == listing_id for row in original['eligible']),
            'selection.listing_id', '只能选择本批次合格房源；不存在、重复、待确认和排除项不能直接交接')
    # A stale recommendation does not become current merely because the user clicks it.
    current = evaluate(report['profile'], dataset, as_of=selected_at)
    assessment = next((row for row in current['eligible'] if row['listing_id'] == listing_id), None)
    if assessment is None:
        raise ValidationError('selection.freshness: 选择时房源或证据已失效/不完整，须先刷新数据并重新推荐')
    snapshot = next(row for row in dataset['listings'] if row['listing_id'] == listing_id)
    related = [row for row in dataset['listings']
               if (row['source'], row['source_listing_id']) == (snapshot['source'], snapshot['source_listing_id'])]
    packet = {
        'schema_version': '1.0', 'data_mode': 'synthetic_demo', 'recipient': 'ContractAgent',
        'handoff_status': 'prepared_not_sent', 'recommendation_run_id': original['recommendation_run_id'],
        'selection_check_run_id': current['recommendation_run_id'],
        'dataset_fingerprint': original['dataset_fingerprint'], 'profile_fingerprint': original['profile_fingerprint'],
        'search_id': original['search_id'], 'profile_version': original['profile_version'],
        'listing_id': listing_id, 'selected_at': selected_at, 'user_confirmed': True,
        'profile': deepcopy(original['profile']), 'listing_snapshot': deepcopy(snapshot),
        'source_records': deepcopy(related), 'assessment': deepcopy(assessment),
        'unresolved_items': list(assessment['issues']) + ['尚未提供或审查租赁合同；本证据包不代表批准签约。'],
        'data_limitations': list(original['data_limitations']) + [
            'user_confirmed 是调用方显式声明，不是用户鉴权或签名；本地原型未发送数据给 Agent 3。',
            '来源事实和时效检查基于提供的模拟快照，不等于已实地验证房源真实或已重新联系供方。',
        ],
    }
    validate_contract('SelectedListingEvidence', packet)
    return packet
