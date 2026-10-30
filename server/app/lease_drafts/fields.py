"""Explicit proposed terms for a draft, separate from advertisement facts."""
from datetime import date
from calendar import monthrange
import math
from ..common import require, shape

TEXT_LIMITS={'address':200,'landlord_name':100,'landlord_contact':160,'landlord_notice_address':200,
    'tenant_names':400,'tenant_contact':160,'tenant_notice_address':200,'agent_name':100,
    'agent_contact':160,'agent_notice_address':200,'inclusions':400,'payment_details':400,'rent_due_day':30}
ENUMS={'rental_mode':{'whole_property'},'lease_type':{'fixed','periodic'},
    'rent_period':{'week','fortnight','month'},'payment_method':{'bank_transfer','centrepay','other'}}
DEFAULTS={**{k:'' for k in TEXT_LIMITS},**{k:None for k in ENUMS},
    'start_date':None,'end_date':None,'first_rent_date':None,'rent_amount':None,'bond':None,'max_occupants':None}
LEGACY_FIELDS=tuple(DEFAULTS)
OPTIONAL_TEXT_LIMITS={'suburb':80,'state':40,'postcode':4,
    **{prefix+'_'+part:(80 if part=='suburb' else 40 if part=='state' else 4)
       for prefix in ('landlord_notice','tenant_notice','agent_notice') for part in ('suburb','state','postcode')},
    'agreement_place':100,'landlord_name_2':100,'landlord_residence':200,'landlord_phone':60,
    **{kind+'_repair_'+part:(100 if part=='name' else 60)
       for kind in ('electrical','plumbing','other') for part in ('name','phone')}}
OPTIONAL_TEXT_LIMITS.update({'tenant_agent_name':100,'tenant_agent_contact':160,'tenant_agent_notice_address':200,
    'tenant_agent_notice_suburb':80,'tenant_agent_notice_state':40,'tenant_agent_notice_postcode':4,
    'corporation_name':100,'corporation_address':200,'corporation_suburb':80,'corporation_state':40,'corporation_postcode':4,
    'smoke_battery_type':80,'smoke_backup_type':80,'landlord_notice_email':160,'tenant_notice_email':160})
YES_NO_FIELDS=('water_usage','electricity_embedded','gas_embedded','smoke_battery_replaceable',
    'smoke_backup_replaceable','smoke_strata_responsible','strata_bylaws','landlord_email_consent','tenant_email_consent')
MANUAL_CHOICE_FIELDS=(*YES_NO_FIELDS,'smoke_alarm_type','bond_recipient')
ENUMS.update({**{k:{'yes','no'} for k in YES_NO_FIELDS},'smoke_alarm_type':{'hardwired','battery','both'},
    'bond_recipient':{'landlord','agent','rbo'}})
DEFAULTS.update({k:None for k in ENUMS if k not in DEFAULTS})
DEFAULTS.update({**{k:'' for k in OPTIONAL_TEXT_LIMITS},'agreement_date':None,'lease_term_months':None})
TEXT_LIMITS.update(OPTIONAL_TEXT_LIMITS)
TERM_MONTHS=(6,12,24,36,60)
LABELS={'address':'Property address','landlord_name':'Landlord name','landlord_contact':'Landlord contact details',
    'landlord_notice_address':'Landlord notice address','tenant_names':'Tenant names','tenant_contact':'Tenant contact details',
    'tenant_notice_address':'Tenant notice address','agent_name':'Agent name','agent_contact':'Agent contact details',
    'agent_notice_address':'Agent notice address','rental_mode':'Whole-property applicability','lease_type':'Lease type',
    'start_date':'Start date','end_date':'End date','first_rent_date':'First rent payment date',
    'rent_amount':'Proposed rent','rent_period':'Rent period','bond':'Proposed bond','max_occupants':'Agreed maximum occupants',
    'inclusions':'Included facilities','payment_method':'Payment method','payment_details':'Payment details','rent_due_day':'Rent due day'}
LABELS.update({'suburb':'Suburb','state':'State','postcode':'Postcode','agreement_date':'Agreement date','agreement_place':'Agreement place',
    'landlord_name_2':'Second landlord name','landlord_residence':'Landlord residence','landlord_phone':'Landlord phone',
    'lease_term_months':'Calendar term in months',
    **{prefix+'_'+part:label+suffix for prefix,label in (('landlord_notice','Landlord notice '),('tenant_notice','Tenant notice '),('agent_notice','Agent notice '))
       for part,suffix in (('suburb','Suburb'),('state','State'),('postcode','Postcode'))},
    **{kind+'_repair_'+part:label+suffix for kind,label in (('electrical','Electrical repair '),('plumbing','Plumbing repair '),('other','Other repair '))
       for part,suffix in (('name','Contact name'),('phone','Phone'))}})
LABELS.update({'agent_name':'Landlord agent name / company','agent_contact':'Landlord agent contact details (phone required)',
    'agent_notice_address':'Landlord agent notice address','tenant_agent_name':'Tenant representative name / company','tenant_agent_contact':'Tenant representative contact details',
    'tenant_agent_notice_address':'Tenant representative notice address','tenant_agent_notice_suburb':'Tenant representative suburb',
    'tenant_agent_notice_state':'Tenant representative state','tenant_agent_notice_postcode':'Tenant representative postcode',
    'corporation_name':'Landlord company registered name','corporation_address':'Landlord company business address','corporation_suburb':'Landlord company suburb',
    'corporation_state':'Landlord company state','corporation_postcode':'Landlord company postcode',
    'water_usage':'Water usage payable separately','electricity_embedded':'Embedded electricity network','gas_embedded':'Embedded gas network',
    'smoke_alarm_type':'Smoke alarm type','smoke_battery_replaceable':'Smoke alarm battery replaceable by tenant',
    'smoke_battery_type':'Smoke alarm battery type','smoke_backup_replaceable':'Backup battery replaceable by tenant',
    'smoke_backup_type':'Backup battery type','smoke_strata_responsible':'Owners corporation responsible for smoke alarm repairs and replacement',
    'strata_bylaws':'Strata / community bylaws apply','landlord_email_consent':'Landlord electronic service consent',
    'tenant_email_consent':'Tenant electronic service consent','landlord_notice_email':'Landlord electronic service email',
    'tenant_notice_email':'Tenant electronic service email','bond_recipient':'Bond recipient'})
REQUIRED=('rental_mode','address','landlord_name','landlord_contact','landlord_notice_address',
    'tenant_names','tenant_contact','lease_type','start_date','rent_amount','rent_period','bond')
REQUIRED=tuple(k for k in REQUIRED if k!='landlord_notice_address')+('tenant_notice_address','max_occupants',
    'payment_method','payment_details','first_rent_date','rent_due_day','water_usage','electricity_embedded','gas_embedded',
    'smoke_alarm_type','strata_bylaws','landlord_email_consent','tenant_email_consent',
    'electrical_repair_name','electrical_repair_phone','plumbing_repair_name','plumbing_repair_phone')
REQUIRED+=('suburb','state','postcode','tenant_notice_suburb','tenant_notice_state','tenant_notice_postcode')
QUESTIONS={'rental_mode':'Confirm this is an ordinary NSW whole-property residential tenancy. Room subleases and roommate agreements are not supported.',
    'landlord_name':'What is the full name of the landlord?','landlord_contact':'What are the landlord contact details?',
    'landlord_notice_address':'What is the landlord address for serving notices?',
    'tenant_names':'Which tenants will be named in the agreement? Enter one full name per line.','tenant_contact':'What are the tenant contact details?',
    'lease_type':'Will this be a fixed-term lease or a periodic lease without an end date?',
    'rent_amount':'What is the proposed rent? Enter the amount to confirm with the other party.',
    'rent_period':'Is this rent weekly, fortnightly or monthly?','bond':'What is the proposed bond? Enter 0 if there is no bond.',
    'start_date':'What is the proposed lease start date?','end_date':'What is the proposed fixed-term end date?','address':'Review the full property address for this tenancy.'}


def add_months(start,months):
    """Same day after N calendar months; clamp only to the target month's last day."""
    require(isinstance(start,str) and type(months) is int and months>0,
        422,'invalid_draft_fields','A calendar term requires a valid start date and a positive integer number of months.')
    try:
        day=date.fromisoformat(start)
        total=day.year*12+day.month-1+months
        year,month=divmod(total,12);month+=1
        return date(year,month,min(day.day,monthrange(year,month)[1])).isoformat()
    except (ValueError,OverflowError):
        require(False,422,'invalid_draft_fields','The calendar term exceeds the supported date range.')


def calendar_months(start,end):
    first=date.fromisoformat(start);last=date.fromisoformat(end)
    months=(last.year-first.year)*12+last.month-first.month
    return months if months>0 and add_months(start,months)==end else None


def validate_fields(value):
    shape(value,LEGACY_FIELDS,tuple(k for k in DEFAULTS if k not in LEGACY_FIELDS))
    value={**DEFAULTS,**value}
    result=dict(value)
    for key,limit in TEXT_LIMITS.items():
        require(isinstance(value[key],str) and len(value[key])<=limit and
                all(ch not in value[key] for ch in ('\x00','\r')),
                422,'invalid_draft_fields',LABELS[key]+' is invalid or too long.')
        result[key]=value[key].strip()
    for key,allowed in ENUMS.items():
        require(value[key] is None or (isinstance(value[key],str) and value[key] in allowed),
                422,'unsupported_draft_scope',LABELS[key]+' is outside the supported scope.')
    for key in ('start_date','end_date','first_rent_date','agreement_date'):
        if value[key] is None:continue
        require(isinstance(value[key],str),422,'invalid_draft_fields','Dates must use YYYY-MM-DD.')
        try: valid=date.fromisoformat(value[key]).isoformat()==value[key]
        except ValueError:valid=False
        require(valid,422,'invalid_draft_fields','Dates must use YYYY-MM-DD.')
    for key in ('postcode','landlord_notice_postcode','tenant_notice_postcode','agent_notice_postcode','tenant_agent_notice_postcode','corporation_postcode'):
        require(not result[key] or (len(result[key])==4 and result[key].isascii() and result[key].isdigit()),
            422,'invalid_draft_fields',LABELS[key]+' must contain four digits; leave blank if unknown.')
    months=result['lease_term_months']
    require(months is None or (type(months) is int and months in TERM_MONTHS),
        422,'invalid_draft_fields','Choose a supported calendar term or use custom dates.')
    require(months is None or result['lease_type']=='fixed',422,'invalid_draft_fields','Preset calendar terms apply only to fixed-term leases.')
    if months is not None and result['start_date']:
        derived=add_months(result['start_date'],months)
        require(result['end_date'] in (None,derived),422,'invalid_draft_fields','The end date does not match the start date and preset calendar term.')
        result['end_date']=derived
    require(not(result['start_date'] and result['end_date']) or result['end_date']>result['start_date'],
            422,'invalid_draft_fields','The end date must be after the start date.')
    require(result['lease_type']!='periodic' or (result['end_date'] is None and months is None),
            422,'invalid_draft_fields','Periodic leases do not have an end date.')
    for key in ('rent_amount','bond'):
        v=result[key]
        require(v is None or (type(v) in (int,float) and math.isfinite(v) and
                (v>=0 if key=='bond' else v>0) and v<1000000),
                422,'invalid_draft_fields',LABELS[key]+' must be a valid amount; leave blank if unknown.')
    capacity=result['max_occupants']
    require(capacity is None or (type(capacity) is int and 1<=capacity<=30),422,'invalid_draft_fields','Maximum occupants must be an integer from 1 to 30.')
    names=[n.strip() for n in result['tenant_names'].splitlines() if n.strip()]
    require(len(names)<=6 and all(len(n)<=80 for n in names),422,'invalid_draft_fields','Enter at most 6 tenants, one per line, with names no longer than 80 characters.')
    result['tenant_names']='\n'.join(names)
    import re
    for key in ('landlord_notice_email','tenant_notice_email'):
        if result[key.replace('_notice_email','_email_consent')]!='yes':result[key]=''
        require(not result[key] or re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',result[key]),
                422,'invalid_draft_fields',LABELS[key]+' has an invalid format.')
    for kind,allowed in (('battery',('battery','both')),('backup',('hardwired','both'))):
        if result['smoke_alarm_type'] not in allowed:
            result['smoke_'+kind+'_replaceable']=None
            result['smoke_'+kind+'_type']=''
        elif result['smoke_'+kind+'_replaceable']!='yes':result['smoke_'+kind+'_type']=''
    if result['strata_bylaws']!='yes':result['smoke_strata_responsible']=None
    return result


def questions(fields):
    fields={**DEFAULTS,**fields}
    required=list(REQUIRED)
    if fields['lease_type']=='fixed':required.append('end_date')
    for prefix,parts in (('agent',('name','contact','notice_address','notice_suburb','notice_state','notice_postcode')),
                         ('tenant_agent',('name','contact','notice_address','notice_suburb','notice_state','notice_postcode')),
                         ('corporation',('name','address','suburb','state','postcode'))):
        if any(fields[prefix+'_'+part] for part in parts):required.extend(prefix+'_'+part for part in parts)
    if not any(fields['agent_'+part] for part in ('name','contact','notice_address')):
        required.extend(('landlord_notice_address','landlord_notice_suburb','landlord_notice_state','landlord_notice_postcode','landlord_phone'))
    if fields['other_repair_name'] or fields['other_repair_phone']:required.extend(('other_repair_name','other_repair_phone'))
    if fields['smoke_alarm_type'] in ('battery','both'):
        required.append('smoke_battery_replaceable')
        if fields['smoke_battery_replaceable']=='yes':required.append('smoke_battery_type')
    if fields['smoke_alarm_type'] in ('hardwired','both'):
        required.append('smoke_backup_replaceable')
        if fields['smoke_backup_replaceable']=='yes':required.append('smoke_backup_type')
    if fields['strata_bylaws']=='yes':required.append('smoke_strata_responsible')
    for person in ('landlord','tenant'):
        if fields[person+'_email_consent']=='yes':required.append(person+'_notice_email')
    return [{'field':k,'label':LABELS[k],'question':QUESTIONS.get(k,'Please confirm '+LABELS[k]+'.')}
            for k in dict.fromkeys(required) if fields[k] in (None,'')]


def warnings(fields):
    result=['This is an unsigned draft for both parties to complete, review and confirm. It does not establish the other party agreement.',
        'Review repair contacts, charges, smoke alarms, electronic service choices and attachments with both parties. Unconfirmed fields remain blank.']
    rent=fields['rent_amount'];period=fields['rent_period'];bond=fields['bond']
    if rent is not None and period and bond is not None:
        weekly=rent if period=='week' else rent/2 if period=='fortnight' else rent*12/52
        if bond>weekly*4+0.005:result.append('The proposed bond exceeds four weeks of rent converted using the current period. Check the amount, period and official form bond requirements.')
    return result


def extraction_schema():
    return {'type':'object','required':['fields'],'additionalProperties':False,'properties':{'fields':{
        'type':'array','maxItems':len(DEFAULTS),'items':{'type':'object','required':['field','value','quote'],
            'additionalProperties':False,'properties':{'field':{'enum':[k for k in DEFAULTS if k not in MANUAL_CHOICE_FIELDS]},
                'value':{'type':['string','number','null']},'quote':{'type':'string','minLength':1,'maxLength':500}}}}}}
