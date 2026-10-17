"""M3 -> M4 local handoff. The coordinator supplies trusted ownership/current review.

This module consumes persisted confirmations; it never manufactures user consent.
"""
from copy import deepcopy
from hashlib import sha256
import json
import re
from uuid import uuid4

from .contracts import canonical, day, instant, validate
from .errors import AftercareError, require
from .planner import SYDNEY

FIELDS = ('address', 'landlord', 'tenant', 'rent_amount', 'rent_period', 'rent_scope',
          'currency', 'bond', 'start_date', 'end_date', 'signed_date')
PROPERTY = {'rooms': None, 'carpeted': None, 'outdoor': None, 'furnished': None,
            'inventory': None, 'inventory_confirmed': False, 'baseline_evidence_refs': []}


def fingerprint(value):
    """SHA-256 of UTF-8, sorted compact JSON, ensure_ascii=False, no NaN."""
    return sha256(canonical(value).encode('utf-8')).hexdigest()


def validate_review(review):
    # Reuse M3's semantic validation when the full repository is installed.
    # Import via package path, without changing sys.path or creating a second schema.
    try:
        from agent3.contract_agent.contracts import validate_review as m3_validate
        from agent3.contract_agent.errors import ContractError
    except ImportError as exc:
        raise AftercareError('missing_dependency', 'M3 validation is required: run from repository root with PYTHONPATH=agent4') from exc
    else:
        try:
            m3_validate(review)
        except (ContractError, KeyError, TypeError, ValueError) as exc:
            raise AftercareError('invalid_review', str(exc)) from exc
    require(isinstance(review.get('document', {}).get('sha256'), str) and
            re.fullmatch('[0-9a-f]{64}', review['document']['sha256']),
            'invalid_review', 'A SHA-256 contract fingerprint is required')


def confirmation_gate(packet, as_of):
    """Return an actionable pause reason; malformed records raise input errors."""
    r, c, context = packet['review'], packet['confirmation'], packet['context']
    if r['status'] != 'Reviewed':
        return 'review_blocked', r['status_reason'] or r['status']
    human = r['human_review']
    high = {f['id'] for f in r['findings'] if f['severity'] == 'high'}
    finding_ids = human.get('finding_ids') if human else []
    if not isinstance(finding_ids, list) or any(not isinstance(item, str) for item in finding_ids):
        return 'review_blocked', 'Human review finding references are malformed'
    if (human is not None and (human.get('status') != 'approved' or human.get('review_version') != r['version'])) or (
            high and (not human or not high <= set(finding_ids))):
        return 'review_blocked', 'Unresolved human review for the current contract version'
    if c is None:
        return 'confirmation_required', 'M3 must persist an explicit actual-tenancy confirmation first'
    validate('tenancy-confirmation', c)
    if c['actual_tenancy_confirmed'] is not True:
        return 'confirmation_required', 'Actual tenancy has not been explicitly confirmed'
    if (c['tenant_id'], c['case_id'], c['confirmed_by']) != (context['tenant_id'], context['case_id'], context['tenant_id']):
        return 'confirmation_ownership_mismatch', 'Confirmation tenant, case and confirmer must match trusted context'
    if c['review_id'] != r['review_id'] or c['review_version'] != r['version']:
        return 'review_version_mismatch', 'Reconfirm the current review version'
    if c['document_sha256'] != r['document']['sha256'] or c['review_sha256'] != fingerprint(r):
        return 'review_fingerprint_mismatch', 'Confirmation does not bind this exact review/document snapshot'
    if not instant(r['updated_at']) <= instant(c['confirmed_at']) <= instant(as_of):
        return 'confirmation_time_invalid', 'Confirmation must follow review and must not be in the future'
    values = {k: r['fields'][k]['value'] for k in FIELDS}
    if any(c['confirmed_fields'][k] != values[k] for k in FIELDS):
        return 'confirmed_fields_mismatch', 'Correct M3 fields and reconfirm instead of changing the confirmation snapshot'
    required = set(FIELDS) - {'end_date', 'bond'}
    if any(values[k] is None or isinstance(values[k], str) and not values[k].strip() for k in required):
        return 'tenancy_fields_missing', 'Required actual lease facts are unknown; correct and reconfirm in M3'
    if c['confirmed_fields']['jurisdiction'] != 'NSW' or c['confirmed_fields']['tenancy_type'] != 'standard_residential':
        return 'unsupported_tenancy', 'M4 currently supports explicitly confirmed NSW standard_residential only'
    for k in ('address', 'landlord', 'tenant'):
        require(isinstance(values[k], str), 'invalid_review', k + ' must be text')
    require(type(values['rent_amount']) in (int, float) and values['rent_amount'] > 0,
            'invalid_review', 'Positive rent is required')
    require(values['currency'] == 'AUD' and values['rent_period'] in {'week', 'fortnight', 'month'} and
            values['rent_scope'] in {'per_person', 'per_room', 'whole_property'}, 'invalid_review', 'Unsupported rent basis')
    start, signed = day(values['start_date']), day(values['signed_date'])
    require(signed <= instant(c['confirmed_at']).astimezone(SYDNEY).date(), 'invalid_review', 'Signing declaration cannot refer to a future date')
    if values['end_date'] is not None:
        require(day(values['end_date']) >= start, 'invalid_review', 'Lease end precedes start')
    if values['bond'] is not None:
        require(type(values['bond']) in (int, float) and values['bond'] >= 0, 'invalid_review', 'Invalid bond amount')
    return None


def receive(agent, packet, *, actor_id, as_of):
    validate('m3-handoff', packet)
    canonical(packet)
    instant(as_of)
    context, review = packet['context'], packet['review']
    require(actor_id == context['tenant_id'], 'access_denied', 'Trusted tenant does not own this handoff')
    validate_review(review)
    require(instant(review['updated_at']) <= instant(as_of), 'invalid_review', 'Review is dated in the future')
    digest, review_digest = fingerprint(packet), fingerprint(review)
    with agent.transaction() as conn:
        old = conn.execute('SELECT fingerprint,response FROM m3_receipts WHERE actor_id=? AND request_id=?',
                           (actor_id, packet['request_id'])).fetchone()
        require(not old or old[0] == digest, 'request_conflict', 'Handoff request ID was reused with different input')
        latest = conn.execute('SELECT tenant_id,upstream_case_id,version,fingerprint,updated_at FROM m3_reviews WHERE review_id=?',
                              (review['review_id'],)).fetchone()
        require(not latest or latest[:2] == (actor_id, context['case_id']),
                'context_conflict', 'This review is already bound to another tenant/case')
        pause = None
        if latest and review['version'] < latest[2]:
            pause = ('stale_review', 'A newer review is known; old confirmations cannot create or update a tenancy')
        elif latest and review['version'] == latest[2] and review_digest != latest[3] and instant(review['updated_at']) <= instant(latest[4]):
            pause = ('review_snapshot_conflict', 'Same-version snapshots require a later updated_at; reload M3 current state')
        else:
            conn.execute('INSERT INTO m3_reviews VALUES(?,?,?,?,?,?) ON CONFLICT(review_id) DO UPDATE SET '
                         'version=excluded.version,fingerprint=excluded.fingerprint,updated_at=excluded.updated_at',
                         (review['review_id'], actor_id, context['case_id'], review['version'], review_digest, review['updated_at']))
        if pause is None:
            pause = confirmation_gate(packet, as_of)
        if pause is None:
            c = packet['confirmation']
            known = conn.execute('SELECT version,fingerprint,tenant_id,upstream_case_id FROM m3_confirmations '
                                 'WHERE confirmation_id=? ORDER BY version DESC', (c['confirmation_id'],)).fetchall()
            require(not known or all(row[2:] == (actor_id, context['case_id']) for row in known),
                    'confirmation_conflict', 'Confirmation source is bound to another tenant/case')
            same = next((row for row in known if row[0] == c['confirmation_version']), None)
            require(not same or same[1] == fingerprint(c), 'confirmation_conflict',
                    'Confirmation ID/version is immutable; persist changed declarations as a new version or ID')
            if known and known[0][0] > c['confirmation_version']:
                pause = ('stale_confirmation', 'A newer confirmation version is already known')
            elif not same:
                conn.execute('INSERT INTO m3_confirmations VALUES(?,?,?,?,?)',
                             (c['confirmation_id'], c['confirmation_version'], fingerprint(c), actor_id, context['case_id']))
        # Check current gates before replaying an old successful receipt.
        if pause:
            response = {'schema_version': '1.0', 'status': 'paused', 'code': pause[0], 'message': pause[1],
                        'upstream_case_id': context['case_id'], 'review_id': review['review_id'],
                        'review_version': review['version'], 'newly_created': False}
            if not old:
                conn.execute('INSERT INTO m3_receipts VALUES(?,?,?,?)', (actor_id, packet['request_id'], digest, canonical(response)))
            return response
        if old:
            saved = json.loads(old[1])
            return {**saved, 'status': 'duplicate', 'newly_created': False} if saved['status'] == 'created' else saved
        existing = conn.execute('SELECT tenant_id,packet,response FROM m3_handoffs WHERE upstream_case_id=?',
                                (context['case_id'],)).fetchone()
        if existing:
            require(existing[0] == actor_id, 'access_denied', 'Case belongs to another tenant')
            original = json.loads(existing[1])
            if all(packet[k] == original[k] for k in ('context', 'review', 'confirmation', 'property_details', 'evidence')):
                response = {**json.loads(existing[2]), 'newly_created': False, 'status': 'duplicate'}
            else:
                response = {'schema_version': '1.0', 'status': 'paused', 'code': 'existing_tenancy_requires_reconciliation',
                            'message': 'Keep the existing tenancy/case; reconcile changed lease facts explicitly', 'newly_created': False,
                            'case_id': json.loads(existing[2])['case_id'], 'upstream_case_id': context['case_id']}
        else:
            confirmation = packet['confirmation']
            tenancy_id = confirmation['tenancy_id'] or 'tenancy-' + uuid4().hex
            conflict = conn.execute('SELECT case_id FROM cases WHERE json_extract(document,\'$.tenancy.tenancy_id\')=?',
                                    (tenancy_id,)).fetchone()
            require(not conflict, 'tenancy_conflict', 'Tenancy already exists; use the original mapping instead of creating another case')
            require(not conn.execute('SELECT 1 FROM m3_handoffs WHERE review_id=?', (review['review_id'],)).fetchone(),
                    'context_conflict', 'Review already consumed by another case')
            case_id = 'aftercare-' + uuid4().hex
            tenancy = {'tenancy_id': tenancy_id, 'tenant_id': actor_id,
                       'address': confirmation['confirmed_fields']['address'], 'jurisdiction': 'NSW',
                       'tenancy_type': 'standard_residential', 'confirmed': True,
                       'source_ref': confirmation['confirmation_id'], 'source_version': confirmation['confirmation_version'],
                       **deepcopy(packet['property_details'])}
            evidence = deepcopy(packet['evidence'])
            for kind, ref, version, stamp, summary in (
                    ('review', review['review_id'], review['version'], review['updated_at'],
                     'M3 ContractReview; document_sha256=' + review['document']['sha256'] + '; review_sha256=' + review_digest),
                    ('confirmation', confirmation['confirmation_id'], confirmation['confirmation_version'], confirmation['confirmed_at'],
                     'M3 actual tenancy declaration; upstream_case_id=' + context['case_id'] + '; not payment or move-out confirmation')):
                evidence.append({'evidence_id': 'm3-' + kind + '-' + fingerprint([ref, version])[:32], 'kind': 'other',
                                 'source_ref': ref, 'source_version': version, 'recorded_at': stamp, 'summary': summary})
            require(len({e['evidence_id'] for e in evidence}) == len(evidence), 'evidence_conflict', 'Duplicate/reserved evidence ID')
            command = {'schema_version': '1.0', 'request_id': 'm3-' + fingerprint([actor_id, packet['request_id']]),
                       'case_id': case_id, 'actor_id': actor_id, 'actor_role': 'tenant', 'expected_version': 0,
                       'as_of': as_of, 'operation': 'create', 'payload': {'tenancy': tenancy, 'evidence': evidence}}
            validate('command', command)
            receipt = agent._submit(conn, command)
            response = {'schema_version': '1.0', 'status': 'created', 'newly_created': True,
                        'upstream_case_id': context['case_id'], 'case_id': case_id, 'tenancy_id': tenancy_id,
                        'review_id': review['review_id'], 'review_version': review['version'],
                        'confirmation_id': confirmation['confirmation_id'], 'confirmation_version': confirmation['confirmation_version'],
                        'next_action': 'confirm_property_details_and_move_out_date', 'receipt': receipt}
            conn.execute('INSERT INTO m3_handoffs VALUES(?,?,?,?,?,?,?)',
                         (context['case_id'], actor_id, tenancy_id, case_id, review['review_id'], canonical(packet), canonical(response)))
        conn.execute('INSERT INTO m3_receipts VALUES(?,?,?,?)', (actor_id, packet['request_id'], digest, canonical(response)))
        return response
