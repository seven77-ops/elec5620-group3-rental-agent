"""Server-owned synthetic fixtures, clocks, runtime location and operator secret."""
from copy import deepcopy
import json
import os
from .bootstrap import ROOT
from .common import load

TENANT = 'web-demo-tenant'
OPERATOR = 'web-demo-operator'
AFTERCARE_CLOCK = '2026-10-15T10:00:00+11:00'


class Settings:
    def __init__(self, runtime_dir=None, operator_key=None):
        self.runtime_dir = runtime_dir or os.environ.get('RENTAL_RUNTIME_DIR', ROOT / '.runtime')
        self.operator_secret = operator_key if operator_key is not None else os.environ.get('RENTAL_OPERATOR_KEY', '')
        self.expected = load('integration/agent1-to-agent2/expected.json')
        self.dataset = load('agent2/data/demo/listings.json')
        self.template = load('integration/agent1-to-agent2/confirmed-profile.json')
        self.templates, self.fixture_clocks = {}, {}
        for path in sorted((ROOT / 'agent4/data/demo/requests').glob('*.json')):
            command = json.loads(path.read_text())
            self.templates.setdefault(command['operation'], command['payload'])
            self.fixture_clocks.setdefault(command['operation'], command['as_of'])
        for operation in ('create', 'revise_tenancy'):
            if operation in self.templates:
                tenancy = self.templates[operation]['tenancy']
                tenancy.pop('tenancy_id', None)
                tenancy.pop('tenant_id', None)
                tenancy['confirmed'] = False
        self.tenancy_template = deepcopy(self.templates['create']['tenancy'])
        agreement = (ROOT / 'agent3/data/demo/agreements/selection-demo.txt').read_bytes()
        self.examples = {'normal': agreement, 'rent_conflict': agreement.replace(b'$500', b'$650')}
