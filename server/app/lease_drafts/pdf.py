"""Fill the pinned official AcroForm without changing standard terms or signing."""
from hashlib import sha256
from io import BytesIO
import json
from datetime import date
from xml.sax.saxutils import escape
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, DictionaryObject, ArrayObject, FloatObject, DecodedStreamObject, TextStringObject
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from ..bootstrap import ROOT
from ..common import require

BASE=ROOT/'agent3/data/templates'
TEMPLATE=BASE/'nsw-residential-tenancy-2026-09-21.pdf'
MANIFEST=BASE/'nsw-residential-tenancy-2026-09-21.json'
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
TEXT_MAP={'address':'Text field 3.11','landlord_name':'Text field 1.4',
    'landlord_contact':'Text field 1.6','landlord_notice_address':'Text field 1.11',
    'tenant_contact':'Text field 2.14','tenant_notice_address':'Text field 2.10',
    'agent_name':'Text field 2.15','agent_notice_address':'Text field 2.16','agent_contact':'Text field 2.20',
    'rent_amount':'Text field 3.13','bond':'Text field 4.0','max_occupants':'Text field 4.4',
    'inclusions':'Text field 3.12','payment_details':'Text field 3.23','rent_due_day':'Text field 3.18'}
DATE_MAP={'start_date':'Text field 3.9','end_date':'Text field 3.10','first_rent_date':'Text field 3.19'}


def template_metadata():
    meta=json.loads(MANIFEST.read_text())
    require(sha256(TEMPLATE.read_bytes()).hexdigest()==meta['sha256'],503,'template_changed','官方租约模板完整性检查失败。')
    return meta


def field_values(fields):
    result={}
    for key,name in TEXT_MAP.items():
        value=fields[key]
        if value not in (None,''):result[name]=f'{value:g}' if type(value) in (int,float) else str(value).replace('\n','; ')
    for key,name in DATE_MAP.items():
        if fields[key]:result[name]=date.fromisoformat(fields[key]).strftime('%d/%m/%Y')
    names=fields['tenant_names'].splitlines()
    for i,name in enumerate(names[:3]):result['Text field 2.'+str(6+i)]=name
    if len(names)>3:result['Text field 2.9']='; '.join(names[3:])
    period=fields['rent_period']
    if period:
        result['Check Box 3.14']='/Weekly' if period=='week' else '/Fortnight' if period=='fortnight' else '/Other'
        if period=='month':result['Text field 3.17']='month'
    if fields['lease_type']=='periodic':result['Check Box 3.1']='/Periodic no end date '
    elif fields['lease_type']=='fixed':
        result['Check Box 3.1']='/Other'
        if fields['start_date'] and fields['end_date']:
            start=date.fromisoformat(fields['start_date']);end=date.fromisoformat(fields['end_date'])
            months=(end.year-start.year)*12+end.month-start.month
            options={6:'/6 months',12:'/12 months',24:'/2 years',36:'/3 years',60:'/5 years'}
            if start.day==end.day and months in options:result['Check Box 3.1']=options[months]
            else:result['Text field 3.2']=str((end-start).days)+' days'
    method=fields['payment_method']
    if method:result['Check Box 3.20']={'bank_transfer':'/Paid by approved electronic bank transfer','centrepay':'/Paid by Centrepay','other':'/Paid by Other'}[method]
    return result


def widget_name(widget):
    parts=[];obj=widget
    while obj:
        if obj.get('/T'):parts.insert(0,str(obj['/T']))
        obj=obj.get('/Parent');obj=obj.get_object() if obj else None
    return '.'.join(parts)


def font_for(value):return 'STSong-Light' if any(ord(c)>127 for c in value) else 'Helvetica'


def fitted(value,width):
    font=font_for(value)
    size=min(10,(width-5)/max(pdfmetrics.stringWidth(value,font,10),1)*10)
    require(size>=6.5,422,'draft_field_too_long','有字段超出官方表单可读长度，请缩短姓名、地址或说明内容后保存。')
    return font,size


def validate_pdf_values(fields):
    values=field_values(fields);reader=PdfReader(TEMPLATE)
    for page in reader.pages:
        for ref in page.get('/Annots',[]):
            obj=ref.get_object();name=widget_name(obj)
            if name in values and not name.startswith('Check Box'):
                rect=obj['/Rect'];fitted(values[name],float(rect[2])-float(rect[0]))
    return values


def appearance(writer,widget,value,retained):
    rect=widget['/Rect'];width=float(rect[2])-float(rect[0]);height=float(rect[3])-float(rect[1])
    font,size=fitted(value,width);buf=BytesIO();c=canvas.Canvas(buf,pagesize=(width,height))
    c.setFillColor(colors.HexColor('#173f7a'));c.setFont(font,size)
    c.drawString(2,max(3,(height-size)/2+2),value);c.save()
    appearance_reader=PdfReader(BytesIO(buf.getvalue()));retained.append(appearance_reader)
    source=appearance_reader.pages[0]
    stream=DecodedStreamObject();stream.set_data(source.get_contents().get_data())
    stream.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Form'),
        NameObject('/BBox'):ArrayObject([FloatObject(0),FloatObject(0),FloatObject(width),FloatObject(height)]),
        NameObject('/Resources'):source['/Resources'].clone(writer)})
    if font=='STSong-Light':
        fonts=writer.root_object['/AcroForm']['/DR']['/Font']
        for font_ref in source['/Resources']['/Font'].values():
            if font_ref.get_object().get('/BaseFont')=='/STSong-Light':
                fonts[NameObject('/DraftCJK')]=font_ref.clone(writer)
                target=widget
                while '/T' not in target and target.get('/Parent'):
                    target=target['/Parent'].get_object()
                target[NameObject('/DA')]=TextStringObject('/DraftCJK 10 Tf 0 g')
                widget[NameObject('/DA')]=TextStringObject('/DraftCJK 10 Tf 0 g')
                break
    widget[NameObject('/AP')]=DictionaryObject({NameObject('/N'):writer._add_object(stream)})


def cover_pages(draft):
    f=draft['fields'];style=ParagraphStyle('body',fontName='STSong-Light',fontSize=9,leading=13,textColor=colors.HexColor('#20334e'))
    title=ParagraphStyle('title',parent=style,fontName='Helvetica-Bold',fontSize=22,leading=27)
    small=ParagraphStyle('small',parent=style,fontSize=8,leading=11)
    story=[Paragraph('NSW LEASE DRAFT',title),Spacer(1,8),
        Paragraph('UNSIGNED - FOR DISCUSSION - VERSION '+str(draft['version']),style),Spacer(1,12),
        Paragraph('Generated from the NSW Fair Trading standard form dated 21 September 2026. Official standard terms follow in full. No signatures or party acknowledgments have been completed.',style),Spacer(1,12)]
    labels={'address':'Property address','rental_mode':'Proposed rental scope','landlord_name':'Landlord',
        'landlord_contact':'Landlord contact','landlord_notice_address':'Landlord notice address','tenant_names':'Tenants',
        'tenant_contact':'Tenant contact','tenant_notice_address':'Tenant notice address','agent_name':'Agent',
        'agent_contact':'Agent contact','agent_notice_address':'Agent notice address','lease_type':'Term type',
        'start_date':'Start date','end_date':'End date','rent_amount':'Proposed rent (AUD)',
        'rent_period':'Rent period','bond':'Proposed bond (AUD)','max_occupants':'Proposed maximum occupants',
        'inclusions':'Proposed inclusions','payment_method':'Proposed payment method','payment_details':'Payment details',
        'first_rent_date':'First rent due','rent_due_day':'Rent due day'}
    rows=[]
    for key,label in labels.items():
        value=f[key]
        if value in (None,''):continue
        value={'whole_property':'Whole property','fixed':'Fixed term','periodic':'Periodic (no end date)','week':'Per week','fortnight':'Per fortnight','month':'Per month','bank_transfer':'Electronic bank transfer','centrepay':'Centrepay','other':'Other'}.get(str(value),value)
        rows.append([Paragraph(label,small),Paragraph(escape(str(value)).replace('\n','<br/>'),small)])
    table=Table(rows,colWidths=[155,355],hAlign='LEFT')
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),0.3,colors.HexColor('#e2e9f2')),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    story += [table,Spacer(1,12),Paragraph('Items still to confirm',style)]
    for q in draft['questions']:story.append(Paragraph('- '+escape(q['question']),small))
    story += [Spacer(1,7),Paragraph('Complete the remaining official-form choices with both parties: repairs contacts, water and utilities, smoke alarms, notices, condition report and attachments. Blank fields are unknown, not agreed defaults.',small),Spacer(1,7),
        Paragraph('Public advertisement and user-recorded follow-up are reference material. This draft does not confirm availability, agreement by another party, application acceptance or signing.',small),Spacer(1,7),
        Paragraph('Template source: NSW Government / NSW Fair Trading. Source URL and SHA-256 are retained in this PDF metadata and the saved draft record.',small)]
    out=BytesIO();SimpleDocTemplate(out,pagesize=(595.276,841.89),leftMargin=42,rightMargin=42,topMargin=38,bottomMargin=38).build(story)
    return PdfReader(BytesIO(out.getvalue()))


def generate_pdf(draft):
    meta=template_metadata()
    require(meta['sha256']==draft['template']['sha256'],409,'template_changed','草稿对应的模板版本不可用。')
    values=validate_pdf_values(draft['fields']);reader=PdfReader(TEMPLATE);writer=PdfWriter();writer.clone_document_from_reader(reader)
    # Preserve the canonical field tree and all signature widgets. pypdf updates values and radio states.
    unicode_values={k:v for k,v in values.items() if not k.startswith('Check Box') and any(ord(c)>127 for c in v)}
    writer.update_page_form_field_values(None,{k:v for k,v in values.items() if k not in unicode_values},auto_regenerate=False)
    # pypdf caches cloned resources by reader identity. Keep temporary readers alive
    # until serialization so Python cannot reuse their ids for another font resource.
    retained=[]
    for page in writer.pages:
        for ref in page.get('/Annots',[]):
            obj=ref.get_object();name=widget_name(obj)
            if name in unicode_values:
                target=obj
                while '/T' not in target and target.get('/Parent'):
                    target=target['/Parent'].get_object()
                target[NameObject('/V')]=TextStringObject(values[name])
                if '/V' in obj:obj[NameObject('/V')]=TextStringObject(values[name])
            if name in values and not name.startswith('Check Box'):appearance(writer,obj,values[name],retained)
    cover=cover_pages(draft);retained.append(cover)
    for i,page in enumerate(cover.pages):writer.insert_page(page,i)
    for page in writer.pages:
        buf=BytesIO();c=canvas.Canvas(buf,pagesize=(float(page.mediabox.width),float(page.mediabox.height)))
        c.setFont('Helvetica',7);c.setFillColor(colors.HexColor('#476b9c'))
        label='UNSIGNED DRAFT v'+str(draft['version'])+' - remaining fields require both parties to confirm'
        stamp=c.beginText();stamp.setFont('Helvetica',7);stamp.setTextRenderMode(0)
        stamp.setTextOrigin((float(page.mediabox.width)-pdfmetrics.stringWidth(label,'Helvetica',7))/2,float(page.mediabox.height)-13)
        stamp.textOut(label);c.drawText(stamp)
        c.save();mark=PdfReader(BytesIO(buf.getvalue()));retained.append(mark);page.merge_page(mark.pages[0])
    writer.add_metadata({'/Title':'Unsigned NSW lease draft v'+str(draft['version']),
        '/Subject':'User-confirmed proposed fields; not signed; official standard terms retained',
        '/NSWTemplateSource':meta['source_url'],'/NSWTemplateSHA256':meta['sha256'],'/LeaseDraftId':draft['draft_id']})
    out=BytesIO();writer.write(out);data=out.getvalue()
    # Check the final canonical values as well as visible widget appearances before returning bytes.
    check=PdfReader(BytesIO(data));saved=check.get_fields() or {}
    require(all(name in saved and str(saved[name].get('/V'))==value for name,value in values.items()),
            500,'pdf_validation_failed','生成的表单字段校验失败。')
    require(all(not f.get('/V') for f in saved.values() if f.get('/FT')=='/Sig'),500,'pdf_validation_failed','签字栏必须保持空白。')
    return data
