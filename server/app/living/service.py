"""Versioned local records and confirmation proposals. No delivery or booking side effects."""
from copy import deepcopy
from ..common import now, uid, shape, integer, request_id, opaque_ref, require
from .catalog import ProviderCatalog
from .repairs import add_repair, update_repair, STATUS_LABELS, TONE_LABELS
from .fields import (blank_profile, profile_values, merge_profile, repair_values,
                     status_values, booking_values, text, profile_summary)


class LivingService:
    def __init__(self, ctx, providers=None):
        self.ctx = ctx
        self.catalog = ProviderCatalog(providers)
        self.enrich_plans = providers is None

    def directory(self):
        directory = self.catalog.directory()
        if self.enrich_plans:
            directory['plan_catalog'] = self.ctx.utility_plans.summary()
            from .utility_catalog import public_plan
            plans = [public_plan(p) for p in self.ctx.utility_plans.search(include_unavailable=True)]
            for provider in directory['providers']:
                provider['plans'] = [p for p in plans if p['provider_id'] == provider['id']]
                if provider['plans']:
                    provider['notes'] = 'Official plans and pricing references are included. Check availability, promotional eligibility and final costs for your address and the terms.'
        return directory

    def _record(self, db, case_id):
        self.ctx.get(db, 'case', case_id)
        record = self.ctx.repo.get(db, 'living_services', case_id) or {
            'case_id': case_id, 'version': 0, 'profile': blank_profile(),
            'repairs': [], 'bookings': [], 'updated_at': None}
        record['profile'] = merge_profile(blank_profile(), record['profile'])
        return record

    def read(self, case_id: str):
        with self.ctx.repo.transaction() as db:
            return self._record(db, case_id)

    def _envelope(self, body, values=True):
        shape(body, ('request_id', 'expected_version', 'confirmed', *(['values'] if values else [])))
        request_id(body['request_id'])
        require(integer(body['expected_version']), 422, 'invalid_input', 'Provide a valid record version.')
        require(body['confirmed'] is True, 422, 'confirmation_required', 'Explicitly confirm this save.')

    def _version(self, record, version):
        require(record['version'] == version, 409, 'version_conflict', 'The details changed. Reload and confirm again.')

    def _finish(self, db, record, key, identity):
        record['version'] += 1
        record['updated_at'] = now()
        self.ctx.repo.put(db, 'living_services', record['case_id'], record)
        self.ctx.save_receipt(db, 'living_receipt', key, identity, record)
        return record

    def _mutate(self, case_id, body, operation, action):
        self._envelope(body)
        key = case_id + ':' + body['request_id']
        identity = {'operation': operation, 'body': body}
        with self.ctx.repo.transaction() as db:
            record = self._record(db, case_id)
            old = self.ctx.receipt(db, 'living_receipt', key, identity)
            if old:
                return old['result']
            self._version(record, body['expected_version'])
            action(record, body['values'])
            return self._finish(db, record, key, identity)

    def profile(self, case_id: str, body: dict):
        def save(record, values):
            validated = profile_values(values, self.catalog)
            for key in ('lease_start_date', 'lease_end_date'):
                if key not in values:
                    validated[key] = record['profile'].get(key)
            record['profile'] = profile_values(validated, self.catalog)
        return self._mutate(case_id, body, 'profile', save)

    def _add_repair(self, record, values):
        return add_repair(record, values)

    def repair(self, case_id: str, body: dict):
        return self._mutate(case_id, body, 'repair', self._add_repair)

    def update_repair(self, case_id: str, repair_id: str, body: dict):
        opaque_ref(repair_id)
        return self._mutate(case_id, body, 'repair:' + repair_id,
                            lambda record, values: update_repair(record, repair_id, values))

    def booking(self, case_id: str, body: dict):
        def save(record, values):
            values = booking_values(values, self.catalog)
            booking_id = values.get('booking_id')
            if booking_id is not None:
                opaque_ref(booking_id)
                entry = next((b for b in record['bookings'] if b['booking_id'] == booking_id), None)
                require(entry is not None, 404, 'not_found', 'Service record not found for this case.')
                entry.update(values, updated_at=now())
            else:
                record['bookings'].append({**values, 'booking_id': uid('booking'), 'created_at': now()})
        return self._mutate(case_id, body, 'booking', save)

    def prepare_proposal(self, case_id, kind, values, source_message):
        require(kind in ('profile', 'repair', 'repair_update'), 422, 'invalid_input', 'This proposal type is unsupported.')
        text(source_message, 12000)
        with self.ctx.repo.transaction() as db:
            record = self._record(db, case_id)
            if kind == 'profile':
                values = profile_values(values, self.catalog, partial=True)
                require(bool(values), 422, 'invalid_input', 'The proposed details cannot be empty.')
                summary = [*profile_summary(values, self.catalog), 'Saved only after confirmation; unspecified fields retain their previous values.']
            elif kind == 'repair_update':
                shape(values, ('repair_id',), ('status', 'note', 'email_tone', 'email_language', 'email_draft'))
                opaque_ref(values['repair_id'])
                entry = next((r for r in record['repairs'] if r['repair_id'] == values['repair_id']), None)
                require(entry is not None, 404, 'not_found', 'Repair record not found for this case.')
                patch = status_values({k:v for k,v in values.items() if k != 'repair_id'})
                summary = ['Update repair: ' + entry['title']]
                if 'status' in patch: summary.append('Status: ' + STATUS_LABELS[patch['status']])
                if 'note' in patch: summary.append('User note: ' + patch['note'])
                if 'email_tone' in patch: summary.append('Email tone: ' + TONE_LABELS[patch['email_tone']] + '; the original facts and recipient are retained.')
                summary.append('Confirm to update the same repair record. The email will not be sent.')
            else:
                values = repair_values(values)
                summary = ['Prepare repair email: ' + values['title'], 'Location: ' + (values['location'] or 'Not supplied'),
                           'Description: ' + values['description'],
                           'Priority: ' + ('Urgent' if values['priority'] == 'urgent' else 'Normal'),
                           'Recipient: ' + (record['profile']['agent_email'] or 'Not supplied'),
                           'Email tone: ' + TONE_LABELS[values.get('email_tone','standard')],
                           'Only a local draft is prepared. The email will not be sent.']
            proposal = {'proposal_id': uid('living-proposal'), 'case_id': case_id, 'kind': kind,
                        'values': values, 'summary': summary, 'expected_version': record['version'],
                        'source_message': source_message, 'status': 'pending', 'created_at': now()}
            self.ctx.repo.put(db, 'living_proposal', proposal['proposal_id'], proposal)
            return {k: deepcopy(proposal[k]) for k in ('proposal_id', 'kind', 'summary', 'expected_version', 'status')}

    def apply(self, case_id: str, proposal_id: str, body: dict):
        self._envelope(body, values=False)
        opaque_ref(proposal_id)
        key = case_id + ':' + body['request_id']
        identity = {'operation': 'apply:' + proposal_id, 'body': body}
        with self.ctx.repo.transaction() as db:
            record = self._record(db, case_id)
            proposal = self.ctx.get(db, 'living_proposal', proposal_id)
            require(proposal['case_id'] == case_id, 404, 'not_found', 'Proposal not found for this case.')
            old = self.ctx.receipt(db, 'living_receipt', key, identity)
            if old:
                return old['result']
            require(proposal['status'] == 'pending', 409, 'proposal_applied', 'This proposal has already been confirmed and saved.')
            self._version(record, body['expected_version'])
            require(proposal['expected_version'] == body['expected_version'], 409, 'version_conflict', 'This proposal uses outdated details. Generate and confirm it again.')
            if proposal['kind'] == 'profile':
                record['profile'] = profile_values(merge_profile(record['profile'], proposal['values']), self.catalog)
            elif proposal['kind'] == 'repair_update':
                values = proposal['values']
                update_repair(record, values['repair_id'], {k:v for k,v in values.items() if k != 'repair_id'})
                proposal['result_repair_id'] = values['repair_id']
            else:
                proposal['result_repair_id'] = self._add_repair(record, proposal['values'])
            proposal.update(status='applied', applied_at=now())
            self.ctx.repo.put(db, 'living_proposal', proposal_id, proposal)
            return self._finish(db, record, key, identity)
