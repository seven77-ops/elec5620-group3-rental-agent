"""System orchestration for the local synthetic API."""

from fastapi.responses import Response
from ..common import require
from ..settings import AFTERCARE_CLOCK
from datetime import datetime
from zoneinfo import ZoneInfo
from .business import MAX_BYTES


class SystemAdapter:
    """System orchestration around saved state and original member functions."""
    def __init__(self, ctx):
        self.ctx = ctx

    def health(self):
        return {'status': 'ok', 'mode': self.ctx.settings.dataset['data_mode']}

    def config(self):
        dataset = self.ctx.settings.dataset
        examples = self.ctx.settings.examples
        expected = self.ctx.settings.expected
        template = self.ctx.settings.template
        templates = self.ctx.settings.templates
        tenancy_template = self.ctx.settings.tenancy_template
        real = self.ctx.settings.catalog is not None
        if real:
            tenancy_template = {'address':'','jurisdiction':'NSW','tenancy_type':'standard_residential',
                'confirmed':False,'source_ref':'user-confirmed-tenancy','source_version':1,
                'rooms':None,'carpeted':None,'outdoor':None,'furnished':None,'inventory':None,
                'inventory_confirmed':False,'baseline_evidence_refs':[]}
        return {'mode': dataset['data_mode'], 'catalog': self.ctx.settings.catalog.metadata() if self.ctx.settings.catalog else None,
                'clocks': {'evaluation': dataset['as_of'], 'selection': expected['selectedAt'],
                'contract': expected['contractReferenceDate'], 'aftercare': datetime.now(ZoneInfo('Australia/Sydney')).isoformat() if real else AFTERCARE_CLOCK},
                'profile_template': template, 'tenancy_template': tenancy_template,
                'agreement_examples': [{'id': key, 'name': key + '.txt'} for key in examples],
                'capabilities': {'agent1': 'local_service', 'agent2': True, 'agent3': True, 'agent4': True,
                                 'external_ai': self.ctx.ai_provider.public_config()['configured'], 'external_ai_opt_in': True, 'lease_draft_generation': self.ctx.settings.catalog is not None, 'synthetic_contract_only': self.ctx.settings.catalog is None, 'max_upload_bytes': MAX_BYTES,
                                 'living_services':real,
                                 'aftercare_evidence_template': [] if real else templates['create']['evidence'],
                                 'aftercare_clock_policy': 'Actual Australia/Sydney clock; original retries retain original time' if real else 'Per-case monotonic; poll advances to 2026-11-03T09:00:00+11:00; close to 09:01; original retries retain original time'}}

    def agreement(self, example_id: str):
        examples = self.ctx.settings.examples
        require(example_id in examples, 404, 'not_found', 'Unknown synthetic agreement example')
        return Response(examples[example_id], media_type='text/plain', headers={'Content-Disposition': f'attachment; filename="{example_id}.txt"'})
