"""Isolated UI verification: model double only; catalogue and workflows remain real.

Never imported by normal app startup. No calls to external AI providers.
"""
import os
from datetime import datetime, timezone
from server.app.main import create_app


class AssistantDemoProvider:
    def public_config(self):
        return {'enabled':True,'configured':True,'provider':'test_stub',
                'model':'assistant-ui-test-only','timeout_seconds':12}

    def call(self, context):
        if context['task'] == 'lease_draft_extract':
            return {'fields':[{'field':'rent_amount','value':600,'quote':'每周600'},
                {'field':'rent_period','value':'week','quote':'每周600'},
                {'field':'bond','value':2400,'quote':'押金2400'},
                {'field':'tenant_names','value':'Zhang San','quote':'租客 Zhang San'}]}, {
                'task':'lease_draft_extract','provider':'test_stub','model':'draft-ui-test-only',
                'status':'succeeded','attempted':True,'simulated':True}
        if context['task'] != 'assistant_intent':
            raise ValueError('UI fixture only accepts assistant intent')
        message = context.get('message') or context.get('latest_user_message') or context.get('query') or ''
        if '我的电是AGL' in message:
            result={'intent':'living_services','topic':'utilities','service_action':'update_profile',
                    'profile_patch':{'utilities':{'electricity':'agl','internet':'tpg'}}}
        elif '客气' in message or '礼貌' in message:
            result={'intent':'living_services','topic':'repairs','service_action':'update_repair','repair_update':{'email_tone':'polite'}}
        elif '中介回复' in message or '跟进报修' in message:
            result={'intent':'living_services','topic':'repairs','service_action':'update_repair','repair_update':{'status':'contacted'}}
        elif '修好了' in message:
            result={'intent':'living_services','topic':'repairs','service_action':'update_repair','repair_update':{'status':'resolved'}}
        elif '报修' in message and '漏水' in message:
            result={'intent':'living_services','topic':'repairs','service_action':'report_repair',
                    'repair':{'title':'房屋报修','description':'厨房水槽下面一直漏水','location':'厨房','priority':'normal'}}
        elif '清洁公司' in message:
            result={'intent':'living_services','topic':'cleaning','service_action':'recommend'}
        elif '搬家公司' in message:
            result={'intent':'living_services','topic':'moving','service_action':'recommend'}
        elif '哪家电力' in message or '哪家公司' in message:
            result={'intent':'living_services','topic':'utilities','service_action':'view'}
        elif '确认两卧方案' in message or '改成' in message or '预算改' in message:
            result = {'intent':'update_preferences','preference_patch':{
                'budget':{'maximum':1500},'housing_preferences':{
                    'suburb':'Rhodes','min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':1}}}
        elif '帮我整理预算' in message:
            result={'intent':'collect_preferences','brief_patch':{}}
        elif '2b2b' in message:
            result={'intent':'collect_preferences','brief_patch':{'suburb':'Rhodes','budget_amount':800,
                'occupants':1,'min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':0}}
        elif '整套，每周' in message:
            result={'intent':'collect_preferences','brief_patch':{'budget_period':'week',
                'budget_scope':'whole_property','rental_mode':'whole_property'}}
        elif '那900' in message:
            result={'intent':'search','filters':{'max_weekly_rent':900}}
        elif any(word in message for word in ('问中介','下一步问','准备看房')):
            result = {'intent':'followup'}
        elif '生成' in message and '合同' in message:
            result = {'intent':'draft_contract'}
        elif '合同' in message:
            result = {'intent':'contract'}
        elif any(word in message for word in ('退租','押金','租后')):
            result = {'intent':'aftercare'}
        elif '安静' in message or '舒服' in message:
            result = {'intent':'clarify','clarification':'目前没有噪声数据。你更重视卧室数量还是租金？'}
        elif '比较' in message:
            # Reference resolution is server-owned; explicit IDs are passed by the UI.
            result = {'intent':'compare'}
        elif '解释' in message or '第一套' in message:
            result = {'intent':'explain'}
        else:
            result = {'intent':'search','filters':{'suburb':'Rhodes','max_weekly_rent':1500,
                                                  'min_bedrooms':2,'min_bathrooms':2,'min_car_spaces':1}}
        return result, {'task':'assistant_intent','provider':'test_stub','model':'assistant-ui-test-only',
                        'status':'succeeded','attempted':True,'simulated':True,
                        'started_at':datetime.now(timezone.utc).isoformat(),'duration_ms':0}


app = create_app(runtime_dir=os.environ.get('RENTAL_ASSISTANT_TEST_RUNTIME','/tmp/rental-assistant-ui-tests'),
                 operator_key='test-only-local',ai_provider=AssistantDemoProvider())
