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
        'status':{'enum':['prepared','contacted','resolved']},'email_tone':{'enum':['standard','polite','concise']},
        'email_language':{'enum':['en','zh']}}},
    'repair':{'type':'object','additionalProperties':False,'required':['title','description','location','priority'],
        'properties':{'title':{'type':'string','maxLength':200},'description':{'type':'string','maxLength':3000},
                      'location':{'type':'string','maxLength':500},'priority':{'enum':['normal','urgent']},
                      'email_language':{'enum':['en','zh']},'email_tone':{'enum':['standard','polite','concise']}}}}
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
        'utility_plan_catalog':directory.get('plan_catalog'),
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
    require(record['version']==expected_version,409,'living_context_changed','Aftercare details changed. Reload the latest details and retry.')
    topic=intent.get('topic','overview'); operation=intent.get('service_action','view')
    nav={'repairs':'repairs','utilities':'utilities','moving':'services','cleaning':'services','overview':'repairs'}[topic]
    answer={'intent':'living_services','agent':'agent4','listings':[],'providers':[],
            'content':'You can record repairs, utilities, moving and cleaning arrangements in Aftercare.',
            'actions':[{'type':'navigate','label':'View aftercare service','page':'aftercare?tab='+nav}]}
    # Only explicitly stated latest-turn profile values are proposed. Existing
    # stored contacts are never reinterpreted as newly supplied information.
    if operation=='update_profile':
        patch=grounded_patch(intent.get('profile_patch',{}),user_message,directory)
        if patch:
            proposal=service.prepare_proposal(case_id,'profile',patch,user_message)
            answer['actions'].insert(0,{'type':'apply_living_services','label':'Confirm and sync aftercare details',
                'proposal_id':proposal['proposal_id'],'expected_version':proposal['expected_version'],
                'summary':proposal['summary']})
            answer['content']='Review the proposed aftercare details below. Confirm to sync them to Aftercare; other saved details are retained.'
        else: answer['content']='No verifiable details were extracted from this message. Specify your current provider or contact details so I can prepare them for confirmation.'
    elif operation=='update_repair':
        from .repair_dialogue import propose_update
        answer.update(propose_update(ctx,intent,case_id,record,focus or {},user_message))
    elif operation=='report_repair':
        repair=deepcopy(intent.get('repair',{}))
        user_sources=[m['content'] for m in conversation['messages'][-12:] if m['role']=='user']+[user_message]
        description=repair.get('description','')
        if not description or not any(description in s for s in user_sources): description=user_message
        title=repair.get('title','')
        if not title or not any(title in s for s in user_sources): title='Property repair'
        location=repair.get('location','')
        if not any(location in s for s in user_sources): location=''
        values={'title':title[:200],'description':description,'location':location[:500],
                'priority':'urgent' if repair.get('priority')=='urgent' else 'normal',
                **{key:repair[key] for key in ('email_language','email_tone') if key in repair}}
        from .repair_drafts import generate_draft, preview
        values, call = generate_draft(ctx,case_id,values,record,user_message)
        proposal=service.prepare_proposal(case_id,'repair',values,user_message)
        answer['actions'].insert(0,{'type':'apply_living_services','label':'Save to Aftercare',
            'proposal_id':proposal['proposal_id'],'expected_version':proposal['expected_version'],'summary':proposal['summary']})
        answer['repair_email']=preview(values,record['profile']['agent_email'],proposal)
        answer['_repair_call']=call
        answer['_living_focus']={'proposal_id':proposal['proposal_id']}
        answer['content']='Here is an email draft based on your description. Copy it or ask for changes. Confirm to save the same draft in Aftercare. The email has not been sent.'
        if values['priority']=='urgent': answer['content']+=' For urgent repairs, contact your agent or the emergency repair contact in your lease immediately; do not rely only on an email response.'
    elif topic=='utilities':
        providers={p['id']:p for p in directory['providers']}
        labels={'electricity':'Electricity','gas':'Gas','internet':'Internet','water':'Water'}
        selected=[labels[k]+'：'+providers[v]['name'] for k,v in record['profile']['utilities'].items() if v in providers]
        answer['content']=('Saved providers: '+'；'.join(selected)+'。\n' if selected else 'No utility providers are saved yet.\n')
        from ..living.utility_advice import advise
        result=advise(ctx.utility_plans,user_message,category=intent.get('provider_category'),profile=record['profile'])
        answer['content']+=result['content']
        answer['utility_search']=result['criteria']
        grouped={}
        for plan in result['plans']:
            identifier=plan['provider_id']
            if identifier not in providers:continue
            grouped.setdefault(identifier,{**providers[identifier],'plans':[]})['plans'].append(plan)
        answer['providers']=list(grouped.values())
    elif topic in ('moving','cleaning'):
        category='removalist' if topic=='moving' else 'cleaner'
        answer['providers']=[p for p in directory['providers'] if category in p['categories']]
        answer['content']=('Ask the moving companies below for quotes. Prepare pickup and delivery suburbs, floor and lift details, an inventory and dates. Confirm arrangements for landlord-owned furniture separately.' if topic=='moving' else
            'Check the cleaning companies below for service coverage. Mention bedrooms, bathrooms, carpets, balconies and whether the property is empty; confirm ovens, windows and any re-clean conditions. You can also clean it yourself. No booking is created automatically.')
        answer['content']+=' Record actual quotes and booking dates on the service page. Live availability is unavailable and no provider has been contacted.'
    elif topic=='repairs':
        labels={'prepared':'Draft; contact pending','contacted':'Contacted (user recorded)','resolved':'Resolved (user recorded)'}
        answer['content']='\n'.join(r['title']+'：'+labels[r['status']] for r in record['repairs'][-5:]) or 'No repairs are saved yet. Describe the issue and its location to prepare a repair email draft for review.'
    # Proposals retain their exact base version. The caller also rejects changed
    # living records before committing the assistant turn.
    return answer
