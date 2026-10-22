"""Durable, source-bound unsigned drafts; official review state is never mutated."""
from copy import deepcopy
from hashlib import sha256
from fastapi.responses import Response
from ..common import require, shape, integer, request_id, uid, now
from ..repository import canonical
from ..adapters.candidate_followup import followup_value
from .fields import DEFAULTS, validate_fields, questions, warnings
from .pdf import template_metadata, generate_pdf, validate_pdf_values


class LeaseDraftService:
    def __init__(self,ctx):self.ctx=ctx

    def source(self,db,case_id):
        case=self.ctx.get(db,'case',case_id)
        selection=self.ctx.contract_selection(case)
        require(selection.get('data_mode')=='real_listings',409,'real_selection_required','请先保存真实房源候选。')
        packet={'case_id':case_id,'selection':deepcopy(selection),'profile':deepcopy(self.ctx.current(case)),
                'followup':deepcopy(followup_value(self.ctx,db,case))}
        return packet,sha256(canonical(packet).encode()).hexdigest()

    def context(self,case_id: str):
        with self.ctx.repo.transaction() as db:
            packet,token=self.source(db,case_id)
        values=deepcopy(DEFAULTS);values['address']=packet['selection']['listing_snapshot']['address']
        sources={'address':'已保存候选的广告地址（待核实）'}
        followup=packet['followup'];facts=followup['facts']
        if followup['version']:
            basis='用户跟进记录 v'+str(followup['version'])+'：'+facts['source_note']
            for key,other in (('landlord_name','landlord'),('bond','bond'),('start_date','start_date'),('end_date','end_date')):
                if facts[other] not in ('',None):values[key]=facts[other];sources[key]=basis
            if facts['rent_scope']=='whole_property':
                for key in ('rent_amount','rent_period'):
                    if facts[key] not in (None,'unknown'):values[key]=facts[key];sources[key]=basis
        return {'context_token':token,'sources':packet,'defaults':values,'prefill_sources':sources,
                'questions':questions(values),'template':template_metadata()}

    def list(self,case_id: str):
        with self.ctx.repo.transaction() as db:
            self.ctx.get(db,'case',case_id)
            try:_,token=self.source(db,case_id)
            except Exception as exc:
                from ..common import ApiError
                if not isinstance(exc,ApiError):raise
                token=None
            index=self.ctx.repo.get(db,'lease_draft_index',case_id) or []
            return {'items':[{**i,'source_current':i['context_token']==token} for i in reversed(index)]}

    def save(self,case_id: str,body: dict):
        shape(body,('request_id','context_token','expected_version','confirmed','applicability_confirmed','fields'),('draft_id',))
        key=case_id+':'+request_id(body['request_id'])
        require(body['confirmed'] is True and body['applicability_confirmed'] is True,403,'confirmation_required','请核对信息并确认本次草稿适用于新州普通整租住宅。')
        require(integer(body['expected_version']),422,'invalid_input','请提供当前草稿版本。')
        fields=validate_fields(body['fields'])
        require(fields['rental_mode']=='whole_property',422,'unsupported_draft_scope','第一版仅支持新州普通整租住宅租约草稿。')
        validate_pdf_values(fields)
        with self.ctx.repo.transaction() as db:
            source,token=self.source(db,case_id)
            require(token==body['context_token'],409,'draft_context_changed','房源、需求或跟进信息已变化，请重新读取后确认。')
            old=self.ctx.receipt(db,'lease_draft_receipt',key,body)
            if old:return old['result']
            if body.get('draft_id'):
                previous=self.owned(db,case_id,body['draft_id'])
                require(previous['context_token']==token,409,'draft_context_changed','历史草稿不能直接覆盖当前房源草稿。')
                require(previous['version']==body['expected_version'],409,'version_conflict','草稿已有新版本，请重新读取。')
                identifier=previous['draft_id'];version=previous['version']+1
            else:
                require(body['expected_version']==0,409,'version_conflict','新草稿版本须从0开始。')
                identifier=uid('lease-draft');version=1
            value={'draft_id':identifier,'case_id':case_id,'version':version,'status':'draft',
                'context_token':token,'fields':fields,'sources':source,'saved_at':now(),
                'questions':questions(fields),'warnings':warnings(fields),'template':template_metadata(),
                'applicability_confirmed':True,'user_confirmed':True}
            self.ctx.repo.put(db,'lease_draft',identifier,value)
            self.ctx.repo.put(db,'lease_draft_version',identifier+':'+str(version),value)
            index=self.ctx.repo.get(db,'lease_draft_index',case_id) or []
            require(len(index)<100 or any(i['draft_id']==identifier for i in index),409,'draft_limit','当前案例最多保存100份草稿。')
            index=[i for i in index if i['draft_id']!=identifier]
            index.append({k:value[k] for k in ('draft_id','version','saved_at','context_token','status')})
            self.ctx.repo.put(db,'lease_draft_index',case_id,index)
            self.ctx.save_receipt(db,'lease_draft_receipt',key,body,value)
            return value

    def owned(self,db,case_id,draft_id):
        self.ctx.get(db,'case',case_id)
        value=self.ctx.get(db,'lease_draft',draft_id)
        require(value['case_id']==case_id,404,'not_found','未找到这份草稿。')
        return value

    def read(self,case_id: str,draft_id: str,version: int | None = None):
        with self.ctx.repo.transaction() as db:
            latest=self.owned(db,case_id,draft_id)
            if version is None:return latest
            require(version>0,422,'invalid_input','版本须为正整数。')
            return self.ctx.get(db,'lease_draft_version',draft_id+':'+str(version))

    def pdf(self,case_id: str,draft_id: str,version: int):
        draft=self.read(case_id,draft_id,version)
        return Response(generate_pdf(draft),media_type='application/pdf',headers={
            'Content-Disposition':f'attachment; filename="nsw-lease-draft-v{version}.pdf"',
            'Cache-Control':'no-store'})
