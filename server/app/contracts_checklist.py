"""Read-only, evidence-backed checklist projection of a saved contract review.

The original review lifecycle remains untouched. AI suggestions are usable only
in a disposable projection with the exact current consent and source binding.
"""
from copy import deepcopy
from datetime import date
from hashlib import sha256
import math
import re

from contract_agent.extract import FIELDS
from contract_agent.rules import evaluate_findings, rule_pack_current
from .ai.service import digest


LABELS = {
    'address': 'Property address', 'landlord': 'Landlord', 'tenant': 'Tenant',
    'rent_amount': 'Rent amount', 'rent_period': 'Rent period',
    'rent_scope': 'Rent charging scope', 'currency': 'Rent currency',
    'bond': 'Bond amount', 'start_date': 'Start date', 'end_date': 'End date',
    'signed_date': 'Signing date',
}
UNKNOWN = {'unknown', 'n/a', 'na', 'none', 'null', 'not provided', 'not specified',
           'not available', 'unreadable', 'tbc', 'tbd', 'pending', '-', '—'}
FOREIGN = re.compile(r'\b(?:USD|NZD|CAD|HKD|SGD|EUR|GBP)\b|(?:US|NZ|CA|HK|SG)\$|[€£]', re.I)
COVERED = {'date_order', 'bond_over_four_weeks', 'bond_basis_unknown'}
RECOMPUTED = COVERED | {'address_difference', 'rent_difference', 'rent_not_comparable'}
ANALYSIS_DETAILS = {
    'failed': 'AI analysis did not complete. The available document checks are shown; review the original agreement and try analysis again.',
    'partial': 'AI analysis completed only partly. Grounded details are shown, but some analysis could not be completed.',
    'stale': 'The saved AI analysis no longer matches this document, review or processing consent. Only the available original document checks are shown.',
    'unavailable': 'The saved AI analysis or its source could not be verified. Only the available original document checks are shown.',
}


def evidence_list(value):
    """Preserve original source quotes and evidence objects without rewriting them."""
    if isinstance(value, dict):
        return [deepcopy(value)]
    if isinstance(value, list):
        return [deepcopy(item) for item in value if isinstance(item, dict)]
    return []


def currency_of(entry):
    quotes = [e.get('quote', '') for e in evidence_list(entry.get('evidence'))]
    quote = ' '.join(q for q in quotes if isinstance(q, str))
    if FOREIGN.search(quote):
        return None
    return 'AUD' if '$' in quote or re.search(r'\bAUD\b', quote, re.I) else None


def field_found(key, entry):
    """Presence requires a supported, readable value with source evidence."""
    value = entry.get('value')
    evidence = evidence_list(entry.get('evidence'))
    if not any(isinstance(e.get('quote'), str) and e['quote'].strip() for e in evidence):
        return False
    if key in {'rent_amount', 'bond'}:
        return type(value) in (int, float) and math.isfinite(value) and 0 < value < 1_000_000
    if not isinstance(value, str) or not value.strip() or value.strip().casefold() in UNKNOWN:
        return False
    if key.endswith('_date'):
        try:
            return bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) and date.fromisoformat(value))
        except ValueError:
            return False
    if key == 'rent_period':
        return value in {'week', 'fortnight', 'month'}
    if key == 'rent_scope':
        return value in {'per_person', 'per_room', 'whole_property'}
    if key == 'currency':
        return value == 'AUD' and currency_of(entry) == 'AUD'
    return True


def check(identifier, label, status, detail, evidence=None, **extra):
    return {'id': identifier, 'label': label, 'status': status, 'detail': detail,
            'evidence': evidence_list(evidence), **extra}


class ContractChecklist:
    def __init__(self, ctx, contracts):
        self.ctx, self.contracts = ctx, contracts

    def analysis_preview(self, db, saved, review_id):
        """Read sidecar state and re-ground candidates; never call a provider or save."""
        repo = self.ctx.repo
        preview = deepcopy(saved['review'])
        pointer = repo.get(db, 'ai_latest', 'contract:' + review_id)
        if pointer is None:
            return preview, {'status': 'not_run'}
        analysis_id = pointer.get('analysis_id')
        state = {'status': 'unavailable'}
        if isinstance(analysis_id, str):
            state['analysis_id'] = analysis_id
        record = repo.get(db, 'ai_analysis', analysis_id) if isinstance(analysis_id, str) else None
        if not isinstance(record, dict):
            return preview, state
        consent = repo.get(db, 'consent', saved.get('consent_id', ''))
        case = self.ctx.get(db, 'case', saved['case_id'])
        binding = {'case_id': saved['case_id'], 'review_id': review_id,
                   'review_version': preview['version'], 'source_digest': digest(preview),
                   'document_sha256': preview['document']['sha256'],
                   'consent_id': saved.get('consent_id')}
        if (record.get('kind') != 'contract' or record.get('analysis_id') != analysis_id
                or record.get('binding') != binding or not consent or not consent.get('active')
                or not self.contracts.selection_is_current(case, consent)):
            state['status'] = 'stale'
            return preview, state
        status = record.get('status')
        if status not in {'success', 'partial'}:
            state['status'] = status if status in {'failed', 'stale'} else 'unavailable'
            return preview, state
        # Compare actual bytes as well as the saved metadata before trusting citations.
        directory = (repo.directory / 'uploads').resolve()
        path = (directory / saved.get('file_ref', '')).resolve()
        try:
            if path.parent != directory or not path.is_file():
                return preview, state
            if sha256(path.read_bytes()).hexdigest() != binding['document_sha256']:
                state['status'] = 'stale'
                return preview, state
            from contract_agent.document import load_document
            from contract_agent.ai_analysis import _candidate, _lines, CANDIDATE_FIELDS
            document = load_document(path, consent=True, max_pdf_pages=30 if saved.get('real_context') else 10)
            document['source_name'] = preview['document']['source_name']
            candidates = (record.get('result') or {}).get('candidates', [])
            if not isinstance(candidates, list):
                return preview, state
            lines = _lines(document)
            names = [item.get('field') for item in candidates if isinstance(item, dict)]
            duplicates = {key for key in CANDIDATE_FIELDS if names.count(key) > 1}
            accepted = []
            for item in candidates:
                if not isinstance(item, dict) or item.get('valid') is not True:
                    continue
                evidence = item.get('evidence')
                if not isinstance(evidence, dict):
                    continue
                validated = _candidate({'field': item.get('field'), 'value': item.get('value'),
                    'line': evidence.get('line'), 'quote': evidence.get('quote')}, document, lines, duplicates)
                if validated['valid'] and validated['evidence'] == evidence:
                    accepted.append(validated)
            if not accepted:
                return preview, state
            for item in accepted:
                preview['fields'][item['field']] = {'value': item['value'], 'confidence': 1.0,
                                                    'evidence': deepcopy(item['evidence'])}
            state['status'] = status
            return preview, state
        except Exception:
            # Source/parser/schema failures are public outcomes, never internal diagnostics.
            return deepcopy(saved['review']), state

    def read(self, review_id: str):
        with self.ctx.repo.transaction() as db:
            saved = self.ctx.get(db, 'review', review_id)
            review, analysis = self.analysis_preview(db, saved, review_id)
        fields = {key: deepcopy(review.get('fields', {}).get(key) or
                  {'value': None, 'confidence': 0, 'evidence': None}) for key in FIELDS}
        found = {key: field_found(key, entry) for key, entry in fields.items()}
        rows = []
        for key in FIELDS:
            entry = fields[key]
            if key == 'signed_date' and entry.get('value') is None and not entry.get('evidence'):
                continue
            present = found[key]
            rows.append(check('field:' + key, LABELS[key], 'passed' if present else 'needs_confirmation',
                'This detail was found in the agreement. This is a presence check, not a finding of legal validity.'
                if present else 'A supported, readable value was not found for this detail. Confirm it against the original agreement.',
                entry.get('evidence'), value=entry.get('value'),
                **({} if present else {'question': 'Could you confirm the ' + LABELS[key].lower() + ' in the agreement?'})))

        dates = [fields[key].get('evidence') for key in ('start_date', 'end_date')]
        date_evidence = [ev for value in dates for ev in evidence_list(value)]
        valid_dates = found['start_date'] and found['end_date']
        date_issue = valid_dates and date.fromisoformat(fields['end_date']['value']) <= date.fromisoformat(fields['start_date']['value'])
        rows.append(check('date_order', 'Agreement date order',
            'issue' if date_issue else 'passed' if valid_dates else 'needs_confirmation',
            'The end date is not after the start date. Check the agreement dates.' if date_issue else
            'The end date is after the start date.' if valid_dates else
            'The start and end dates could not both be checked. Confirm the agreement term.', date_evidence))

        pack = review.get('rule_pack') or {}
        try:
            current_pack = rule_pack_current(review['as_of'], pack)
        except (KeyError, TypeError, ValueError):
            current_pack = False
        comparable = (all(found[key] for key in ('rent_amount', 'rent_period', 'currency', 'bond'))
                      and fields['rent_period']['value'] == 'week'
                      and currency_of(fields['bond']) == 'AUD'
                      and currency_of(fields['rent_amount']) == 'AUD')
        bond_evidence = [ev for key in ('bond', 'rent_amount') for ev in evidence_list(fields[key].get('evidence'))]
        over = comparable and fields['bond']['value'] > 4 * fields['rent_amount']['value']
        rows.append(check('bond_reference', 'Bond and weekly rent reference',
            'needs_confirmation' if not current_pack or not comparable else 'issue' if over else 'passed',
            'The NSW reference information is out of date or unavailable. The bond reference check was not completed.' if not current_pack else
            'The bond reference check needs verified AUD bond and AUD weekly rent amounts. Confirm the currency, amounts and rent period.' if not comparable else
            'The extracted AUD bond exceeds four weeks of the extracted AUD weekly rent. Confirm both amounts against the agreement.' if over else
            'The extracted AUD bond does not exceed four weeks of the extracted AUD weekly rent under the saved NSW reference. This limited check does not establish legal validity.',
            bond_evidence))

        # Re-evaluate deterministic findings from the disposable fields even when the
        # lifecycle would withhold results pending human review or resubmission.
        safe_fields = deepcopy(fields)
        for key in FIELDS:
            if not found[key]:
                safe_fields[key]['value'] = None
        if not comparable or not current_pack:
            safe_fields['bond']['value'] = None
        generated = evaluate_findings(safe_fields, review.get('selection_evidence'), pack)
        observed = {f.get('code', f.get('id')): f for f in review.get('findings', [])
                    if f.get('code') not in RECOMPUTED}
        observed.update({f.get('code', f.get('id')): f for f in generated})
        for code, finding in observed.items():
            if code in COVERED or (isinstance(code, str) and code.startswith('missing_') and code[8:] in LABELS):
                continue
            rows.append(check('finding:' + str(code), finding.get('title', 'Agreement detail needs confirmation'),
                'issue' if finding.get('severity') == 'high' else 'needs_confirmation',
                finding.get('reason', 'Confirm this detail against the original agreement.'), finding.get('evidence')))
        for index, clause in enumerate(review.get('additional_clauses', []), 1):
            rows.append(check('clause:' + str(index), 'Additional or special clause', 'needs_confirmation',
                'Confirm the meaning and effect of this additional or special clause. Its legal validity has not been established by these checks.',
                clause.get('evidence'), question='Could you clarify this additional or special clause?'))
        if analysis['status'] in ANALYSIS_DETAILS:
            rows.append(check('analysis', 'AI analysis completion', 'needs_confirmation', ANALYSIS_DETAILS[analysis['status']]))
        if review.get('status') in {'Awaiting Resubmission', 'Degraded Summary Only'} or review.get('extraction_confidence', 0) < 0.5:
            rows.append(check('document_quality', 'Document analysis coverage', 'needs_confirmation',
                'Some document checks could not be completed reliably. Confirm the original agreement or upload a clearer copy.'))
        passed = [row for row in rows if row['status'] == 'passed']
        attention = [row for row in rows if row['status'] != 'passed']
        counts = (f"{len(attention)} {'check needs' if len(attention) == 1 else 'checks need'} attention; "
                  f"{len(passed)} {'check' if len(passed) == 1 else 'checks'} passed.")
        if not attention and analysis['status'] == 'success':
            summary = 'No issues found in completed checks.'
        elif analysis['status'] in ANALYSIS_DETAILS:
            summary = counts + ' ' + ANALYSIS_DETAILS[analysis['status']]
        else:
            summary = counts
            if analysis['status'] == 'not_run':
                summary += ' AI analysis has not run.'
        return {'review_id': review_id, 'review_version': review['version'],
                'document_name': review['document'].get('source_name') or 'Uploaded agreement',
                'total': len(rows), 'passed': passed, 'attention': attention,
                'analysis': analysis, 'summary': summary}
