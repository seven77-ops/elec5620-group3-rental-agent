"""Grounded optional AI suggestions; no template text or saved draft is changed."""
from copy import deepcopy
from decimal import Decimal
import re
from time import time
from ..common import require, shape, request_id, uid, now
from ..ai.provider import ProviderError
from .fields import DEFAULTS, ENUMS, validate_fields, questions, extraction_schema, add_months, TERM_MONTHS, MANUAL_CHOICE_FIELDS

PERIOD_WORDS={'week':r'每周|一周|周租|weekly|per week', 'fortnight':r'两周|二周|fortnight', 'month':r'每月|月租|monthly|per month'}


DURATION_WORDS={6:r'半\s*年|六\s*个\s*月',12:r'一\s*年|十二\s*个\s*月',
    24:r'(?:两|二)\s*年|二十四\s*个\s*月',36:r'三\s*年|三十六\s*个\s*月',60:r'五\s*年|六十\s*个\s*月'}


DURATION_NUMBER=r'(?:[零〇一二两三四五六七八九十百]+|[0-9]+)'
CHINESE_COMPOUND=r'(?:'+DURATION_NUMBER+r'|半)\s*年\s*(?:(?:又|和|加(?:上)?|零)\s*)?(?:半(?:\s*年)?|'+DURATION_NUMBER+r'\s*(?:个\s*)?月)'
ENGLISH_NUMBER=r'(?:[0-9]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a|an)'
ENGLISH_COMPOUND=r'(?<![A-Za-z0-9])'+ENGLISH_NUMBER+r'\s*years?\s*(?:,\s*)?(?:(?:and|plus|\+)\s*)?(?:(?:a\s+)?half(?:\s*years?)?|'+ENGLISH_NUMBER+r'\s*months?)(?![A-Za-z])'
COMPOUND_DURATION=re.compile('(?:'+CHINESE_COMPOUND+')|(?:'+ENGLISH_COMPOUND+')',re.I)
DURATION_END=r'(?!\s*(?:半|多|余|餘))'


def duration_grounded(value,quote,message=None):
    if type(value) is not int or value not in TERM_MONTHS:return False
    # An unsupported compound duration is never a shorter calendar preset, even
    # when the model quotes only its year prefix or its trailing month component.
    if COMPOUND_DURATION.search(quote):return False
    if message is not None:
        compounds=[match.span() for match in COMPOUND_DURATION.finditer(message)]
        occurrences=list(re.finditer(re.escape(quote),message))
        if not any(not any(start<match.end() and match.start()<end for start,end in compounds)
                   for match in occurrences):return False
    patterns=[r'(?<![\d.])'+str(value)+r'\s*(?:个\s*月|months?)(?![a-z])',
        r'(?<![零一二两三四五六七八九十百\d])(?:'+DURATION_WORDS[value]+r')']
    if value%12==0:patterns.append(r'(?<![\d.])'+str(value//12)+r'\s*(?:年|years?)(?![a-z])')
    return any(re.search('(?:'+pattern+')'+DURATION_END,quote,re.I) for pattern in patterns)


def calendar_patch(patch,current):
    """Derive dates from grounded changes; changing an explicit end means custom dates."""
    patch=dict(patch)
    if patch.get('lease_type')=='periodic':
        require(patch.get('lease_term_months') is None and patch.get('end_date') is None,
            502,'ai_invalid_response','持续租约与固定租期或结束日期冲突。')
        patch.update(lease_term_months=None,end_date=None)
    elif 'end_date' in patch and 'lease_term_months' not in patch:
        patch.update(lease_term_months=None,lease_type='fixed')
    elif 'start_date' in patch or 'lease_term_months' in patch:
        merged={**current,**patch};months=merged['lease_term_months']
        if months is not None:
            patch['lease_term_months']=months
            derived=add_months(merged['start_date'],months) if merged['start_date'] else None
            require('end_date' not in patch or patch['end_date']==derived,
                502,'ai_invalid_response','AI 提取的结束日期与日历租期不一致。')
            patch['end_date']=derived
    return patch


def grounded_patch(response,message):
    require(isinstance(response,dict) and set(response)=={'fields'} and isinstance(response['fields'],list)
            and len(response['fields'])<=len(DEFAULTS),502,'ai_invalid_response','AI 提取格式无效，请重试。')
    patch={}
    for item in response['fields']:
        require(isinstance(item,dict) and set(item)=={'field','value','quote'},502,'ai_invalid_response','AI 字段格式无效。')
        key=item['field'];value=item['value'];quote=item['quote']
        require(key not in MANUAL_CHOICE_FIELDS,502,'ai_invalid_response','费用、设施及电子送达选择请在表单中明确确认。')
        require(isinstance(key,str) and key in DEFAULTS and key not in patch and
                isinstance(quote,str) and 0<len(quote)<=500 and quote in message,
                502,'ai_ungrounded','AI 提取缺少有效的用户原文。')
        if value is None:continue
        # Some compatible providers return the tenant list despite the requested
        # newline string. Normalize only literal, bounded names for this one field.
        if key=='tenant_names' and isinstance(value,list):
            require(1<=len(value)<=6 and all(isinstance(name,str) and 0<len(name.strip())<=80 and
                '\n' not in name and '\r' not in name and name in quote for name in value),
                502,'ai_ungrounded','AI 租客姓名数组缺少有效的用户原文或超出人数范围。')
            value='\n'.join(name.strip() for name in value)
            valid=True
        elif key in ('rent_amount','bond','max_occupants'):
            amounts=re.findall(r'(?<![\d.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\d.])',quote)
            valid=type(value) in (int,float) and any(Decimal(v.replace(',',''))==Decimal(str(value)) for v in amounts)
        elif key=='postcode' or key.endswith('_postcode'):
            postal_prefix=r'(?:邮编|郵編|邮政编码|郵政編碼|postcode|postal\s+code)[\s:：=-]*(?:(?:是|为|為|is)\s*)?'
            state_prefix=r'(?<![A-Za-z0-9])(?:NSW|ACT|VIC|QLD|TAS|NT|SA|WA)\s*'
            valid=isinstance(value,str) and bool(re.fullmatch(r'[0-9]{4}',value)) and bool(
                re.search(postal_prefix+re.escape(value)+r'(?![0-9])',quote,re.I) or
                re.search(state_prefix+re.escape(value)+r'(?![0-9])',quote,re.I))
        elif key=='lease_term_months':valid=duration_grounded(value,quote,message)
        elif key=='rent_period':valid=isinstance(value,str) and value in PERIOD_WORDS and re.search(PERIOD_WORDS[value],quote,re.I)
        elif key=='rental_mode':valid=value=='whole_property' and re.search(r'整租|整套|whole property|entire property',quote,re.I)
        elif key=='lease_type':valid=isinstance(value,str) and value in ('fixed','periodic') and (re.search(r'固定|fixed|(?<!不)定期' if value=='fixed' else r'持续|不定期|periodic|无结束日期',quote,re.I) or (value=='fixed' and any(duration_grounded(months,quote,message) for months in TERM_MONTHS)))
        elif key=='payment_method':
            valid=value in ('bank_transfer','centrepay','other') and re.search({'bank_transfer':r'转账|bank transfer|direct debit|BPAY','centrepay':r'centrepay','other':r'其他|other'}[value],quote,re.I)
        else:valid=isinstance(value,str) and value!='' and value in quote
        require(bool(valid),502,'ai_ungrounded','AI 候选值未通过原文核对，请修改描述后重试。')
        patch[key]=value
    if patch.get('lease_term_months') is not None:
        require(patch.get('lease_type')!='periodic',502,'ai_invalid_response','持续租约不能同时设置固定日历租期。')
        patch.setdefault('lease_type','fixed')
    if patch.get('lease_type')=='periodic':
        require(patch.get('end_date') is None,502,'ai_invalid_response','持续租约不能同时设置结束日期。')
        patch.update(end_date=None,lease_term_months=None)
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
            patch=calendar_patch(grounded_patch(output,body['message']),current)
            try:combined=validate_fields({**current,**patch})
            except Exception as exc:
                from ..common import ApiError
                if isinstance(exc,ApiError):require(False,502,'ai_invalid_response','AI 候选值与当前租约字段冲突。')
                raise
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
