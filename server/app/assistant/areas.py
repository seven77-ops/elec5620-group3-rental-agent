"""Area read tools and shared, versioned evidence previews."""
from copy import deepcopy
from ..areas.evidence import AreaKnowledge, TOPICS
from ..areas.evidence import needs_review


def model_context():
    knowledge=AreaKnowledge()
    return {'supported_topics':TOPICS,'covered_suburbs':sorted({r['suburb'] for r in knowledge.records}),
            'facts':'Retrieved by server only. Opinions and missing evidence never prove property suitability.'}


def answer_areas(catalog,brief,names=None):
    report=AreaKnowledge().advice(catalog,brief,names)
    missing=not brief.get('lifestyle_priorities')
    content=('我把这些区域的资料和当前房源库存放在一起比较。'
             '下面会区分可核对的设施、背景报道和住户体验；通勤是否满足仍以具体路线为准。')
    if missing:content+=' 你更看重公园、吃饭购物方便、图书馆，还是安静？告诉我后可以进一步缩小范围。'
    if not names and not brief.get('suburb'):
        content+=' 当前仅按已整理的相关设施资料和库存标价给出初步区域参考。'
    return {'intent':'area_advice','agent':'agent2','content':content,'listings':[],'actions':[],
            'area_advice':report,'_area_names':names}


def enrich_commute(answer,catalog,knowledge=None):
    report=answer.get('commute_recommendation')
    if not report:return answer
    knowledge=knowledge or AreaKnowledge()
    names=[a['suburb'] for a in report['areas']]
    context=knowledge.advice(catalog,report['criteria'],names,limit=5) if names else None
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
        reasons.append('已有新的区域或通勤需求，请在最新对话重新比较。')
    if not conversation or conversation.get('rental_brief')!=saved['brief']:
        reasons.append('聊天需求已更新，请重新比较区域。')
    if signature(case)!=saved['case_signature']:reasons.append('已保存的需求已更新，请重新核对区域参考。')
    if ctx.settings.catalog.fingerprint!=saved['catalog_fingerprint']:reasons.append('房源数据已更新，请重新比较区域。')
    if AreaKnowledge().fingerprint!=saved['area_knowledge_fingerprint']:reasons.append('区域资料已更新，请重新检索。')
    if needs_review(saved.get('message',{}).get('area_advice',{})):reasons.append('区域资料已到重新核对时间，请重新检索。')
    result.update(stale=bool(reasons),stale_reasons=reasons)
    return result
