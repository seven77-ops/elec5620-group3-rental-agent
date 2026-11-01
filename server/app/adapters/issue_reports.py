"""Simple issue reports with server dates, immutable content and local human advice."""
from ..common import require, shape, request_id, uid, now, integer
from .review_files import validate_review_files

CATEGORIES={'rent':'Rent / bond','furniture':'Furniture','repairs':'Repairs',
            'tenancy':'During the tenancy','moveout':'Moving out','post_tenancy':'After moving out','other':'Other'}


def issue_view(ctx,db,record):
    files=[]
    for identifier in record['report']['attachment_ids']:
        saved=ctx.repo.get(db,'living_attachment',identifier)
        if saved and saved['case_id']==record['case_id']:files.append(saved['metadata'])
    return {**record,'attachments':files}


class IssueReports:
    def __init__(self,ctx):self.ctx=ctx

    def list(self):
        from .operator_inbox import OperatorInbox
        from datetime import datetime
        items = [item for item in OperatorInbox(self.ctx).read(None)['items'] if item.get('report') and not item.get('is_demo')]
        items.sort(key=lambda item: datetime.fromisoformat(item['created_at'].replace('Z','+00:00')).timestamp(), reverse=True)
        return {'items':items}

    def create(self,case_id:str,body:dict):
        shape(body,('request_id','category','description','attachment_ids'))
        logical_id=request_id(body['request_id'])
        require(isinstance(body['category'],str) and body['category'] in CATEGORIES,422,'invalid_input','Choose an issue type.')
        description=body['description']
        require(isinstance(description,str) and 0<len(description.strip())<=5000 and len(description)<=5000,
                422,'invalid_input','Describe the issue using 1 to 5000 characters.')
        key=case_id+':'+logical_id
        with self.ctx.repo.transaction() as db:
            self.ctx.get(db,'case',case_id)
            old=self.ctx.receipt(db,'issue_report_receipt',key,body)
            if old:return old['result']
            validate_review_files(self.ctx,db,case_id,body['attachment_ids'])
            identifier=uid('issue');at=now();label=CATEGORIES[body['category']]
            record={'kind':'issue','case_id':case_id,'review_id':identifier,'address':'','version':1,
                    'status':'open','reason':label,'created_at':at,'updated_at':at,'decisions':[],
                    'report':{'category':body['category'],'title':label,'description':description,
                              'attachment_ids':body['attachment_ids']}}
            self.ctx.repo.put(db,'issue_report',identifier,record)
            result=issue_view(self.ctx,db,record)
            self.ctx.save_receipt(db,'issue_report_receipt',key,body,result)
            return result

    def advice(self,report_id:str,body:dict):
        shape(body,('request_id','expected_version','note'))
        logical_id=request_id(body['request_id'])
        require(integer(body['expected_version']) and body['expected_version']>=1,422,'invalid_input','Use the current report version.')
        require(isinstance(body['note'],str) and 0<len(body['note'].strip())<=2000 and len(body['note'])<=2000,
                422,'invalid_input','Enter review advice using 1 to 2000 characters.')
        with self.ctx.repo.transaction() as db:
            record=self.ctx.get(db,'issue_report',report_id)
            key=report_id+':'+logical_id
            old=self.ctx.receipt(db,'issue_advice_receipt',key,body)
            if old:return old['result']
            require(record['version']==body['expected_version'],409,'version_conflict','The report changed. Load the latest report before saving advice.')
            require(record['status']=='open',409,'review_closed','This report has already been reviewed.')
            from ..settings import OPERATOR
            at=now()
            record['decisions'].append({'decision':'release','note':body['note'],'at':at,'operator_id':OPERATOR})
            record.update(status='released',updated_at=at,version=record['version']+1)
            self.ctx.repo.put(db,'issue_report',report_id,record)
            result=issue_view(self.ctx,db,record)
            self.ctx.save_receipt(db,'issue_advice_receipt',key,body,result)
            return result
