"""Polish only user-supplied repair text; saving and delivery are separate actions."""
from time import time

from ..ai.provider import ProviderError
from ..common import ApiError, now, request_id, require, shape, uid
from .fields import text
from ..english import supplied_names, untranslated_prose

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
        require(body['allow_external_ai'] is True,422,'ai_consent_required','Consent is required to send this draft to the configured AI provider.')
        text(body['draft'],5000,required=True)
        text(body['recipient_name'],200,single_line=True)
        text(body.get('title',''),200,single_line=True)
        text(body.get('location',''),500,single_line=True)
        require(body['language'] in ('en','zh') and body['tone'] in ('standard','polite','concise')
                and body.get('priority','normal') in ('normal','urgent'),422,'invalid_input','Choose a supported language, tone and priority.')
        attempt = uid('attempt')
        with self.ctx.repo.transaction() as db:
            self.ctx.get(db,'case',case_id)
            old = self.ctx.receipt(db,'repair_email_ai_receipt',key,body)
            if old and 'result' in old:
                return old['result']
            require(not old or old.get('status') != 'pending' or time()-old['started_at'] > 120,
                    409,'request_in_progress','This draft is still being polished. Retry shortly.')
            self.ctx.repo.put(db,'repair_email_ai_receipt',key,
                {'input':body,'attempt':attempt,'started_at':time(),'status':'pending'})
        try:
            output, meta = self.ctx.ai_provider.call({
                'task':'repair_email_polish', 'response_schema':SCHEMA,
                **{k:body[k] for k in ('draft','recipient_name','tone','title','location','priority') if k in body}, 'language':'en'})
            try:
                shape(output,('subject','body'))
                text(output['subject'],200,required=True,single_line=True)
                text(output['body'],8000,required=True)
                prose=' '.join(output[key] for key in ('subject','body'))
                require(not untranslated_prose(prose,[body['recipient_name'],body.get('location',''),*supplied_names(body['draft'])]),502,'ai_invalid_response',
                        'The generated email was not returned in English.')
            except ApiError:
                require(False,502,'ai_invalid_response','The AI email is incomplete or not in English. Please retry; your original draft is retained.')
            result = {**output, 'created_at':now(),
                'call':{k:v for k,v in meta.items() if k in ('task','provider','model','status','attempted','duration_ms','simulated')}}
            with self.ctx.repo.transaction() as db:
                saved = self.ctx.repo.get(db,'repair_email_ai_receipt',key)
                require(saved and saved.get('attempt') == attempt,409,'request_superseded','This polish request was superseded by a later request.')
                self.ctx.save_receipt(db,'repair_email_ai_receipt',key,body,result)
            return result
        except BaseException as exc:
            with self.ctx.repo.transaction() as db:
                saved = self.ctx.repo.get(db,'repair_email_ai_receipt',key)
                if saved and saved.get('attempt') == attempt:
                    saved['status'] = 'failed'
                    self.ctx.repo.put(db,'repair_email_ai_receipt',key,saved)
            if isinstance(exc,ProviderError):
                require(False,503,'ai_unavailable','AI is temporarily unavailable. Your original draft is retained. Retry later or prepare a standard repair draft.')
            raise
