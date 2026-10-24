"""A maximum of three typed, read-only catalogue operations per assistant turn."""
from .comparison import prepare_enquiry, verification_checklist

LABELS={'search':'筛选房源','compare':'比较房源','explain':'解释房源','prepare_enquiry':'准备询问信草稿'}


def execute_workflow(intent,case,conversation,catalog,requested_ids):
    from .tools import execute, reference_listings, listing_context
    previous=list(requested_ids) or [r['listing_id'] for r in listing_context(catalog,[r['listing_id'] for r in reference_listings(conversation)])]
    combined={}; outcomes=[]; content=[]; extras={}; memory=dict(conversation)
    for step in intent['steps']:
        kind=step['kind']; ids=[]
        if kind!='search':
            ref=step.get('reference')
            if ref=='selected': ids=list(requested_ids)
            elif ref in ('previous','cheapest'):
                ids=list(previous)
                if ref=='cheapest' and ids: ids=[min((catalog.get(i) for i in ids),key=lambda r:r['weekly_rent'])['listing_id']]
            elif requested_ids: ids=list(requested_ids)
            else: ids=step.get('listing_ids',[])
            count=len(ids)
            if not count or (kind=='compare' and count<2) or (kind=='prepare_enquiry' and count!=1):
                detail='请选择两套已展示房源进行比较。' if kind=='compare' else ('请明确选择一套房源，或先比较再指定标示周租较低的一套。' if kind=='prepare_enquiry' else '请选择要解释的已展示房源。')
                outcomes.append({'label':LABELS[kind],'status':'needs_input','detail':detail}); content.append(detail)
                previous=[]
                continue
        if kind=='prepare_enquiry':
            row=catalog.get(ids[0]); extras['enquiry']=prepare_enquiry(row)
            rows=[row]; detail='已准备询问信草稿，请核对后自行复制发送。'
        else:
            result=execute({'intent':kind,**({'filters':step.get('filters',{})} if kind=='search' else {'listing_ids':ids})},case,memory,catalog,[])
            rows=result['listings']; detail=result['content']
            if '_search_filters' in result:
                extras['_search_filters']=result['_search_filters']; memory={**memory,'last_search_filters':result['_search_filters'],'dialogue_mode':'search'}
            if 'comparison' in result: extras['comparison']=result['comparison']
        previous=[r['listing_id'] for r in rows]
        combined.update({r['listing_id']:r for r in rows})
        outcomes.append({'label':LABELS[kind],'status':'completed','detail':detail}); content.append(detail)
    return {'intent':'workflow','agent':'agent2','content':'\n'.join(content),'listings':list(combined.values()),'actions':[],
        'task_steps':outcomes,'verification_checklist':verification_checklist(),**extras}
