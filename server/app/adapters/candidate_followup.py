"""User-recorded candidate facts, isolated from immutable advertisement snapshots."""
from copy import deepcopy
from datetime import date
from hashlib import sha256
import math
from fastapi.responses import Response
from ..common import require, shape, integer, request_id, now
from ..repository import canonical

DEFAULT_FACTS = {'stage':'research', 'availability':'unknown', 'rent_amount':None,
    'rent_period':'unknown', 'rent_scope':'unknown', 'bills':'unknown',
    'bond':None, 'start_date':None, 'end_date':None, 'landlord':'',
    'viewing_note':'', 'source_note':'', 'notes':''}
ENUMS = {'stage':{'research','viewing','application'}, 'availability':{'unknown','available','unavailable'},
    'rent_period':{'unknown','week','fortnight','month'},
    'rent_scope':{'unknown','per_person','per_room','whole_property'},
    'bills':{'unknown','included','excluded'}}
PERIODS = {'unknown':'待确认','week':'周','fortnight':'两周','month':'月'}
SCOPES = {'unknown':'待确认','whole_property':'整套','per_room':'每间','per_person':'每人'}


def selection_signature(selection):
    return sha256(canonical(selection).encode()).hexdigest()


def followup_value(ctx, db, case):
    selection = case.get('selection')
    require(selection and selection.get('data_mode')=='real_listings',409,'selection_required','请先保存一套真实房源候选。')
    signature = selection_signature(selection)
    value = ctx.repo.get(db,'candidate_followup',case['case_id']+':'+signature)
    return value or {'case_id':case['case_id'], 'listing_id':selection['listing_id'],
        'selection_signature':signature,'version':0,'facts':deepcopy(DEFAULT_FACTS),
        'provenance':'user_recorded','updated_at':None}


def validate_facts(facts):
    shape(facts,tuple(DEFAULT_FACTS))
    for key,values in ENUMS.items():
        require(isinstance(facts[key],str) and facts[key] in values,422,'invalid_facts','请使用有效的跟进状态和计价单位。')
    for key in ('rent_amount','bond'):
        v=facts[key]
        require(v is None or (type(v) in (int,float) and math.isfinite(v) and 0<v<1000000),
                422,'invalid_facts','租金和押金须为正数，未知时留空。')
    for key in ('start_date','end_date'):
        v=facts[key]
        if v is not None:
            require(isinstance(v,str),422,'invalid_facts','日期须为 YYYY-MM-DD。')
            try: valid=date.fromisoformat(v).isoformat()==v
            except ValueError: valid=False
            require(valid,422,'invalid_facts','日期须为 YYYY-MM-DD。')
    require(not(facts['start_date'] and facts['end_date']) or facts['end_date']>facts['start_date'],
            422,'invalid_facts','结束日期须晚于起租日期。')
    for key,limit in (('landlord',200),('viewing_note',500),('source_note',500),('notes',2000)):
        require(isinstance(facts[key],str) and len(facts[key])<=limit,422,'invalid_facts','文字内容超过允许长度。')
    require(bool(facts['source_note'].strip()),422,'source_required','请记录信息来源，例如中介邮件、看房记录或本人备注。')
    return {k:v.strip() if isinstance(v,str) else v for k,v in facts.items()}


def enquiry_questions(selection, facts):
    address=selection['listing_snapshot']['address']
    return [f'请问 {address} 目前是否仍可租，何时可以看房？',
        '请确认实际租金金额、付款周期，以及是整套、每间还是每人计价。',
        '租金包含哪些账单？还有哪些固定费用？',
        '最早起租日期、租期和押金金额分别是多少？',
        '广告中的卧室、浴室和车位是否均包含在本次出租范围内？',
        '申请需要哪些材料？能否提供拟签合同及出租方或代理信息供核对？']


class CandidateFollowupAdapter:
    def __init__(self,ctx): self.ctx=ctx

    def read(self,case_id: str):
        with self.ctx.repo.transaction() as db:
            return followup_value(self.ctx,db,self.ctx.get(db,'case',case_id))

    def save(self,case_id: str,body: dict):
        shape(body,('request_id','expected_version','selection_signature','confirmed','facts'))
        key=case_id+':'+request_id(body['request_id'])
        require(body['confirmed'] is True,403,'confirmation_required','请确认保存这些跟进信息。')
        require(integer(body['expected_version']),422,'invalid_input','请提供当前跟进版本。')
        facts=validate_facts(body['facts'])
        with self.ctx.repo.transaction() as db:
            case=self.ctx.get(db,'case',case_id)
            self.ctx.contract_selection(case)
            current=followup_value(self.ctx,db,case)
            require(body['selection_signature']==current['selection_signature'],409,'stale_selection','候选已变化，请重新打开当前房源跟进。')
            old=self.ctx.receipt(db,'candidate_followup_receipt',key,body)
            if old: return old['result']
            require(current['version']==body['expected_version'],409,'version_conflict','跟进记录已更新，请重新读取后保存。')
            value={**current,'facts':facts,'version':current['version']+1,'updated_at':now()}
            identifier=case_id+':'+current['selection_signature']
            self.ctx.repo.put(db,'candidate_followup',identifier,value)
            self.ctx.repo.put(db,'candidate_followup_version',identifier+':'+str(value['version']),value)
            self.ctx.save_receipt(db,'candidate_followup_receipt',key,body,value)
            return value

    def questions(self,case_id: str):
        with self.ctx.repo.transaction() as db:
            case=self.ctx.get(db,'case',case_id)
            value=followup_value(self.ctx,db,case)
            selection=case['selection']; facts=value['facts']
            lines=['# 看房与询问清单','',selection['listing_snapshot']['address'],
                '原广告：'+selection['listing_snapshot']['source_url'],'',
                '以下为待询问事项；保存候选不代表已联系、申请或核实。','']
            lines += [f'{i}. {q}' for i,q in enumerate(enquiry_questions(selection,facts),1)]
            if value['version']:
                lines+=['','## 用户记录（未经平台独立核实）','信息来源：'+facts['source_note'],
                    f"租金：{facts['rent_amount'] if facts['rent_amount'] is not None else '待确认'} AUD / {PERIODS[facts['rent_period']]} / {SCOPES[facts['rent_scope']]}",
                    '看房安排：'+(facts['viewing_note'] or '待安排'),'备注：'+(facts['notes'] or '无')]
            return Response('\n'.join(lines)+'\n',media_type='text/markdown',
                headers={'Content-Disposition':'attachment; filename="rental-enquiries.md"'})
