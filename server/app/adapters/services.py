"""Services orchestration for the local synthetic API."""
import hmac

from fastapi.responses import Response
from ..bootstrap import ROOT
from ..common import require, opaque_ref
from ..repository import canonical
from ..settings import OPERATOR
from .business import AftercareAgent
from ..repository import Repository
from .agent1 import Agent1Bridge
from ..ai.provider import ModelProvider
from ..real_data.providers import DataProviders


class Services:
    """Shared saved-object authorization, identity, gates and durable receipt helpers."""
    def __init__(self, settings, ai_provider=None, data_provider=None):
        self.settings = settings
        self.ai_provider = ai_provider if ai_provider is not None else ModelProvider()
        self.data_provider = data_provider if data_provider is not None else DataProviders()
        self.repo = Repository(settings.runtime_dir)
        self.preferences = Agent1Bridge(self.repo)
        self.aftercare = AftercareAgent(self.repo.directory / 'aftercare.sqlite3', operator_ids={OPERATOR}, gateway=None)

    def safe_message(self, message):
        repo = self.repo
        result = str(message).replace(str(repo.directory), '[runtime]').replace(str(ROOT), '[application]')
        return result[:1500]

    def get(self, db, kind, identifier):
        repo = self.repo
        opaque_ref(identifier)
        value = repo.get(db, kind, identifier)
        require(value is not None, 404, 'not_found', 'The saved object was not found')
        return value

    def operator(self, request):
        operator_secret = self.settings.operator_secret
        supplied = request.headers.get('X-Operator-Key', '')
        require(bool(operator_secret) and hmac.compare_digest(supplied, operator_secret), 403, 'access_denied',
                'A locally configured operator key is required')

    def current(self, case, version=None):
        latest = case['confirmations'][-1] if case['confirmations'] else None
        require(latest is not None and latest['fingerprint'] == case['draft']['fingerprint'] and
                latest['draft_revision'] == case['draft']['revision'] and (version is None or latest['version'] == version),
                409, 'unconfirmed_profile', 'Confirm the exact current saved draft before continuing')
        self.preferences.current(case, latest)
        return latest

    def selected(self, case):
        current = self.current
        latest = current(case)
        require(case['selection'] is not None and case['selection']['profile_version'] == latest['version'],
                409, 'selection_required', 'Choose and confirm a listing from the current confirmed preferences')
        require(self.settings.catalog is None or case['selection'].get('data_mode') == 'real_listings',
                409, 'legacy_selection', '历史模拟选择不参与真实房源流程，请重新生成真实候选。')
        require(case['selection'].get('data_mode') != 'real_listings', 409, 'real_selection_unverified',
                '此房源已保存为真实候选；尚需核实在租状态、租金计价和租期，当前合同接口不能把它当作已核实证据包。')
        return case['selection']

    def contract_selection(self, case):
        """Authorize a candidate for document processing, without certifying its facts."""
        if not case.get('selection') or case['selection'].get('data_mode') != 'real_listings':
            return self.selected(case)
        latest = self.current(case)
        selection = case['selection']
        require(selection['profile_version'] == latest['version'] and
                selection.get('profile_fingerprint') == latest['fingerprint'],
                409, 'stale_selection', '请按当前确认需求重新选择候选。')
        return selection

    def receipt(self, db, kind, key, body):
        repo = self.repo
        saved = repo.get(db, kind, key)
        if saved:
            require(saved['input'] == body, 409, 'request_conflict', 'This request ID belongs to different input')
        return saved

    def save_receipt(self, db, kind, key, body, result):
        repo = self.repo
        repo.put(db, kind, key, {'input': body, 'result': result})

    def download(self, value, name):
        return Response(canonical(value), media_type='application/json', headers={'Content-Disposition': f'attachment; filename="{name}.json"'})
