"""Isolated UI verification: model double only; catalogue and workflows remain real.

Never imported by normal app startup. No calls to external AI providers.
English output is fixed; both English and Chinese test inputs remain recognised.
"""
import os
import re
from datetime import datetime, timezone
from server.app.main import create_app


class AssistantDemoProvider:
    def public_config(self):
        return {'enabled': True, 'configured': True, 'provider': 'test_stub',
                'model': 'assistant-ui-test-only', 'timeout_seconds': 12}

    @staticmethod
    def _meta(task):
        return {'task': task, 'provider': 'test_stub', 'model': 'assistant-ui-test-only',
                'status': 'succeeded', 'attempted': True, 'simulated': True,
                'started_at': datetime.now(timezone.utc).isoformat(), 'duration_ms': 0}

    @staticmethod
    def _lease_fields(message):
        """Return only values with verbatim support in this synthetic user input."""
        fields = []
        rent = re.search(r'每周\s*(\d+)|(?:aud\s*|\$)?(\d+)\s*(?:per\s+week|/week|a\s+week|weekly)', message, re.I)
        if rent:
            amount = int(next(value for value in rent.groups() if value is not None))
            fields.extend([{'field': 'rent_amount', 'value': amount, 'quote': rent.group()},
                           {'field': 'rent_period', 'value': 'week', 'quote': rent.group()}])
        bond = re.search(r'(?:押金|bond(?:\s+is)?\s*[:=]?)\s*(?:AUD\s*|\$)?(\d+)', message, re.I)
        if bond:
            fields.append({'field': 'bond', 'value': int(bond.group(1)), 'quote': bond.group()})
        tenant = re.search(r'(?:租客|tenant(?:\s+is)?\s*[:=]?)\s*(Zhang San)', message, re.I)
        if tenant:
            fields.append({'field': 'tenant_names', 'value': tenant.group(1), 'quote': tenant.group()})
        return {'fields': fields}

    def call(self, context):
        task = context['task']
        meta = self._meta(task)
        if task == 'rag_summary_check':
            return {'supported': [True] * len(context['checks']),
                    'original_supported': [True] * len(context['checks']),
                    'texts': [check['claim'] for check in context['checks']]}, meta
        if task == 'rag_grounded_summary':
            evidence = context['evidence'][0]
            passage = evidence['passages'][0]
            return {'claims': [{'text': 'Contact the landlord or agent about repairs.',
                                'evidence_id': evidence['evidence_id'],
                                'quote_ids': [passage['quote_id']],
                                'grounded': True, 'conditions_preserved': True}],
                    'unknowns': []}, meta
        if task == 'aftercare_deduction_extract':
            return {'claims': [{'amount': 180, 'reason': 'carpet cleaning',
                                'quote': '$180 for carpet cleaning'}],
                    'event_date': None, 'event_date_quote': None}, meta
        if task == 'aftercare_draft_select':
            return {'statement_ids': [statement['id'] for statement in context['catalogue']
                                      if statement['mandatory']],
                    'closing': 'itemisation'}, meta
        if task == 'rag_answer':
            if context['question'] == 'What is my exact rent debt?':
                return {'claims': [], 'unknowns': ['Your rent ledger and payment dates are not supplied.']}, meta
            evidence = context['evidence'][0]
            return {'claims': [{'text': 'Contact your landlord or agent to request repairs.',
                                'evidence_id': evidence['evidence_id'],
                                'quote_id': evidence['passages'][0]['quote_id']}], 'unknowns': []}, meta
        if task == 'repair_email_polish':
            draft = context['draft']
            overnight = '昨晚' in draft or 'last night' in draft.casefold()
            issue = ('The kitchen sink has been leaking since last night.' if overnight
                     else 'The kitchen sink has been leaking continuously.' if '水槽' in draft or 'sink' in draft.casefold()
                     else 'The kitchen tap is leaking.')
            tone = context.get('tone', 'polite')
            request = ('Please arrange a repair.' if tone == 'concise'
                       else 'Could you please arrange an inspection and repair, and let me know the next steps?'
                       if tone == 'polite' else 'Could you please arrange a repair?')
            recipient = context.get('recipient_name') or 'Property Manager'
            subject = 'Kitchen sink repair request' if 'sink' in issue else 'Kitchen tap repair request'
            return {'subject': subject, 'body': f'Dear {recipient},\n\n{issue} {request}\n\nThank you.'}, meta
        if task == 'assistant_preferences_reply':
            return {'is_reply': False, 'brief_patch': {}}, meta
        if task == 'assistant_area_followup':
            message = context.get('message', '')
            chosen = '那先看Ashfield吧' in message or 'look in ashfield' in message.casefold()
            return {'continue_housing': chosen, 'brief_patch': {'suburb': 'Ashfield'} if chosen else {}}, meta
        if task == 'lease_draft_extract':
            return self._lease_fields(context.get('message', '')), meta
        if task != 'assistant_intent':
            raise ValueError(f'Unsupported isolated UI fixture task: {task}')
        message = context.get('message') or context.get('latest_user_message') or context.get('query') or ''
        lower = message.casefold()
        has = lambda *words: any(word.casefold() in lower for word in words)
        basic_intakes={
            'Record my rental needs: any suburb, AUD 900 per week for the whole property, one person, at least two bedrooms and two bathrooms, no parking.':None,
            'Record my rental needs: Burwood, AUD 900 per week for the whole property, one person, at least two bedrooms and two bathrooms, no parking.':'Burwood',
        }
        if message in basic_intakes:
            result={'intent':'collect_preferences','brief_patch':{'suburb':basic_intakes[message],
                'budget_amount':900,'budget_period':'week','budget_scope':'whole_property','occupants':1,
                'min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':0,'rental_mode':'whole_property'}}
        elif message in ('How do I request repairs?', '在 NSW，租客怎么报修？', 'What is my exact rent debt?', 'How can I avoid rental scams when finding accommodation near university?'):
            result = {'intent': 'knowledge'}
        elif has('网络套餐', 'internet plan'):
            result = {'intent': 'living_services', 'topic': 'utilities', 'service_action': 'recommend', 'provider_category': 'internet'}
        elif has('AGL电费', 'agl electricity'):
            result = {'intent': 'living_services', 'topic': 'utilities', 'service_action': 'recommend', 'provider_category': 'electricity'}
        elif has('水费怎么收', 'water charges', 'water bill'):
            result = {'intent': 'living_services', 'topic': 'utilities', 'service_action': 'view', 'provider_category': 'water'}
        elif (has('悉大', 'usyd', 'university of sydney') and has('步行20分钟', '20-minute walk', 'walk 20 minutes', '20 minutes walking')):
            result = {'intent': 'recommend_areas', 'brief_patch': {'suburb': None, 'budget_amount': 1200,
                      'budget_period': 'week', 'budget_scope': 'whole_property', 'rental_mode': 'whole_property',
                      'min_bedrooms': 1, 'min_bathrooms': 1, 'min_car_spaces': 0, 'occupants': 1,
                      'commute_mode': 'walk', 'commute_max_minutes': 20}}
        elif lower.strip() in ('20分钟', '20 minutes'):
            result = {'intent': 'recommend_areas', 'brief_patch': {'commute_max_minutes': 20}}
        elif has('我想住Burwood预算1200每周', 'burwood with a weekly budget of 1200'):
            result = {'intent': 'collect_preferences', 'brief_patch': {'suburb': 'Burwood', 'budget_amount': 1200,
                      'budget_period': 'week', 'budget_scope': 'unknown'}}
        elif lower.strip() in ('整套', 'whole property'):
            result = {'intent': 'collect_preferences', 'brief_patch': {}}
        elif has('比较 Burwood 和 Ashfield', 'compare burwood and ashfield'):
            result = {'intent': 'area_advice', 'areas': ['Burwood', 'Ashfield'], 'brief_patch': {
                      'budget_amount': 850, 'budget_period': 'week', 'budget_scope': 'whole_property',
                      'min_bedrooms': 1, 'lifestyle_priorities': ['food']}}
        elif has('那先看Ashfield吧', 'look in ashfield'):
            result = {'intent': 'area_advice', 'areas': ['Ashfield']}
        elif has('预算降到700', 'reduce the budget to 700'):
            result = {'intent': 'area_advice', 'areas': ['Burwood', 'Ashfield'], 'focus': 'housing',
                      'brief_patch': {'budget_amount': 700}}
        elif has('比较 Burwood 和 Rhodes', 'compare burwood and rhodes'):
            result = {'intent': 'area_advice', 'areas': ['Burwood', 'Rhodes'], 'brief_patch': {
                      'lifestyle_priorities': ['parks', 'food'], 'budget_amount': 900,
                      'budget_period': 'week', 'budget_scope': 'whole_property', 'min_bedrooms': 2}}
        elif has('比较 Carlton 的安静和安全', 'compare quiet and safety in carlton'):
            result = {'intent': 'area_advice', 'areas': ['Carlton'], 'brief_patch': {'lifestyle_priorities': ['quiet', 'safety']}}
        elif has('我的电是AGL', 'my electricity is with agl'):
            result = {'intent': 'living_services', 'topic': 'utilities', 'service_action': 'update_profile',
                      'profile_patch': {'utilities': {'electricity': 'agl', 'internet': 'tpg'}}}
        elif (has('报修') and has('漏水')) or (has('leak') and has('repair email', 'report a repair')):
            result = {'intent': 'living_services', 'topic': 'repairs', 'service_action': 'report_repair',
                      'repair': {'title': 'Kitchen sink repair',
                                 'description': ('The kitchen sink has been leaking since last night.'
                                                 if has('昨晚', 'last night') else 'The kitchen sink has been leaking continuously.'),
                                 'location': 'Kitchen', 'priority': 'normal'}}
        elif has('简洁', '简短', 'more concise', 'shorter email'):
            result = {'intent': 'living_services', 'topic': 'repairs', 'service_action': 'update_repair',
                      'repair_update': {'email_tone': 'concise'}}
        elif has('这封报修邮件改成', 'regenerate this repair email in english', 'rewrite this repair email in english'):
            result = {'intent': 'living_services', 'topic': 'repairs', 'service_action': 'update_repair',
                      'repair_update': {'email_language': 'en'}}
        elif has('客气', '礼貌', 'more polite'):
            result = {'intent': 'living_services', 'topic': 'repairs', 'service_action': 'update_repair',
                      'repair_update': {'email_tone': 'polite'}}
        elif has('中介回复', '跟进报修', 'agent replied', 'follow up on the repair'):
            result = {'intent': 'living_services', 'topic': 'repairs', 'service_action': 'update_repair',
                      'repair_update': {'status': 'contacted'}}
        elif has('修好了', 'repair is complete', 'repair is resolved', 'has been fixed'):
            result = {'intent': 'living_services', 'topic': 'repairs', 'service_action': 'update_repair',
                      'repair_update': {'status': 'resolved'}}
        elif has('清洁公司', 'cleaning compan'):
            result = {'intent': 'living_services', 'topic': 'cleaning', 'service_action': 'recommend'}
        elif has('搬家公司', 'moving compan'):
            result = {'intent': 'living_services', 'topic': 'moving', 'service_action': 'recommend'}
        elif has('哪家电力', '哪家公司', 'which electricity provider', 'which company'):
            result = {'intent': 'living_services', 'topic': 'utilities', 'service_action': 'view'}
        elif has('确认两卧方案', '改成', '预算改', 'confirm the two-bedroom plan', 'change my budget'):
            result = {'intent': 'update_preferences', 'preference_patch': {
                      'budget': {'maximum': 1500}, 'housing_preferences': {
                          'suburb': 'Rhodes', 'min_bedrooms': 2, 'min_bathrooms': 2, 'min_car_spaces': 1}}}
        elif has('帮我整理预算', 'help me work through my budget'):
            result = {'intent': 'collect_preferences', 'brief_patch': {}}
        elif '2b2b' in lower:
            result = {'intent': 'collect_preferences', 'brief_patch': {'suburb': 'Rhodes', 'budget_amount': 800,
                      'occupants': 1, 'min_bedrooms': 2, 'min_bathrooms': 2, 'min_car_spaces': 0}}
        elif has('整套，每周', 'whole property, weekly'):
            result = {'intent': 'collect_preferences', 'brief_patch': {'budget_period': 'week',
                      'budget_scope': 'whole_property', 'rental_mode': 'whole_property'}}
        elif has('那900', 'then 900'):
            result = {'intent': 'search', 'filters': {'max_weekly_rent': 900}}
        elif has('问中介', '下一步问', '准备看房', 'ask the agent', 'prepare an inspection'):
            result = {'intent': 'followup'}
        elif (has('生成') and has('合同')) or has('generate a lease', 'prepare a lease draft'):
            result = {'intent': 'draft_contract'}
        elif has('合同', 'contract', 'lease'):
            result = {'intent': 'contract'}
        elif has('退租', '押金', '租后', 'aftercare', 'move out', 'bond'):
            result = {'intent': 'aftercare'}
        elif has('安静', '舒服', 'quiet', 'comfortable'):
            result = {'intent': 'clarify', 'clarification': 'Noise data is unavailable. Do you prioritise bedroom count or rent?'}
        elif has('比较', 'compare'):
            # Explicit comparison IDs and reference resolution remain server-owned.
            result = {'intent': 'compare'}
        elif has('解释', '第一套', 'explain', 'first listing'):
            result = {'intent': 'explain'}
        else:
            result = {'intent': 'search', 'filters': {'suburb': 'Rhodes', 'max_weekly_rent': 1500,
                      'min_bedrooms': 2, 'min_bathrooms': 2, 'min_car_spaces': 1}}
        return result, meta


app = create_app(runtime_dir=os.environ.get('RENTAL_ASSISTANT_TEST_RUNTIME', '/tmp/rental-assistant-ui-tests'),
                 operator_key='test-only-local', ai_provider=AssistantDemoProvider())
