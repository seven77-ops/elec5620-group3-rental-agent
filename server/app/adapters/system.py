"""System orchestration for the local synthetic API."""

from fastapi.responses import Response
from ..common import require
from ..settings import AFTERCARE_CLOCK
from .business import MAX_BYTES


class SystemAdapter:
    """System orchestration around saved state and original member functions."""
    def __init__(self, ctx):
        self.ctx = ctx

    def health(self):
        return {'status': 'ok', 'mode': 'synthetic_demo'}

    def config(self):
        dataset = self.ctx.settings.dataset
        examples = self.ctx.settings.examples
        expected = self.ctx.settings.expected
        template = self.ctx.settings.template
        templates = self.ctx.settings.templates
        tenancy_template = self.ctx.settings.tenancy_template
        return {'mode': 'synthetic_demo', 'clocks': {'evaluation': dataset['as_of'], 'selection': expected['selectedAt'],
                'contract': expected['contractReferenceDate'], 'aftercare': AFTERCARE_CLOCK},
                'profile_template': template, 'tenancy_template': tenancy_template,
                'agreement_examples': [{'id': key, 'name': key + '.txt'} for key in examples],
                'capabilities': {'agent1': 'simulated_form', 'agent2': True, 'agent3': True, 'agent4': True,
                                 'external_ai': False, 'synthetic_contract_only': True, 'max_upload_bytes': MAX_BYTES,
                                 'aftercare_evidence_template': templates['create']['evidence'],
                                 'aftercare_clock_policy': 'Per-case monotonic; poll advances to 2026-11-03T09:00:00+11:00; close to 09:01; original retries retain original time'}}

    def agreement(self, example_id: str):
        examples = self.ctx.settings.examples
        require(example_id in examples, 404, 'not_found', 'Unknown synthetic agreement example')
        return Response(examples[example_id], media_type='text/plain', headers={'Content-Disposition': f'attachment; filename="{example_id}.txt"'})
