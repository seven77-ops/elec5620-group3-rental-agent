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
DEFAULTS.update({**{k:'' for k in OPTIONAL_TEXT_LIMITS},'agreement_date':None,'lease_term_months':None})
TEXT_LIMITS.update(OPTIONAL_TEXT_LIMITS)
TERM_MONTHS=(6,12,24,36,60)
LABELS={'address':'房屋地址','landlord_name':'出租方姓名','landlord_contact':'出租方联系方式',
    'landlord_notice_address':'出租方送达地址','tenant_names':'租客姓名','tenant_contact':'租客联系方式',
    'tenant_notice_address':'租客送达地址','agent_name':'代理姓名','agent_contact':'代理联系方式',
    'agent_notice_address':'代理送达地址','rental_mode':'整租适用范围','lease_type':'租期类型',
    'start_date':'起租日期','end_date':'结束日期','first_rent_date':'首期租金付款日期',
    'rent_amount':'拟定租金','rent_period':'租金周期','bond':'拟定押金','max_occupants':'约定最多居住人数',
    'inclusions':'明确包含的设施','payment_method':'付款方式','payment_details':'付款说明','rent_due_day':'租金付款日'}
LABELS.update({'suburb':'区域','state':'州','postcode':'邮编','agreement_date':'协议日期','agreement_place':'协议地点',
    'landlord_name_2':'第二出租方姓名','landlord_residence':'出租方住址','landlord_phone':'出租方电话',
    'lease_term_months':'日历月租期',
    **{prefix+'_'+part:label+suffix for prefix,label in (('landlord_notice','出租方送达'),('tenant_notice','租客送达'),('agent_notice','代理送达'))
       for part,suffix in (('suburb','区域'),('state','州'),('postcode','邮编'))},
    **{kind+'_repair_'+part:label+suffix for kind,label in (('electrical','电力维修'),('plumbing','管道维修'),('other','其他维修'))
       for part,suffix in (('name','联系人'),('phone','电话'))}})
REQUIRED=('rental_mode','address','landlord_name','landlord_contact','landlord_notice_address',
    'tenant_names','tenant_contact','lease_type','start_date','rent_amount','rent_period','bond')
QUESTIONS={'rental_mode':'请确认是否为新州普通整租住宅；单间分租及室友协议暂不适用。',
    'landlord_name':'出租方的完整姓名是什么？','landlord_contact':'出租方的联系方式是什么？',
    'landlord_notice_address':'出租方用于送达通知的地址是什么？',
    'tenant_names':'有哪些租客将列入合同？请逐行填写完整姓名。','tenant_contact':'租客的联系方式是什么？',
    'lease_type':'准备采用固定租期，还是没有结束日期的持续租约？',
    'rent_amount':'拟定租金是多少？请填写准备与对方确认的金额。',
    'rent_period':'这笔租金按每周、两周还是每月计价？','bond':'拟定押金是多少？没有押金请填 0。',
    'start_date':'准备从哪一天起租？','end_date':'固定租期准备在哪一天结束？','address':'请核对本次租约的完整地址。'}


def add_months(start,months):
    """Same day after N calendar months; clamp only to the target month's last day."""
    require(isinstance(start,str) and type(months) is int and months>0,
        422,'invalid_draft_fields','日历租期需要有效起租日期和正整数月数。')
    try:
        day=date.fromisoformat(start)
        total=day.year*12+day.month-1+months
        year,month=divmod(total,12);month+=1
        return date(year,month,min(day.day,monthrange(year,month)[1])).isoformat()
    except (ValueError,OverflowError):
        require(False,422,'invalid_draft_fields','日历租期超出支持的日期范围。')


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
                422,'invalid_draft_fields',LABELS[key]+'内容无效或过长。')
        result[key]=value[key].strip()
    for key,allowed in ENUMS.items():
        require(value[key] is None or (isinstance(value[key],str) and value[key] in allowed),
                422,'unsupported_draft_scope',LABELS[key]+'不属于当前支持的范围。')
    for key in ('start_date','end_date','first_rent_date','agreement_date'):
        if value[key] is None:continue
        require(isinstance(value[key],str),422,'invalid_draft_fields','日期须为 YYYY-MM-DD。')
        try: valid=date.fromisoformat(value[key]).isoformat()==value[key]
        except ValueError:valid=False
        require(valid,422,'invalid_draft_fields','日期须为 YYYY-MM-DD。')
    for key in ('postcode','landlord_notice_postcode','tenant_notice_postcode','agent_notice_postcode'):
        require(not result[key] or (len(result[key])==4 and result[key].isascii() and result[key].isdigit()),
            422,'invalid_draft_fields',LABELS[key]+'须为四位数字，未知时留空。')
    months=result['lease_term_months']
    require(months is None or (type(months) is int and months in TERM_MONTHS),
        422,'invalid_draft_fields','请选择支持的日历租期，或使用自定义日期。')
    require(months is None or result['lease_type']=='fixed',422,'invalid_draft_fields','预设日历租期只适用于固定租约。')
    if months is not None and result['start_date']:
        derived=add_months(result['start_date'],months)
        require(result['end_date'] in (None,derived),422,'invalid_draft_fields','结束日期与起租日及预设日历租期不一致。')
        result['end_date']=derived
    require(not(result['start_date'] and result['end_date']) or result['end_date']>result['start_date'],
            422,'invalid_draft_fields','结束日期须晚于起租日期。')
    require(result['lease_type']!='periodic' or (result['end_date'] is None and months is None),
            422,'invalid_draft_fields','持续租约不设置结束日期。')
    for key in ('rent_amount','bond'):
        v=result[key]
        require(v is None or (type(v) in (int,float) and math.isfinite(v) and
                (v>=0 if key=='bond' else v>0) and v<1000000),
                422,'invalid_draft_fields',LABELS[key]+'须为有效金额，未知时留空。')
    capacity=result['max_occupants']
    require(capacity is None or (type(capacity) is int and 1<=capacity<=30),422,'invalid_draft_fields','最多居住人数须为1至30的整数。')
    names=[n.strip() for n in result['tenant_names'].splitlines() if n.strip()]
    require(len(names)<=6 and all(len(n)<=80 for n in names),422,'invalid_draft_fields','最多填写6名租客，每行一名，姓名不超过80字。')
    result['tenant_names']='\n'.join(names)
    return result


def questions(fields):
    required=REQUIRED+('end_date',) if fields['lease_type']=='fixed' else REQUIRED
    return [{'field':k,'label':LABELS[k],'question':QUESTIONS[k]} for k in required if fields[k] in (None,'')]


def warnings(fields):
    result=['此文件是未签署草稿，须由双方完善、核对并确认；不会自动表示对方同意。',
        '官方表单中的紧急维修联系人、水费、供电供气、烟雾报警器、通知送达及相关附件仍需逐项完善；未知项保持空白。']
    rent=fields['rent_amount'];period=fields['rent_period'];bond=fields['bond']
    if rent is not None and period and bond is not None:
        weekly=rent if period=='week' else rent/2 if period=='fortnight' else rent*12/52
        if bond>weekly*4+0.005:result.append('拟定押金高于按当前周期折算的四周租金，请核对金额和周期，并复核官方表单押金要求。')
    return result


def extraction_schema():
    return {'type':'object','required':['fields'],'additionalProperties':False,'properties':{'fields':{
        'type':'array','maxItems':len(DEFAULTS),'items':{'type':'object','required':['field','value','quote'],
            'additionalProperties':False,'properties':{'field':{'enum':list(DEFAULTS)},
                'value':{'type':['string','number','null']},'quote':{'type':'string','minLength':1,'maxLength':500}}}}}}
