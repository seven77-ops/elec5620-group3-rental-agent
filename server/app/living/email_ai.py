"""Polish only user-supplied repair text; saving and delivery are separate actions."""
from time import time

from ..ai.provider import ProviderError
from ..common import ApiError, now, request_id, require, shape, uid
from .fields import text

SCHEMA = {'type':'object','additionalProperties':False,'required':['subject','body'],
          'properties':{'subject':{'type':'string','minLength':1,'maxLength':200},
                        'body':{'type':'string','minLength':1,'maxLength':8000}}}


class RepairEmailAI:
    def __init__(self, ctx):
        self.ctx = ctx

    def polish(self, case_id: str, body: dict):
        shape(body, ('request_id','allow_external_ai','draft','recipient_name','language','tone'),
              ('title','location','priority'))
        key = case_id + ':' + request_id(body['request_id'])
        require(body['allow_external_ai'] is True,422,'ai_consent_required','请同意将本次原稿发送至配置的 AI。')
        text(body['draft'],5000,required=True)
        text(body['recipient_name'],200,single_line=True)
        text(body.get('title',''),200,single_line=True)
        text(body.get('location',''),500,single_line=True)
        require(body['language'] in ('en','zh') and body['tone'] in ('standard','polite','concise')
                and body.get('priority','normal') in ('normal','urgent'),422,'invalid_input','请选择有效的语言、语气和紧急程度。')
        attempt = uid('attempt')
        with self.ctx.repo.transaction() as db:
            self.ctx.get(db,'case',case_id)
            old = self.ctx.receipt(db,'repair_email_ai_receipt',key,body)
            if old and 'result' in old:
                return old['result']
            require(not old or old.get('status') != 'pending' or time()-old['started_at'] > 120,
                    409,'request_in_progress','这次润色仍在处理中，请稍后重试。')
            self.ctx.repo.put(db,'repair_email_ai_receipt',key,
                {'input':body,'attempt':attempt,'started_at':time(),'status':'pending'})
        try:
            output, meta = self.ctx.ai_provider.call({
                'task':'repair_email_polish', 'response_schema':SCHEMA,
                **{k:body[k] for k in ('draft','recipient_name','language','tone','title','location','priority') if k in body}})
            try:
                shape(output,('subject','body'))
                text(output['subject'],200,required=True,single_line=True)
                text(output['body'],8000,required=True)
            except ApiError:
                require(False,502,'ai_invalid_response','AI 返回的邮件格式不完整，请重新润色；原稿仍保留。')
            result = {**output, 'created_at':now(),
                'call':{k:v for k,v in meta.items() if k in ('task','provider','model','status','attempted','duration_ms','simulated')}}
            with self.ctx.repo.transaction() as db:
                saved = self.ctx.repo.get(db,'repair_email_ai_receipt',key)
                require(saved and saved.get('attempt') == attempt,409,'request_superseded','本次润色已被后续请求替代。')
                self.ctx.save_receipt(db,'repair_email_ai_receipt',key,body,result)
            return result
        except BaseException as exc:
            with self.ctx.repo.transaction() as db:
                saved = self.ctx.repo.get(db,'repair_email_ai_receipt',key)
                if saved and saved.get('attempt') == attempt:
                    saved['status'] = 'failed'
                    self.ctx.repo.put(db,'repair_email_ai_receipt',key,saved)
            if isinstance(exc,ProviderError):
                require(False,503,'ai_unavailable','AI 暂时不可用，原稿已保留。可稍后重试或直接准备普通报修草稿。')
            raise
