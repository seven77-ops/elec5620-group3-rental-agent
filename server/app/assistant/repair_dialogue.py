"""Resolve explicit repair references and durable conversation focus locally."""
from copy import deepcopy
from ..living.service import LivingService


def repair_focus(ctx, case_id, conversation, record):
    focus=conversation.get('living_focus',{})
    rid=focus.get('repair_id');pending=None
    if focus.get('proposal_id'):
        with ctx.repo.transaction() as db:
            p=ctx.repo.get(db,'living_proposal',focus['proposal_id'])
        if p and p['case_id']==case_id:
            rid=p.get('result_repair_id') or p.get('values',{}).get('repair_id') or rid
            if p['status']=='pending' and p['kind'] in ('repair','repair_update'):pending=p
    if rid and not any(r['repair_id']==rid for r in record['repairs']):rid=None
    return {'repair_id':rid,'pending':pending}


def focus_context(focus):
    pending=focus.get('pending')
    return {'focused_repair_id':focus.get('repair_id'),
        'pending_repair':({'kind':pending['kind'],'values':deepcopy(pending['values'])} if pending else None)}


def propose_update(ctx, intent, case_id, record, focus, user_message):
    answer={'content':'请先说明要更新哪一条报修；可以说出问题名称，或从报修卡片继续聊。', 'actions':[]}
    requested=intent.get('repair_id')
    named=[r for r in record['repairs'] if r['repair_id'] in user_message or r['title'] in user_message]
    rid=focus.get('repair_id')
    if len(named)==1 and requested and requested!=named[0]['repair_id']:
        return answer
    if requested:
        target=next((r for r in record['repairs'] if r['repair_id']==requested),None)
        # A model-selected ID is accepted only when grounded in the user's words
        # or equal to the already focused issue, never merely because it exists.
        if not target or (requested!=rid and target not in named):return answer
        rid=requested
    elif len(named)==1:rid=named[0]['repair_id']
    elif len(named)>1:return answer
    pending=focus.get('pending')
    patch=deepcopy(intent.get('repair_update',{}))
    service=LivingService(ctx)
    if rid:
        values={}
        if pending and pending['kind']=='repair_update' and pending['values'].get('repair_id')==rid:
            values=deepcopy(pending['values'])
        values.update(patch,repair_id=rid)
        if 'status' in patch or not patch:values['note']=user_message
        if set(values)=={'repair_id'}:return answer
        proposal=service.prepare_proposal(case_id,'repair_update',values,user_message)
        content='已整理这条报修的更新。确认后修改原记录，保留之前的问题描述；邮件不会发送。'
    elif pending and pending['kind']=='repair' and not requested:
        # A rewrite of an unconfirmed draft remains an unconfirmed draft.
        if set(patch)!={'email_tone'}:
            answer['content']='这条报修还没有确认保存。请先确认报修草稿，再记录联系结果或处理状态。'
            return answer
        values={**pending['values'],**patch}
        proposal=service.prepare_proposal(case_id,'repair',values,user_message)
        content='已调整这封待确认报修草稿的语气，原来的问题描述保持不变。确认后只保存一条报修。'
    else:return answer
    return {'content':content,'actions':[{'type':'apply_living_services','label':'确认更新这条报修',
        'proposal_id':proposal['proposal_id'],'expected_version':proposal['expected_version'],'summary':proposal['summary']}],
        '_living_focus':{'proposal_id':proposal['proposal_id'],**({'repair_id':rid} if rid else {})},
        '_supersede_living_proposal':pending['proposal_id'] if pending else None}
