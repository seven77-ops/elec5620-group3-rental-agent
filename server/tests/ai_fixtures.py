"""Explicit test-only model double. Never wired into normal product startup."""
from datetime import datetime, timezone
import re
from time import monotonic
from server.app.ai.provider import ProviderError


class TestProvider:
    def __init__(self, mode='valid', on_call=None):
        self.inputs = []
        self.mode, self.on_call = mode, on_call

    def public_config(self):
        return {'enabled': True, 'configured': True, 'provider': 'test_stub', 'model': 'local-test-double', 'timeout_seconds': 12}

    def call(self, context):
        start = monotonic()
        self.inputs.append(context)
        meta = {'task': context['task'], 'provider': 'test_stub', 'model': 'local-test-double',
                'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'succeeded',
                'attempted': True, 'simulated': True, 'duration_ms': 0}
        if self.on_call:
            self.on_call(context)
        if self.mode == 'error':
            meta.update(status='failed', error_code='ai_timeout')
            raise ProviderError('ai_timeout', meta)
        if context['task'] == 'contract_extract':
            document = context['document']
            lines = document['text'].splitlines()
            entries = []
            for index, line in enumerate(lines, 1):
                low = line.lower()
                values = {}
                if 'address' in low:
                    address = line.split(':',1)[-1].strip() if ':' in line else line.split(' is ',1)[-1].strip()
                    values['address'] = address
                if 'rent' in low and ('500' in line or '650' in line):
                    values.update(rent_amount=650 if '650' in line else 500, rent_period='week', rent_scope='per_person', currency='AUD')
                dates = re.findall(r'20\d\d-\d\d-\d\d', line)
                if dates and ('start' in low or 'commence' in low):
                    values['start_date'] = dates[0]
                if dates and ('end' in low or 'expiry' in low):
                    values['end_date'] = dates[0]
                for field,value in values.items():
                    entries.append({'field':field,'value':value,'line':index,'quote':line if self.mode != 'hallucinated' else 'invented quote'})
            result = {'fields': entries}
        elif context['task'] == 'contract_explain':
            result = {'explanations':[{'finding_id':f['id'],'text':'测试替身解释：请核对系统发现的差异及原文。'} for f in context['findings']]}
        else:
            rows = context.get('recommendations', [])
            result = {'items':[]}
            for row in rows:
                refs = row.get('evidence_refs', {})
                if isinstance(refs,dict):
                    refs = [e.get('source_ref') for e in refs.values() if isinstance(e,dict) and e.get('source_ref')]
                result['items'].append({'listing_id':row['listing_id'],'text':'测试替身解读：请结合已保存评分与证据比较通勤和费用。','evidence_refs':list(dict.fromkeys(refs))[:2]})
        meta['duration_ms'] = round((monotonic()-start)*1000)
        return result, meta
