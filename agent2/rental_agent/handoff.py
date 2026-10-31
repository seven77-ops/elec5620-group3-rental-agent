"""Prepare a local evidence packet after explicit selection; never send it automatically."""

from copy import deepcopy

from .contracts import validate_contract
from .engine import evaluate
from .validation import ValidationError, require, text, timestamp


def build_selected_listing_evidence(report, dataset, listing_id, *, selected_at, user_confirmed):
    require(user_confirmed is True, 'selection.user_confirmed', 'Explicit user selection is required; the top-ranked listing is not selected automatically')
    text(listing_id, 'selection.listing_id')
    selected_time = timestamp(selected_at, 'selection.selected_at')
    validate_contract('RecommendationReport', report)
    if 'comparison' in report:
        comparison = report['comparison']
        require(comparison['after_run_id'] == report['recommendation_run_id']
                and comparison['after_profile_version'] == report['profile_version']
                and comparison['after_weights'] == report['effective_weights'],
                'selection.comparison', 'The comparison target run, version or weights do not match this report')
    require(selected_time >= timestamp(report['as_of'], 'report.as_of'),
            'selection.selected_at', 'Cannot be earlier than the recommendation snapshot')
    # Recompute the score/evidence snapshot; comparison history is not selected evidence.
    original = evaluate(report['profile'], dataset, as_of=report['as_of'])
    supplied = {k: v for k, v in report.items() if k != 'comparison'}
    require(supplied == original, 'selection.report', 'The report does not match the original data. Re-evaluate; scores and run references cannot be altered')
    require(any(row['listing_id'] == listing_id for row in original['eligible']),
            'selection.listing_id', 'Only eligible listings in this run can be selected. Missing, duplicate, pending and excluded items cannot be handed off directly')
    # A stale recommendation does not become current merely because the user clicks it.
    current = evaluate(report['profile'], dataset, as_of=selected_at)
    assessment = next((row for row in current['eligible'] if row['listing_id'] == listing_id), None)
    if assessment is None:
        raise ValidationError('selection.freshness: Listing details or evidence are expired or incomplete at selection time. Refresh the data and generate recommendations again')
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
        'unresolved_items': list(assessment['issues']) + ['No tenancy agreement has been supplied or reviewed. This evidence package does not approve signing.'],
        'data_limitations': list(original['data_limitations']) + [
            'user_confirmed is an explicit caller declaration, not user authentication or a signature. This local prototype has not sent data to Agent 3.',
            'Source-fact and freshness checks use the supplied synthetic snapshot. They do not establish an on-site property verification or renewed contact with the provider.',
        ],
    }
    validate_contract('SelectedListingEvidence', packet)
    return packet
