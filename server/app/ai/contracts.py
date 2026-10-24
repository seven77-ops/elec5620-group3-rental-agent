"""Contract AI sidecar execution and explicit, version-bound candidate application."""
from pathlib import Path
from ..common import integer, request_id, require, shape
from .service import digest

FIELDS={'address','rent_amount','start_date','end_date','rent_period','rent_scope','currency'}


def analyze_saved_contract(ctx,saved,gateway):
    from contract_agent.document import load_document
    from contract_agent.ai_analysis import analyze_contract
    directory=(ctx.repo.directory/'uploads').resolve()
    path=(directory/saved['file_ref']).resolve()
    require(path.parent==directory and path.is_file(),404,'document_missing','保存的合同不可用，请重新提交。')
    document=load_document(path,consent=True,max_pdf_pages=30 if saved.get('real_context') else 10)
    require(document['sha256']==saved['review']['document']['sha256'],409,'document_changed','保存的合同内容已变化，请重新提交。')
    document['source_name']=saved['review']['document']['source_name']
    return analyze_contract(document,saved['review'],gateway)


def apply_candidates(service,review_id,analysis_id,body):
    shape(body,('request_id','expected_version','confirmed','fields'))
    require(body['confirmed'] is True,403,'confirmation_required','请先核对原文并明确确认应用所选字段。')
    require(integer(body['expected_version']),422,'invalid_input','复核版本必须是整数。')
    chosen=body['fields']
    require(isinstance(chosen,list) and 0<len(chosen)<=len(FIELDS) and all(isinstance(x,str) for x in chosen)
            and len(chosen)==len(set(chosen)) and set(chosen)<=FIELDS,422,'invalid_input','请选择不重复的允许字段。')
    key=review_id+':'+request_id(body['request_id'])
    ctx=service.ctx
    from contract_agent.review import correct_review
    with ctx.repo.transaction() as db:
        binding,saved=service.contract_source(db,review_id)
        old=ctx.receipt(db,'ai_apply_receipt',key,{'analysis_id':analysis_id,**body})
        if old:
            return old['result']
        analysis=ctx.get(db,'ai_analysis',analysis_id)
        require(analysis['kind']=='contract' and analysis['binding']==binding
                and saved['review']['version']==body['expected_version'],409,'ai_context_changed','AI 候选对应的复核已变化，请重新分析当前版本。')
        require(analysis['status'] in {'success','partial'},409,'ai_not_applicable','该 AI 分析没有可应用结果。')
        candidates={c['field']:c['value'] for c in analysis['result']['candidates'] if c['valid'] and c['value'] is not None and c['field'] in FIELDS}
        require(set(chosen)<=set(candidates),422,'invalid_candidates','所选字段没有通过原文和类型校验。')
        review=correct_review(saved['review'],{field:candidates[field] for field in chosen})
        service.contracts.save_review(db,saved,review)
        result={'review':review,'analysis_id':analysis_id}
        ctx.save_receipt(db,'ai_apply_receipt',key,{'analysis_id':analysis_id,**body},result)
        return result
