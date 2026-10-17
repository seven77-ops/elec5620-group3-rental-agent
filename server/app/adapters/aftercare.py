"""Aftercare orchestration for the local synthetic API."""
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256

from fastapi import Request
from ..common import require, uid, shape, integer, request_id
from ..settings import TENANT, OPERATOR, AFTERCARE_CLOCK
from .business import validate_aftercare, AftercareError


class AftercareAdapter:
    """Aftercare orchestration around saved state and original member functions."""
    def __init__(self, ctx):
        self.ctx = ctx

    def command_templates(self):
        templates = self.ctx.settings.templates
        return templates

    def aftercare_command(self, body: dict, request: Request):
        aftercare = self.ctx.aftercare
        fixture_clocks = self.ctx.settings.fixture_clocks
        get = self.ctx.get
        operator = self.ctx.operator
        receipt = self.ctx.receipt
        repo = self.ctx.repo
        shape(body, ('case_id', 'request_id', 'expected_version', 'operation', 'payload'))
        logical_id = request_id(body['request_id'])
        require(integer(body['expected_version']), 422, 'invalid_input', 'Expected version must be a nonnegative integer')
        require(isinstance(body['operation'], str) and isinstance(body['payload'], dict), 422, 'invalid_input', 'Operation and payload must be valid')
        role = 'operator' if body['operation'] == 'operator_decision' else 'tenant'
        if role == 'operator':
            operator(request)
        key = str(body['case_id']) + ':' + logical_id
        with repo.transaction() as db:
            case = get(db, 'case', body['case_id'])
            old = receipt(db, 'aftercare_receipt', key, body)
            if old and 'result' in old:
                return old['result']
            binding = old.get('command') if old else None
            pending = case.get('aftercare_pending')
            require(pending is None or pending['request_key'] == key, 409, 'creation_in_progress',
                    'Another tenancy creation is in progress; retry its original request')
            if binding:
                require(case['aftercare_case_id'] in (None, binding['case_id']), 409, 'mapping_conflict',
                        'This request belongs to another saved tenancy creation')
            if binding is None:
                m4_id = case['aftercare_case_id']
                payload = deepcopy(body['payload'])
                if body['operation'] == 'create':
                    require(m4_id is None, 409, 'already_exists', 'An aftercare case is already linked')
                    require(isinstance(payload.get('tenancy'), dict) and payload['tenancy'].get('confirmed') is True,
                            422, 'tenancy_confirmation_required', 'Explicitly confirm tenancy details first')
                    m4_id = uid('aftercare')
                    payload['tenancy'].update(tenant_id=TENANT, tenancy_id=uid('tenancy'))
                else:
                    require(m4_id is not None, 409, 'aftercare_required', 'Create the confirmed tenancy case first')
                    if body['operation'] == 'revise_tenancy' and isinstance(payload.get('tenancy'), dict):
                        previous = aftercare.get(m4_id, TENANT)
                        payload['tenancy'].update(tenant_id=TENANT, tenancy_id=previous['tenancy']['tenancy_id'])
                if body['operation'] == 'request_draft':
                    require(payload.get('use_model') is False and payload.get('allow_external_ai') is False,
                            422, 'external_ai_disabled', 'This synthetic demo uses deterministic drafts only')
                previous_clock = repo.get(db, 'clock', case['case_id'])
                base = datetime.fromisoformat(previous_clock['at'] if previous_clock else AFTERCARE_CLOCK)
                candidate = base + timedelta(seconds=1) if previous_clock else base
                # Poll/close progress to allowlisted scenario checkpoints, never a browser-supplied clock.
                checkpoint = datetime.fromisoformat(fixture_clocks.get(body['operation'], AFTERCARE_CLOCK))
                clock = max(candidate, checkpoint).isoformat()
                binding = {'schema_version': '1.0', 'case_id': m4_id, 'request_id': 'web-' + sha256(key.encode()).hexdigest(),
                    'actor_id': OPERATOR if role == 'operator' else TENANT, 'actor_role': role,
                    'expected_version': body['expected_version'], 'operation': body['operation'], 'payload': payload, 'as_of': clock}
                validate_aftercare('command', binding)
                # Persist the generated clock/IDs before module submission, including recoverable failures.
                repo.put(db, 'clock', case['case_id'], {'at': clock})
                repo.put(db, 'aftercare_receipt', key, {'input': body, 'command': binding})
            if body['operation'] == 'create' and case['aftercare_case_id'] is None:
                case['aftercare_pending'] = {'request_key': key, 'case_id': binding['case_id']}
                repo.put(db, 'case', case['case_id'], case)
        # The module owns its atomic receipts. A lost adapter response is recovered with this frozen command.
        try:
            result = aftercare.submit(binding)
        except AftercareError:
            with repo.transaction() as db:
                case = get(db, 'case', body['case_id'])
                if case.get('aftercare_pending', {}).get('request_key') == key:
                    case.pop('aftercare_pending')
                    repo.put(db, 'case', case['case_id'], case)
            raise
        with repo.transaction() as db:
            case = get(db, 'case', body['case_id'])
            require(case['aftercare_case_id'] in (None, binding['case_id']), 409, 'mapping_conflict', 'Reload the mapped aftercare case')
            case['aftercare_case_id'] = binding['case_id']
            case.pop('aftercare_pending', None)
            repo.put(db, 'case', case['case_id'], case)
            repo.put(db, 'aftercare_mapping', binding['case_id'], {'case_id': case['case_id']})
            repo.put(db, 'aftercare_receipt', key, {'input': body, 'command': binding, 'result': result})
        return result

    def read_aftercare(self, aftercare_id: str):
        aftercare = self.ctx.aftercare
        get = self.ctx.get
        repo = self.ctx.repo
        with repo.transaction() as db:
            get(db, 'aftercare_mapping', aftercare_id)
        return aftercare.get(aftercare_id, TENANT)

    def export_aftercare(self, aftercare_id: str):
        download = self.ctx.download
        read_aftercare = self.read_aftercare
        return download(read_aftercare(aftercare_id), 'aftercare-case')
