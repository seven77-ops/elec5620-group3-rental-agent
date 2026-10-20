"""Independent scripted local handoff check. All data/choices/consent are synthetic."""
from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'agent1'))
sys.path.insert(0, str(ROOT / 'agent3'))
from preference_agent.service import PreferenceAgent
from preference_agent.llm import ManualOnly
from preference_agent.store import Store
from preference_agent.fields import flatten
from preference_agent.handover import HandoverService
from preference_agent.cli import export_case
from rental_agent.handoff import build_selected_listing_evidence
from contract_agent.document import load_document
from contract_agent.intake import receive_review
from contract_agent.errors import ContractError


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def run():
    checks = []
    with tempfile.TemporaryDirectory(prefix='pr6-chain-') as directory:
        tmp = Path(directory)
        store = Store(tmp / 'agent1.sqlite3')
        agent = PreferenceAgent(store, ManualOnly())
        case = agent.startCollection()['case_id']
        agent.setFields(case, flatten(load(ROOT / 'agent2/data/demo/profiles/commute.json')))
        handover = HandoverService(store)
        dataset = load(ROOT / 'agent2/data/demo/listings.json')
        try:
            handover.submitConfirmed(case, dataset)
        except ValueError:
            checks.append('unconfirmed_search_blocked')
        else:
            raise AssertionError('Unconfirmed search was allowed')
        token = agent.reviewDraft(case)['confirmation_token']
        record = agent.confirmProfile(case, token, 'REVIEWER_SCRIPTED_SYNTHETIC_ACTOR')
        task = handover.submitConfirmed(case, dataset)
        assert task['status'] == 'completed'
        assert task['report']['counts'] == {
            'input': 30, 'eligible': 15, 'pending': 9, 'excluded': 5, 'duplicates': 1}
        checks.append('actual_agent1_to_agent2')
        assert handover.submitConfirmed(case, dataset) == task
        checks.append('agent1_retry_reuses_task')
        export_case(store, case, tmp / 'export')
        assert load(tmp / 'export/rental-profile.json') == record['profile']
        checks.append('agent1_profile_export_matches_saved_record')
        expected = load(ROOT / 'integration/agent1-to-agent2/expected.json')
        packet = build_selected_listing_evidence(
            task['report'], dataset, 'DEMO-006', selected_at=expected['selectedAt'],
            user_confirmed=True)  # Scripted test choice, not a human tenancy decision.
        checks.append('new_selection_generated_from_agent1_report')
        document = load_document(
            ROOT / 'agent3/data/demo/agreements/selection-demo.txt', consent=True)
        args = dict(consent=True, selection=packet, request_id='review-pr6-agent123',
                    as_of=expected['contractReferenceDate'], store=tmp / 'receipts.sqlite3')
        review, created = receive_review(document, **args)
        assert created and review['status'] == 'Reviewed'
        checks.append('agent3_receive_reviewed')
        for field in ('search_id', 'profile_version', 'listing_id',
                      'recommendation_run_id', 'selection_check_run_id'):
            assert review['intake'][field] == packet[field]
        checks.append('intake_ids_and_versions_match')
        replay, newly_created = receive_review(document, **args)
        assert not newly_created and replay == review
        checks.append('agent3_retry_returns_original')
        try:
            receive_review(document, **{**args, 'consent': False})
        except ContractError:
            checks.append('missing_contract_consent_rejected')
        else:
            raise AssertionError('Contract processing without consent was allowed')
        return {
            'scope': 'Independent local synthetic scripted check; no live LLM or real tenancy action',
            'checks_passed': len(checks), 'passed': checks,
            'agent2_counts': task['report']['counts'],
            'listing_id': review['intake']['listing_id'],
            'profile_version': review['intake']['profile_version'],
            'status': review['status'], 'review_id': review['review_id'],
            'synthetic_selected_at': expected['selectedAt'],
            'fixed_contract_reference_date': expected['contractReferenceDate'],
            'duplicate_review_identical': replay == review,
        }


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False, indent=2))
