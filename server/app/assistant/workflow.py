"""A maximum of three typed, read-only catalogue operations per assistant turn."""
from .comparison import prepare_enquiry, verification_checklist

LABELS={'search':'Filter listings','compare':'Compare listings','explain':'Explain listing','prepare_enquiry':'Prepare enquiry draft'}


def execute_workflow(intent,case,conversation,catalog,requested_ids,ctx=None):
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
                detail='Select two displayed listings to compare.' if kind=='compare' else ('Select one listing explicitly, or compare first and choose the one with lower advertised weekly rent.' if kind=='prepare_enquiry' else 'Select a displayed listing to explain.')
                outcomes.append({'label':LABELS[kind],'status':'needs_input','detail':detail}); content.append(detail)
                previous=[]
                continue
        if kind=='prepare_enquiry':
            row=catalog.get(ids[0]); extras['enquiry']=prepare_enquiry(row)
            rows=[row]; detail='The enquiry draft is ready. Review it, then copy and send it yourself.'
        else:
            result=execute({'intent':kind,**({'filters':step.get('filters',{})} if kind=='search' else {'listing_ids':ids})},case,memory,catalog,[],ctx=ctx)
            rows=result['listings']; detail=result['content']
            if '_search_filters' in result:
                extras['_search_filters']=result['_search_filters']; memory={**memory,'last_search_filters':result['_search_filters'],'dialogue_mode':'search'}
            if 'comparison' in result: extras['comparison']=result['comparison']
        previous=[r['listing_id'] for r in rows]
        combined.update({r['listing_id']:r for r in rows})
        outcomes.append({'label':LABELS[kind],'status':'completed','detail':detail}); content.append(detail)
    return {'intent':'workflow','agent':'agent2','content':'\n'.join(content),'listings':list(combined.values()),'actions':[],
        'task_steps':outcomes,'verification_checklist':verification_checklist(),**extras}
