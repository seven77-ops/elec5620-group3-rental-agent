"""Repair email formatting and reviewed updates; no delivery or generated facts."""
from ..common import now, require, uid
from .fields import repair_values, status_values

STATUS_LABELS={'prepared':'草稿待联系','contacted':'已联系（用户记录）','resolved':'已解决（用户记录）'}
TONE_LABELS={'standard':'标准','polite':'礼貌','concise':'简洁'}


def styled_email(body, tone):
    # Change only the known opening/closing, preserving the entire saved body,
    # including multiline user descriptions, address and recipient snapshot.
    openings={'standard':'请协助安排以下维修：','polite':'打扰您了，想麻烦您协助查看并安排以下维修：',
              'concise':'请安排以下维修：'}
    endings={'standard':'请告知后续处理安排，谢谢。','polite':'方便时烦请告知处理安排或需要我补充的信息，非常感谢您的帮助。',
             'concise':'请回复处理安排，谢谢。'}
    for value in openings.values():
        marker='\n\n'+value+'\n'
        if marker in body:
            body=body.replace(marker,'\n\n'+openings[tone]+'\n',1)
            break
    for value in endings.values():
        suffix='\n\n'+value
        if body.endswith(suffix):
            body=body[:-len(suffix)]+'\n\n'+endings[tone]
            break
    return body


def add_repair(record, values):
    values=repair_values(values);profile=record['profile']
    body=[f"您好{('，'+profile['agent_name']) if profile['agent_name'] else ''}：",'', '请协助安排以下维修：']
    if profile['address']:body.append('地址：'+profile['address'])
    body.extend(['维修事项：'+values['title'],'位置：'+(values['location'] or '待补充'),
        '情况描述：'+values['description'],'优先级：'+('紧急' if values['priority']=='urgent' else '普通'),
        '', '请告知后续处理安排，谢谢。'])
    tone=values.get('email_tone','standard')
    entry={**values,'email_tone':tone,'repair_id':uid('repair'),'status':'prepared','created_at':now(),'updates':[],
        'email':{'to':profile['agent_email'],'subject':'维修申请：'+values['title'],
            'body':styled_email('\n'.join(body),tone),'delivery_status':'prepared_not_sent'}}
    record['repairs'].append(entry)
    return entry['repair_id']


def update_repair(record, repair_id, values):
    values=status_values(values)
    entry=next((r for r in record['repairs'] if r['repair_id']==repair_id),None)
    require(entry is not None,404,'not_found','未找到此案例的维修记录。')
    updates=entry.setdefault('updates',[])
    require(len(updates)<100,409,'repair_update_limit','此报修的更新已达上限，请保留现有记录。')
    if 'status' in values:entry['status']=values['status']
    if 'email_tone' in values:
        entry['email_tone']=values['email_tone']
        entry['email']['body']=styled_email(entry['email']['body'],values['email_tone'])
    entry['updated_at']=now()
    updates.append({'at':entry['updated_at'],'note':values.get('note',''), 'status':entry['status'],
                    **({'email_tone':values['email_tone']} if 'email_tone' in values else {})})
    return entry
