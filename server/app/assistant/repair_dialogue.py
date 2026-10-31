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
        'pending_repair':({'kind':pending['kind'],'values':{k:deepcopy(v) for k,v in pending['values'].items()
            if k in ('repair_id','title','description','location','priority','status','email_tone','email_language')}} if pending else None)}


def propose_update(ctx, intent, case_id, record, focus, user_message):
    answer={'content':'Specify which repair to update. Name the issue or continue from its repair card.', 'actions':[]}
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
    draft_values=None;call=None;recipient=''
    if rid:
        target=next((r for r in record['repairs'] if r['repair_id']==rid),None)
        if target is None:return answer
        values={}
        if pending and pending['kind']=='repair_update' and pending['values'].get('repair_id')==rid:
            values=deepcopy(pending['values'])
        values.update(patch,repair_id=rid)
        if 'email_tone' in patch or 'email_language' in patch:
            from .repair_drafts import generate_draft
            draft_values,call=generate_draft(ctx,case_id,{**{k:target[k] for k in ('title','description','location','priority')},
                **{k:values[k] for k in ('email_tone','email_language') if k in values}},record,user_message,
                previous={**target,**values})
            values.update({key:draft_values[key] for key in ('email_tone','email_language','email_draft')})
            recipient=target['email']['to']
        if 'status' in patch or not patch:values['note']=user_message
        if set(values)=={'repair_id'}:return answer
        proposal=service.prepare_proposal(case_id,'repair_update',values,user_message)
        content='The repair update is ready. Confirm to update the existing record and retain the original issue description. The email will not be sent.'
    elif pending and pending['kind']=='repair' and not requested:
        # A rewrite of an unconfirmed draft remains an unconfirmed draft.
        if not patch or set(patch)-{'email_tone','email_language'}:
            answer['content']='This repair has not been confirmed and saved. Confirm the draft before recording contact results or status.'
            return answer
        values={**pending['values'],**patch}
        from .repair_drafts import generate_draft
        values,call=generate_draft(ctx,case_id,values,record,user_message,previous=pending['values'])
        draft_values=values;recipient=record['profile']['agent_email']
        proposal=service.prepare_proposal(case_id,'repair',values,user_message)
        content='The draft tone has been updated while retaining the original issue description. Confirmation saves one repair record.'
    else:return answer
    result={'content':('The requested changes are ready to copy below. Confirming the save updates the same repair record; the email will not be sent.' if draft_values else content),'actions':[{'type':'apply_living_services','label':'Save to Aftercare' if draft_values else 'Confirm repair update',
        'proposal_id':proposal['proposal_id'],'expected_version':proposal['expected_version'],'summary':proposal['summary']}],
        '_living_focus':{'proposal_id':proposal['proposal_id'],**({'repair_id':rid} if rid else {})},
        '_supersede_living_proposal':pending['proposal_id'] if pending else None}
    if draft_values:
        from .repair_drafts import preview
        result.update(repair_email=preview(draft_values,recipient,proposal,rid),_repair_call=call)
    return result
