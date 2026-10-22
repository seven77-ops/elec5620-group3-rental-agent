"""Grounded optional AI suggestions; no template text or saved draft is changed."""
from copy import deepcopy
from decimal import Decimal
import re
from time import time
from ..common import require, shape, request_id, uid, now
from ..ai.provider import ProviderError
from .fields import DEFAULTS, ENUMS, validate_fields, questions, extraction_schema

PERIOD_WORDS={'week':r'每周|一周|周租|weekly|per week', 'fortnight':r'两周|二周|fortnight', 'month':r'每月|月租|monthly|per month'}


def grounded_patch(response,message):
    require(isinstance(response,dict) and set(response)=={'fields'} and isinstance(response['fields'],list)
            and len(response['fields'])<=len(DEFAULTS),502,'ai_invalid_response','AI 提取格式无效，请重试。')
    patch={}
    for item in response['fields']:
        require(isinstance(item,dict) and set(item)=={'field','value','quote'},502,'ai_invalid_response','AI 字段格式无效。')
        key=item['field'];value=item['value'];quote=item['quote']
        require(isinstance(key,str) and key in DEFAULTS and key not in patch and
                isinstance(quote,str) and 0<len(quote)<=500 and quote in message,
                502,'ai_ungrounded','AI 提取缺少有效的用户原文。')
        if value is None:continue
        if key in ('rent_amount','bond','max_occupants'):
            amounts=re.findall(r'(?<![\d.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\d.])',quote)
            valid=type(value) in (int,float) and any(Decimal(v.replace(',',''))==Decimal(str(value)) for v in amounts)
        elif key=='rent_period':valid=isinstance(value,str) and value in PERIOD_WORDS and re.search(PERIOD_WORDS[value],quote,re.I)
        elif key=='rental_mode':valid=value=='whole_property' and re.search(r'整租|整套|whole property|entire property',quote,re.I)
        elif key=='lease_type':valid=value in ('fixed','periodic') and re.search(r'固定|fixed|定期' if value=='fixed' else r'持续|不定期|periodic|无结束日期',quote,re.I)
        elif key=='payment_method':
            valid=value in ('bank_transfer','centrepay','other') and re.search({'bank_transfer':r'转账|bank transfer|direct debit|BPAY','centrepay':r'centrepay','other':r'其他|other'}[value],quote,re.I)
        else:valid=isinstance(value,str) and value!='' and value in quote
        require(bool(valid),502,'ai_ungrounded','AI 候选值未通过原文核对，请修改描述后重试。')
        patch[key]=value
    if patch.get('lease_type')=='periodic':
        patch['end_date']=None
    try:validate_fields({**DEFAULTS,**patch})
    except Exception as exc:
        from ..common import ApiError
        if isinstance(exc,ApiError):require(False,502,'ai_invalid_response','AI 候选值未通过字段校验。')
        raise
    return patch


class LeaseDraftAI:
    def __init__(self,service):self.service=service;self.ctx=service.ctx

    def propose(self,case_id: str,body: dict):
        shape(body,('request_id','context_token','message','current_fields','allow_external_ai'))
        key=case_id+':'+request_id(body['request_id'])
        require(body['allow_external_ai'] is True,422,'ai_consent_required','请同意将本段文字发送至配置的外部 AI。')
        require(isinstance(body['message'],str) and 0<len(body['message'].strip())<=3000,422,'invalid_input','描述须为1至3000字。')
        current=validate_fields(body['current_fields']);attempt=uid('attempt')
        with self.ctx.repo.transaction() as db:
            _,token=self.service.source(db,case_id)
            require(token==body['context_token'],409,'draft_context_changed','房源或跟进信息已变化，请重新读取。')
            old=self.ctx.receipt(db,'lease_ai_receipt',key,body)
            if old and 'result' in old:return old['result']
            require(not old or old.get('status')!='pending' or time()-old['started_at']>60,409,'request_in_progress','这次提取仍在处理中，请稍后重试。')
            self.ctx.repo.put(db,'lease_ai_receipt',key,{'input':body,'attempt':attempt,'started_at':time(),'status':'pending'})
        try:
            output,meta=self.ctx.ai_provider.call({'task':'lease_draft_extract','message':body['message'],
                'response_schema':extraction_schema()})
            patch=grounded_patch(output,body['message'])
            combined=validate_fields({**current,**patch})
            result={'patch':patch,'questions':questions(combined),
                'call':{k:v for k,v in meta.items() if k in {'task','provider','model','status','attempted','duration_ms','simulated'}},
                'created_at':now()}
            with self.ctx.repo.transaction() as db:
                _,current_token=self.service.source(db,case_id)
                record=self.ctx.repo.get(db,'lease_ai_receipt',key)
                require(current_token==token and record['attempt']==attempt,409,'draft_context_changed','AI 提取期间房源或跟进已变化，请重新读取。')
                self.ctx.save_receipt(db,'lease_ai_receipt',key,body,result)
            return result
        except BaseException as exc:
            with self.ctx.repo.transaction() as db:
                saved=self.ctx.repo.get(db,'lease_ai_receipt',key)
                if saved and saved.get('attempt')==attempt:
                    saved['status']='failed';self.ctx.repo.put(db,'lease_ai_receipt',key,saved)
            if isinstance(exc,ProviderError):
                require(False,503,'ai_unavailable','AI 暂时不可用，可以手动填写或稍后重试。')
            raise
