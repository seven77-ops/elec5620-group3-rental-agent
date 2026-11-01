"""Area read tools and shared, versioned evidence previews."""
from copy import deepcopy
from ..areas.evidence import AreaKnowledge, TOPICS
from ..areas.evidence import needs_review


def model_context():
    knowledge=AreaKnowledge()
    return {'supported_topics':TOPICS,'covered_suburbs':sorted({r['suburb'] for r in knowledge.records}),
            'facts':'Retrieved by server only. Opinions and missing evidence never prove property suitability.'}


def answer_areas(catalog,brief,names=None,focus='balanced'):
    from .area_answers import summarize
    report=AreaKnowledge().advice(catalog,brief,names)
    content=summarize(report,catalog,brief,focus)
    return {'intent':'area_advice','agent':'agent2','content':content,'listings':[],'actions':[],
            'area_advice':report,'_area_names':names}


def enrich_commute(answer,catalog,knowledge=None):
    report=answer.get('commute_recommendation')
    if not report:return answer
    knowledge=knowledge or AreaKnowledge()
    names=[a['suburb'] for a in report['areas']]
    context=knowledge.advice(catalog,report['criteria'],names,limit=len(names)) if names else None
    report['area_knowledge_fingerprint']=knowledge.fingerprint
    report['area_knowledge_coverage']=(context or knowledge.advice(catalog,{},[],limit=0))['coverage']
    for area,details in zip(report['areas'],context['areas'] if context else []):
        area['area_context']=details
    return answer


def latest(ctx,case_id):
    from .service import signature
    with ctx.repo.transaction() as db:
        case=ctx.get(db,'case',case_id)
        saved=ctx.repo.get(db,'assistant_area_report',case_id)
        if not saved:return None
        conversation=ctx.repo.get(db,'assistant_conversation',saved['conversation_id'])
        activity=ctx.repo.get(db,'assistant_commute_activity',case_id)
    result=deepcopy(saved); reasons=[]
    if activity and (activity['conversation_id']!=saved['conversation_id'] or activity['brief']!=saved['brief']):
        reasons.append('Suburb or commute requirements changed. Compare again in the latest conversation.')
    if not conversation or conversation.get('rental_brief')!=saved['brief']:
        reasons.append('Conversation requirements changed. Compare areas again.')
    if signature(case)!=saved['case_signature']:reasons.append('Saved requirements changed. Review the area references again.')
    if ctx.settings.catalog.fingerprint!=saved['catalog_fingerprint']:reasons.append('Listing data changed. Compare areas again.')
    if AreaKnowledge().fingerprint!=saved['area_knowledge_fingerprint']:reasons.append('Area information changed. Search again.')
    if needs_review(saved.get('message',{}).get('area_advice',{})):reasons.append('Area information is due for review. Search again.')
    result.update(stale=bool(reasons),stale_reasons=reasons)
    return result
