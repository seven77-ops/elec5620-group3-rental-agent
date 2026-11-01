"""Repair email formatting and reviewed updates; no delivery or generated facts."""
from ..common import now, require, uid
from .fields import repair_values, status_values

STATUS_LABELS={'prepared':'Draft; contact pending','contacted':'Contacted (user recorded)','resolved':'Resolved (user recorded)'}
TONE_LABELS={'standard':'Standard','polite':'Polite','concise':'Concise'}


def styled_email(body, tone):
    # Change only the known opening/closing, preserving the entire saved body,
    # including multiline user descriptions, address and recipient snapshot.
    openings={'standard':'Please help arrange the following repair:','polite':'Could you please review the issue below and help arrange a repair?',
              'concise':'Please arrange this repair:'}
    endings={'standard':'Please let me know the next steps. Thank you.','polite':'Please let me know the arrangements or any additional details you need. Thank you for your help.',
             'concise':'Please reply with the arrangements. Thank you.'}
    # Recognise historical boilerplate as input aliases; new wording remains English.
    legacy_openings=('请协助安排以下维修：','打扰您了，想麻烦您协助查看并安排以下维修：','请安排以下维修：')
    legacy_endings=('请告知后续处理安排，谢谢。','方便时烦请告知处理安排或需要我补充的信息，非常感谢您的帮助。','请回复处理安排，谢谢。')
    for value in (*openings.values(), *legacy_openings):
        marker='\n\n'+value+'\n'
        if marker in body:
            body=body.replace(marker,'\n\n'+openings[tone]+'\n',1)
            break
    for value in (*endings.values(), *legacy_endings):
        suffix='\n\n'+value
        if body.endswith(suffix):
            body=body[:-len(suffix)]+'\n\n'+endings[tone]
            break
    return body


def add_repair(record, values):
    values={**repair_values(values),'email_language':'en'};profile=record['profile']
    name=values.get('recipient_name',profile['agent_name'])
    body=[f"Hello{(', '+name) if name else ''}:",'', 'Please help arrange the following repair:']
    if profile['address']:body.append('Property: '+profile['address'])
    body.extend(['Repair: '+values['title'],'Location: '+(values['location'] or 'Not supplied'),
        'Description: '+values['description'],'Priority: '+('Urgent' if values['priority']=='urgent' else 'Normal'),
        '', 'Please let me know the next steps. Thank you.'])
    tone=values.get('email_tone','standard')
    entry={**values,'email_tone':tone,'repair_id':uid('repair'),'status':'prepared','created_at':now(),'updates':[],
        'email':{'to':profile['agent_email'],'subject':'Repair request: '+values['title'],
            'body':styled_email('\n'.join(body),tone),'delivery_status':'prepared_not_sent'}}
    if 'email_draft' in values:
        entry['email'].update(values['email_draft'])
    record['repairs'].append(entry)
    return entry['repair_id']


def update_repair(record, repair_id, values):
    values=status_values(values)
    entry=next((r for r in record['repairs'] if r['repair_id']==repair_id),None)
    require(entry is not None,404,'not_found','Repair record not found for this case.')
    require('email_tone' not in values or not entry.get('email_draft') or 'email_draft' in values,422,'custom_email_requires_polish',
            'This email uses a polished draft and cannot apply a fixed-template tone. Polish it on the repairs page.')
    updates=entry.setdefault('updates',[])
    require(len(updates)<100,409,'repair_update_limit','This repair has reached its update limit. Retain the existing records.')
    if 'status' in values:entry['status']=values['status']
    if 'email_tone' in values:
        entry['email_tone']=values['email_tone']
        if 'email_draft' not in values:
            entry['email']['body']=styled_email(entry['email']['body'],values['email_tone'])
    if 'email_language' in values:entry['email_language']=values['email_language']
    if 'email_draft' in values:
        entry['email_draft']=values['email_draft']
        entry['email'].update(values['email_draft'])
    entry['updated_at']=now()
    updates.append({'at':entry['updated_at'],'note':values.get('note',''), 'status':entry['status'],
                    **({'email_tone':values['email_tone']} if 'email_tone' in values else {})})
    return entry
