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
PERIODS = {'unknown':'Unconfirmed','week':'week','fortnight':'fortnight','month':'month'}
SCOPES = {'unknown':'Unconfirmed','whole_property':'whole property','per_room':'per room','per_person':'per person'}


def selection_signature(selection):
    return sha256(canonical(selection).encode()).hexdigest()


def followup_value(ctx, db, case):
    selection = case.get('selection')
    require(selection and selection.get('data_mode')=='real_listings',409,'selection_required','Save a live listing candidate first.')
    signature = selection_signature(selection)
    value = ctx.repo.get(db,'candidate_followup',case['case_id']+':'+signature)
    return value or {'case_id':case['case_id'], 'listing_id':selection['listing_id'],
        'selection_signature':signature,'version':0,'facts':deepcopy(DEFAULT_FACTS),
        'provenance':'user_recorded','updated_at':None}


def validate_facts(facts):
    shape(facts,tuple(DEFAULT_FACTS))
    for key,values in ENUMS.items():
        require(isinstance(facts[key],str) and facts[key] in values,422,'invalid_facts','Use valid follow-up statuses and rent units.')
    for key in ('rent_amount','bond'):
        v=facts[key]
        require(v is None or (type(v) in (int,float) and math.isfinite(v) and 0<v<1000000),
                422,'invalid_facts','Rent and bond must be positive amounts; leave blank if unknown.')
    for key in ('start_date','end_date'):
        v=facts[key]
        if v is not None:
            require(isinstance(v,str),422,'invalid_facts','Dates must use YYYY-MM-DD.')
            try: valid=date.fromisoformat(v).isoformat()==v
            except ValueError: valid=False
            require(valid,422,'invalid_facts','Dates must use YYYY-MM-DD.')
    require(not(facts['start_date'] and facts['end_date']) or facts['end_date']>facts['start_date'],
            422,'invalid_facts','The end date must be after the start date.')
    for key,limit in (('landlord',200),('viewing_note',500),('source_note',500),('notes',2000)):
        require(isinstance(facts[key],str) and len(facts[key])<=limit,422,'invalid_facts','The text exceeds the permitted length.')
    require(bool(facts['source_note'].strip()),422,'source_required','Record the source, such as an agent email, inspection record or your own note.')
    return {k:v.strip() if isinstance(v,str) else v for k,v in facts.items()}


def enquiry_questions(selection, facts):
    address=selection['listing_snapshot']['address']
    return [f'Is {address} still available, and when can I inspect it?',
        'Please confirm the actual rent, payment period and whether it is for the whole property, per room or per person.',
        'Which bills are included, and what other fixed charges apply?',
        'What are the earliest start date, lease term and bond amount?',
        'Are all advertised bedrooms, bathrooms and parking spaces included in this rental?',
        'What documents are needed to apply? Can you provide the proposed agreement and landlord or agent details for review?']


class CandidateFollowupAdapter:
    def __init__(self,ctx): self.ctx=ctx

    def read(self,case_id: str):
        with self.ctx.repo.transaction() as db:
            return followup_value(self.ctx,db,self.ctx.get(db,'case',case_id))

    def save(self,case_id: str,body: dict):
        shape(body,('request_id','expected_version','selection_signature','confirmed','facts'))
        key=case_id+':'+request_id(body['request_id'])
        require(body['confirmed'] is True,403,'confirmation_required','Confirm saving these follow-up details.')
        require(integer(body['expected_version']),422,'invalid_input','Provide the current follow-up version.')
        facts=validate_facts(body['facts'])
        with self.ctx.repo.transaction() as db:
            case=self.ctx.get(db,'case',case_id)
            self.ctx.contract_selection(case)
            current=followup_value(self.ctx,db,case)
            require(body['selection_signature']==current['selection_signature'],409,'stale_selection','The candidate changed. Reopen follow-up for the current listing.')
            old=self.ctx.receipt(db,'candidate_followup_receipt',key,body)
            if old: return old['result']
            require(current['version']==body['expected_version'],409,'version_conflict','The follow-up record changed. Reload before saving.')
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
            lines=['# Inspection and enquiry checklist','',selection['listing_snapshot']['address'],
                'Original advertisement: '+selection['listing_snapshot']['source_url'],'',
                'These questions remain to be asked. Saving a candidate does not establish contact, an application or verification.','']
            lines += [f'{i}. {q}' for i,q in enumerate(enquiry_questions(selection,facts),1)]
            if value['version']:
                lines+=['','## User records (not independently verified)','Source: '+facts['source_note'],
                    f"Rent: {facts['rent_amount'] if facts['rent_amount'] is not None else 'Unconfirmed'} AUD / {PERIODS[facts['rent_period']]} / {SCOPES[facts['rent_scope']]}",
                    'Inspection arrangements: '+(facts['viewing_note'] or 'To be arranged'),'Notes: '+(facts['notes'] or 'None')]
            return Response('\n'.join(lines)+'\n',media_type='text/markdown',
                headers={'Content-Disposition':'attachment; filename="rental-enquiries.md"'})
