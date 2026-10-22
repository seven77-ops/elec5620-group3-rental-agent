"""Grounded living-service tools over the same versioned records used by the page."""
from copy import deepcopy
import re
from ..living.service import LivingService
from ..living.fields import blank_profile, PROFILE_FIELDS
from ..common import require

TOPICS = ('overview','repairs','utilities','moving','cleaning')
ACTIONS = ('view','recommend','update_profile','report_repair','update_repair')
CATEGORIES = ('electricity','gas','internet','water')
PROFILE_SCHEMA = {'type':'object','additionalProperties':False,'properties':{
    **{k:{'type':'string','maxLength':1000} for k in ('address','suburb','postcode','agent_name','agent_email','agent_phone','emergency_phone','moving_to','own_furniture','landlord_furniture','notes')},
    **{k:{'type':['integer','null'],'minimum':0,'maximum':100} for k in ('bedrooms','bathrooms')},
    **{k:{'type':['boolean','null']} for k in ('carpeted','has_pets','has_elevator')},
    'move_out_date':{'type':['string','null'],'pattern':'^[0-9]{4}-[0-9]{2}-[0-9]{2}$'},
    'utilities':{'type':'object','additionalProperties':False,'properties':{k:{'type':['string','null']} for k in CATEGORIES}}}}
INTENT_PROPERTIES = {
    'topic':{'enum':list(TOPICS)}, 'service_action':{'enum':list(ACTIONS)},
    'provider_category':{'enum':list(CATEGORIES)}, 'profile_patch':PROFILE_SCHEMA,
    'repair_id':{'type':'string','maxLength':160},
    'repair_update':{'type':'object','additionalProperties':False,'properties':{
        'status':{'enum':['prepared','contacted','resolved']},'email_tone':{'enum':['standard','polite','concise']}}},
    'repair':{'type':'object','additionalProperties':False,'required':['title','description','location','priority'],
        'properties':{'title':{'type':'string','maxLength':200},'description':{'type':'string','maxLength':3000},
                      'location':{'type':'string','maxLength':500},'priority':{'enum':['normal','urgent']}}}}
LIVING_INTENT_SCHEMA = {'type':'object','required':['intent','topic','service_action'],'additionalProperties':False,
                       'properties':{'intent':{'const':'living_services'},**INTENT_PROPERTIES}}
ALIASES = {'origin':('origin','origin energy'), 'energyaustralia':('energyaustralia','energy australia'),
    'aussie-broadband':('aussie broadband','aussie'), 'two-men-and-a-truck':('two men','两个人一辆卡车'),
    'sydney-water':('sydney water',)}


def read_snapshot(ctx, db, case_id):
    return ctx.repo.get(db,'living_services',case_id) or {
        'case_id':case_id,'version':0,'profile':blank_profile(),'repairs':[],'bookings':[],'updated_at':None}


def model_context(record, directory, focus=None):
    """Contact details and exact address stay local; routing needs service choices only."""
    return {'version':record['version'], 'profile':{k:record['profile'][k] for k in
        ('suburb','bedrooms','bathrooms','carpeted','has_pets','move_out_date','utilities')},
        'repairs':[{k:r[k] for k in ('repair_id','title','description','location','status')} |
                   {'latest_update':r.get('updates',[])[-1:] } for r in record['repairs'][-20:]],
        **(focus or {}),
        'providers':[{k:p[k] for k in ('id','name','categories')} for p in directory['providers']]}


def grounded_patch(patch, source, directory):
    if not isinstance(patch,dict): return {}
    result={}; folded=source.casefold()
    providers={p['id']:p for p in directory['providers']}
    for key,value in patch.items():
        if key not in PROFILE_FIELDS: continue
        if key=='utilities' and isinstance(value,dict):
            choices={}
            for category,identifier in value.items():
                provider=providers.get(identifier) if isinstance(identifier,str) else None
                if provider and category in provider['categories']:
                    names=(provider['name'].casefold(),identifier.casefold(),*ALIASES.get(identifier,()))
                    if any(re.search(r'(?<![a-z0-9])'+re.escape(name)+r'(?![a-z0-9])',folded) for name in names):
                        choices[category]=identifier
            if choices: result[key]=choices
        elif isinstance(value,str) and value and value.casefold() in folded:
            result[key]=value
        elif key in ('bedrooms','bathrooms') and type(value) is int:
            if re.search(r'(?<!\d)'+str(value)+r'(?!\d)',source): result[key]=value
        elif key in ('carpeted','has_pets','has_elevator') and type(value) is bool:
            word={'carpeted':'地毯','has_pets':'宠物','has_elevator':'电梯'}[key]
            positive=bool(re.search(r'(?:有|带)'+word,source))
            negative=bool(re.search(r'(?:没有|无|不带)'+word,source))
            if (value and positive and not negative) or (not value and negative): result[key]=value
    return result


def answer_living(ctx, intent, case_id, conversation, user_message, expected_version, focus=None):
    service=LivingService(ctx); record=service.read(case_id); directory=service.directory()
    require(record['version']==expected_version,409,'living_context_changed','租后资料已变化，请读取最新资料后重试。')
    topic=intent.get('topic','overview'); operation=intent.get('service_action','view')
    nav={'repairs':'repairs','utilities':'utilities','moving':'services','cleaning':'services','overview':'repairs'}[topic]
    answer={'intent':'living_services','agent':'agent4','listings':[],'providers':[],
            'content':'可以在租后服务里记录报修、水电气网、搬运和清洁安排。',
            'actions':[{'type':'navigate','label':'查看对应租后服务','page':'aftercare?tab='+nav}]}
    # Only explicitly stated latest-turn profile values are proposed. Existing
    # stored contacts are never reinterpreted as newly supplied information.
    if operation=='update_profile':
        patch=grounded_patch(intent.get('profile_patch',{}),user_message,directory)
        if patch:
            proposal=service.prepare_proposal(case_id,'profile',patch,user_message)
            answer['actions'].insert(0,{'type':'apply_living_services','label':'确认同步租后资料',
                'proposal_id':proposal['proposal_id'],'expected_version':proposal['expected_version'],
                'summary':proposal['summary']})
            answer['content']='已整理成下面的租后资料建议。核对并确认后，会同步到租后服务页面；其他已保存信息保持原值。'
        else: answer['content']='还没有提取到能从你这条消息核对的资料。请明确说出当前使用的公司或联系信息，我再整理给你确认。'
    elif operation=='update_repair':
        from .repair_dialogue import propose_update
        answer.update(propose_update(ctx,intent,case_id,record,focus or {},user_message))
    elif operation=='report_repair':
        repair=deepcopy(intent.get('repair',{}))
        user_sources=[m['content'] for m in conversation['messages'][-12:] if m['role']=='user']+[user_message]
        description=repair.get('description','')
        if not description or not any(description in s for s in user_sources): description=user_message
        title=repair.get('title','')
        if not title or not any(title in s for s in user_sources): title='房屋报修'
        location=repair.get('location','')
        if not any(location in s for s in user_sources): location=''
        values={'title':title[:200],'description':description,'location':location[:500],
                'priority':'urgent' if repair.get('priority')=='urgent' else 'normal'}
        proposal=service.prepare_proposal(case_id,'repair',values,user_message)
        answer['actions'].insert(0,{'type':'apply_living_services','label':'确认生成报修草稿',
            'proposal_id':proposal['proposal_id'],'expected_version':proposal['expected_version'],'summary':proposal['summary']})
        answer['_living_focus']={'proposal_id':proposal['proposal_id']}
        answer['content']='我会按你描述的情况准备报修记录和邮件草稿。确认后可在日常报修里核对、复制，或用自己的邮件客户端打开。尚未发送邮件。'
        if not record['profile']['agent_email']: answer['content']+=' 请先在租后资料中补充中介邮箱；没有邮箱时也可以复制文字或拨打已记录的电话。'
        if values['priority']=='urgent': answer['content']+=' 紧急维修应立即联系中介或租约中的紧急维修联系人，不要只等待邮件回复。'
    elif topic=='utilities':
        providers={p['id']:p for p in directory['providers']}
        labels={'electricity':'电力','gas':'燃气','internet':'网络','water':'供水'}
        selected=[labels[k]+'：'+providers[v]['name'] for k,v in record['profile']['utilities'].items() if v in providers]
        answer['content']=('已保存的公司：'+'；'.join(selected)+'。\n' if selected else '目前还没有保存水电气网公司。\n')
        answer['content']+='下面是可核对的官方入口，先按房屋地址确认可用服务，再比较套餐；目录没有实时费率，不能据此判断哪家最便宜。供水方依地址确认。'
        category=intent.get('provider_category')
        answer['providers']=[p for p in directory['providers'] if
            category in p['categories']] if category else [p for p in directory['providers'] if set(p['categories'])&set(CATEGORIES)]
    elif topic in ('moving','cleaning'):
        category='removalist' if topic=='moving' else 'cleaner'
        answer['providers']=[p for p in directory['providers'] if category in p['categories']]
        answer['content']=('可先向下面的搬家公司询价。请准备搬出和搬入区域、楼层/电梯、家具清单及日期；只处理自己的物品，房东家具另行核对。' if topic=='moving' else
            '可先向下面的清洁公司核对服务范围。询价时说明卧卫数、地毯、阳台及是否为空房，并确认烤箱、窗户、返工条件等。也可以自行清洁，不会自动创建预约。')
        answer['content']+=' 页面可记录实际报价和预约日期；这里没有实时档期，也未联系商家。'
    elif topic=='repairs':
        labels={'prepared':'草稿待联系','contacted':'已联系（用户记录）','resolved':'已解决（用户记录）'}
        answer['content']='\n'.join(r['title']+'：'+labels[r['status']] for r in record['repairs'][-5:]) or '目前没有已保存的报修。告诉我哪里出现了什么问题，我可以整理成待确认的维修邮件草稿。'
    # Proposals retain their exact base version. The caller also rejects changed
    # living records before committing the assistant turn.
    return answer
