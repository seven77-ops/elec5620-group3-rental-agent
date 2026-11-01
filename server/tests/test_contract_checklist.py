"""Checklist projections use synthetic uploads and injected model transports only."""
import copy
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from server.tests.ai_fixtures import TestProvider


COMPLETE = """Synthetic agreement - TEST ONLY
Property address: 42 Example Street, Sydney NSW 2000
Landlord: Example Owner
Tenant: Example Tenant
Weekly rent: AUD $500 per week whole property
Bond: AUD $2000
Start date: 2026-11-01
End date: 2027-11-01
"""


def pdf_bytes(text):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
        DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(('BT /F1 10 Tf 40 740 Td ' + ' '.join(
        ('0 -18 Td ' if i else '') + '(' + line + ') Tj'
        for i, line in enumerate(text.splitlines())) + ' ET').encode())
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class ContractChecklistTests(unittest.TestCase):
    def setUp(self):
        from server.tests.legacy_app import create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.provider = TestProvider()
        self.app = create_app(runtime_dir=self.tmp.name, ai_provider=self.provider)
        self.client = TestClient(self.app)
        self.repo = self.app.state.repository
        self.case_id = self.post('/cases', {}).json()['case_id']
        self.consent_id = self.post(f'/cases/{self.case_id}/contract-consents',
            {'confirmed': True, 'scope': 'document'}).json()['consent_id']

    def post(self, path, body):
        return self.client.post('/api/v1' + path, json=body)

    def upload(self, text=COMPLETE, *, pdf=False, request='upload'):
        response = self.client.post(f'/api/v1/cases/{self.case_id}/contract-reviews',
            content=pdf_bytes(text) if pdf else text.encode(), headers={
                'Content-Type': 'application/octet-stream', 'X-Consent-Id': self.consent_id,
                'X-Request-Id': request, 'X-Filename': 'synthetic.pdf' if pdf else 'synthetic.txt'})
        self.assertEqual(response.status_code, 200, response.text)
        self.review = response.json()['review']
        self.review_id = self.review['review_id']
        return self.review

    def analyze(self):
        response = self.post(f'/contract-reviews/{self.review_id}/ai-analyses',
            {'request_id': 'analysis', 'expected_version': 1, 'allow_external_ai': True})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def snapshot(self):
        with self.repo.transaction() as db:
            return db.execute('SELECT kind,id,body FROM objects ORDER BY kind,id').fetchall()

    def checklist(self):
        before = self.snapshot()
        calls = len(self.provider.inputs)
        response = self.client.get(f'/api/v1/contract-reviews/{self.review_id}/checklist')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(before, self.snapshot(), 'GET must not change any business or sidecar state')
        self.assertEqual(calls, len(self.provider.inputs), 'GET must never call the model')
        result = response.json()
        self.assertEqual(result['total'], len(result['passed']) + len(result['attention']))
        ids = [row['id'] for row in result['passed'] + result['attention']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(row['status'] == 'passed' for row in result['passed']))
        self.assertTrue(all(row['status'] in {'issue', 'needs_confirmation'} for row in result['attention']))
        self.assertEqual(result['review_version'], self.review['version'])
        return result

    def rows(self, result):
        return {row['id']: row for row in result['passed'] + result['attention']}

    def update_review(self, update):
        with self.repo.transaction() as db:
            saved = self.repo.get(db, 'review', self.review_id)
            update(saved['review'])
            self.repo.put(db, 'review', self.review_id, saved)

    def update_analysis(self, analysis, update):
        with self.repo.transaction() as db:
            record = self.repo.get(db, 'ai_analysis', analysis['analysis_id'])
            update(record)
            self.repo.put(db, 'ai_analysis', analysis['analysis_id'], record)

    def test_uploaded_pdf_date_error_visible_despite_human_review_status(self):
        self.upload(COMPLETE.replace('2027-11-01', '2026-10-01'), pdf=True)
        self.assertEqual(self.review['status'], 'Awaiting Human Review')
        result = self.checklist()
        self.assertEqual(result['document_name'], 'synthetic.pdf')
        row = self.rows(result)['date_order']
        self.assertEqual(row['status'], 'issue')
        self.assertIn('not after', row['detail'])
        self.assertTrue(all(ev['page'] == 1 for ev in row['evidence']))

    def test_complete_contract_has_real_checks_without_legal_presence_claims(self):
        self.upload()
        result = self.checklist()
        rows = self.rows(result)
        for field in ('address', 'landlord', 'tenant', 'rent_amount', 'rent_period',
                      'rent_scope', 'currency', 'bond', 'start_date', 'end_date'):
            row = rows['field:' + field]
            self.assertEqual(row['status'], 'passed', field)
            self.assertIn('found', row['detail'].lower())
            self.assertIn('legal', row['detail'].lower())
            self.assertTrue(row['evidence'])
        self.assertEqual(rows['date_order']['status'], 'passed')
        self.assertEqual(rows['bond_reference']['status'], 'passed')
        self.assertNotIn('field:signed_date', rows)
        self.assertEqual(result['analysis']['status'], 'not_run')
        self.assertNotIn('No issues found in completed checks', result['summary'])

    def test_missing_unknown_and_unsupported_fields_never_pass_or_duplicate(self):
        self.upload('Synthetic TEST agreement\nProperty address: unknown\nLandlord: N/A\n'
                    'Tenant: Example Tenant\nRent: USD 500 per quarter\nBond: USD 2000\n')
        result = self.checklist()
        rows = self.rows(result)
        for field in ('address', 'landlord', 'rent_period', 'rent_scope', 'currency', 'start_date', 'end_date'):
            self.assertEqual(rows['field:' + field]['status'], 'needs_confirmation', field)
        self.assertFalse(any(row['id'].startswith('missing_') for row in result['attention']))
        self.assertEqual(rows['bond_reference']['status'], 'needs_confirmation')

    def test_failed_ai_keeps_base_checks_and_cannot_report_all_clear(self):
        self.upload()
        self.provider.mode = 'error'
        self.analyze()
        result = self.checklist()
        self.assertEqual(result['analysis']['status'], 'failed')
        self.assertTrue(result['passed'])
        self.assertIn('analysis', self.rows(result))
        self.assertNotIn('No issues found', result['summary'])
        self.assertNotIn('ai_timeout', str(result))

    def test_grounded_ai_preview_fills_fields_without_saving(self):
        # The labelled extractor misses this line; the model's literal citations recover it.
        text = COMPLETE.replace('Weekly rent: AUD $500 per week whole property',
                                'The rent is AUD 500 per week per person.')
        self.upload(text)
        self.assertIsNone(self.review['fields']['rent_amount']['value'])
        analysis = self.analyze()
        self.assertEqual(analysis['status'], 'success')
        result = self.checklist()
        self.assertEqual(result['analysis'], {'status': 'success', 'analysis_id': analysis['analysis_id']})
        rent = self.rows(result)['field:rent_amount']
        self.assertEqual(rent['status'], 'passed')
        self.assertEqual(rent['value'], 500)
        self.assertEqual(rent['evidence'][0]['quote'], 'The rent is AUD 500 per week per person.')
        self.assertEqual(self.client.get(f'/api/v1/contract-reviews/{self.review_id}').json(), self.review)

    def test_successful_complete_analysis_can_report_no_issues_in_completed_checks(self):
        self.upload()
        self.analyze()
        result = self.checklist()
        self.assertEqual(result['attention'], [])
        self.assertIn('No issues found in completed checks', result['summary'])

    def test_ai_preview_removes_resolved_deterministic_comparison_finding(self):
        self.upload(COMPLETE.replace('Weekly rent: AUD $500 per week whole property',
                                     'The rent is AUD 500 per week per person.'))
        def selected(review):
            review['selection_evidence'] = {'listing_id': 'synthetic',
                'recommendation_run_id': 'synthetic', 'selected_at': '2026-10-31',
                'listing_snapshot': {'address': '42 Example Street, Sydney NSW 2000',
                    'rent_amount': 500, 'rent_period': 'week', 'rent_scope': 'per_person', 'currency': 'AUD'}}
            review['findings'].append({'id': 'F99', 'code': 'rent_not_comparable',
                'severity': 'needs_review', 'title': 'Old comparison',
                'reason': 'The old rent basis was unknown.', 'evidence': []})
        self.update_review(selected)
        self.analyze()
        result = self.checklist()
        self.assertNotIn('finding:rent_not_comparable', self.rows(result))

    def test_unsupported_candidates_and_forged_quotes_never_overlay_fields(self):
        self.upload(COMPLETE.replace('Weekly rent: AUD $500 per week whole property',
                                     'The rent is AUD 500 per week per person.'))
        analysis = self.analyze()
        def forge(record):
            for candidate in record['result']['candidates']:
                if candidate['field'] == 'rent_amount':
                    candidate['value'] = 9000
                    candidate['evidence']['quote'] = 'Invented rent AUD 9000'
        self.update_analysis(analysis, forge)
        result = self.checklist()
        self.assertEqual(self.rows(result)['field:rent_amount']['status'], 'needs_confirmation')

    def test_optional_signing_date_is_checked_when_found(self):
        self.upload(COMPLETE + 'Signing date: 2026-10-31\n')
        self.assertEqual(self.rows(self.checklist())['field:signed_date']['status'], 'passed')

    def test_stale_binding_components_never_overlay_candidates(self):
        self.upload(COMPLETE.replace('Weekly rent: AUD $500 per week whole property',
                                     'The rent is AUD 500 per week per person.'))
        analysis = self.analyze()
        original = copy.deepcopy(analysis)
        for key, value in (('case_id', 'foreign-case'), ('review_id', 'foreign-review'),
                           ('review_version', 999), ('source_digest', 'changed'),
                           ('document_sha256', 'changed'), ('consent_id', 'foreign-consent')):
            with self.subTest(key=key):
                self.update_analysis(analysis, lambda record: record.update(binding={**original['binding'], key: value}))
                result = self.checklist()
                self.assertEqual(result['analysis']['status'], 'stale')
                self.assertEqual(self.rows(result)['field:rent_amount']['status'], 'needs_confirmation')

    def test_revoked_processing_consent_ignores_ai_but_keeps_base_date_error(self):
        self.upload(COMPLETE.replace('2027-11-01', '2026-10-01'))
        self.analyze()
        self.post(f'/cases/{self.case_id}/contract-consents',
            {'confirmed': False, 'consent_id': self.consent_id})
        result = self.checklist()
        self.assertEqual(result['analysis']['status'], 'stale')
        self.assertEqual(self.rows(result)['date_order']['status'], 'issue')

    def test_foreign_review_pointer_and_wrong_kind_are_ignored(self):
        self.upload()
        analysis = self.analyze()
        self.update_analysis(analysis, lambda record: record.update(kind='recommendation'))
        result = self.checklist()
        self.assertEqual(result['analysis']['status'], 'stale')

    def test_changed_source_bytes_cannot_overlay_saved_ai(self):
        self.upload()
        self.analyze()
        with self.repo.transaction() as db:
            saved = self.repo.get(db, 'review', self.review_id)
        (Path(self.tmp.name) / 'uploads' / saved['file_ref']).write_bytes(b'changed source')
        result = self.checklist()
        self.assertEqual(result['analysis']['status'], 'stale')
        self.assertNotIn('No issues found', result['summary'])

    def test_partial_analysis_is_explicit_without_provider_reasons(self):
        self.upload()
        analysis = self.analyze()
        self.update_analysis(analysis, lambda record: record.update(status='partial'))
        result = self.checklist()
        self.assertEqual(result['analysis']['status'], 'partial')
        self.assertEqual(self.rows(result)['analysis']['status'], 'needs_confirmation')
        self.assertNotIn('No issues found', result['summary'])

    def test_special_clauses_are_confirmation_items_with_unchanged_evidence(self):
        quote = 'Special condition: Tenant pays the requested cleaning fee.'
        self.upload(COMPLETE + quote + '\n')
        result = self.checklist()
        clause = self.rows(result)['clause:1']
        self.assertEqual(clause['status'], 'needs_confirmation')
        self.assertEqual(clause['evidence'][0]['quote'], quote)
        self.assertIn('confirm', clause['detail'].lower())

    def test_stale_rule_pack_preserves_date_check_but_never_passes_bond_reference(self):
        self.upload(COMPLETE.replace('2027-11-01', '2026-10-01'))
        self.update_review(lambda review: review['rule_pack'].update(verified_on='2020-01-01'))
        result = self.checklist()
        self.assertEqual(self.rows(result)['date_order']['status'], 'issue')
        self.assertEqual(self.rows(result)['bond_reference']['status'], 'needs_confirmation')

    def test_unavailable_rule_pack_keeps_other_checks_readable(self):
        self.upload()
        self.update_review(lambda review: review.pop('rule_pack'))
        result = self.checklist()
        self.assertEqual(self.rows(result)['bond_reference']['status'], 'needs_confirmation')
        self.assertEqual(self.rows(result)['date_order']['status'], 'passed')

    def test_field_with_no_readable_source_evidence_cannot_pass(self):
        self.upload()
        self.update_review(lambda review: review['fields']['address'].update(evidence=None))
        self.assertEqual(self.rows(self.checklist())['field:address']['status'], 'needs_confirmation')

    def test_failed_sidecar_with_valid_candidates_cannot_fill_missing_fields(self):
        self.upload(COMPLETE.replace('Weekly rent: AUD $500 per week whole property',
                                     'The rent is AUD 500 per week per person.'))
        analysis = self.analyze()
        self.update_analysis(analysis, lambda record: record.update(status='failed'))
        result = self.checklist()
        self.assertEqual(result['analysis']['status'], 'failed')
        self.assertEqual(self.rows(result)['field:rent_amount']['status'], 'needs_confirmation')

    def test_foreign_or_missing_bond_currency_cannot_be_compared_to_aud_rent(self):
        for bond in ('USD $9000', '9000'):
            with self.subTest(bond=bond):
                self.upload(COMPLETE.replace('AUD $2000', bond), request=bond.replace(' ', '-').replace('$', ''))
                result = self.checklist()
                self.assertEqual(self.rows(result)['bond_reference']['status'], 'needs_confirmation')
                self.assertNotIn('bond_over_four_weeks', self.rows(result))

    def test_aud_excess_bond_has_real_issue_and_no_duplicate(self):
        self.upload(COMPLETE.replace('AUD $2000', 'AUD $3000'))
        result = self.checklist()
        row = self.rows(result)['bond_reference']
        self.assertEqual(row['status'], 'issue')
        self.assertEqual(len(row['evidence']), 2)
        self.assertNotIn('bond_over_four_weeks', self.rows(result))

    def test_other_existing_findings_survive_with_their_source_quotes(self):
        self.upload()
        finding = {'id': 'F99', 'code': 'other_observed_issue', 'severity': 'high',
                   'title': 'Observed discrepancy', 'reason': 'The uploaded details differ.',
                   'evidence': [{'quote': 'Original source 原文', 'page': 1}], 'rule_version': None}
        self.update_review(lambda review: review['findings'].append(finding))
        row = self.rows(self.checklist())['finding:other_observed_issue']
        self.assertEqual(row['status'], 'issue')
        self.assertEqual(row['evidence'], finding['evidence'])


if __name__ == '__main__':
    unittest.main()
