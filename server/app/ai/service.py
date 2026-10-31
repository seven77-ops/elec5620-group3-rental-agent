"""Durable opt-in AI sidecars; external calls never own a SQLite write transaction."""
from hashlib import sha256
import time

from ..common import ApiError, integer, now, request_id, require, shape, uid
from ..repository import canonical
from .provider import CallRecorder, ProviderError


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


class AiService:
    def __init__(self, ctx, contracts):
        self.ctx, self.contracts = ctx, contracts

    def config(self):
        return self.ctx.ai_provider.public_config()

    def contract_source(self, db, review_id, expected_version=None):
        saved = self.ctx.get(db, 'review', review_id)
        review = saved['review']
        consent = self.ctx.repo.get(db, 'consent', saved.get('consent_id',''))
        case = self.ctx.get(db, 'case', saved['case_id'])
        require(consent and consent['active'] and self.contracts.selection_is_current(case,consent),
                403, 'consent_required', 'Contract-processing consent was revoked or the selection context changed. Historical results remain available.')
        if expected_version is not None:
            require(integer(expected_version) and expected_version == review['version'],409,'version_conflict','Reload the current contract review version.')
        return {'case_id':saved['case_id'],'review_id':review_id,'review_version':review['version'],
                'source_digest':digest(review),'document_sha256':review['document']['sha256'],
                'consent_id':saved['consent_id']}, saved

    def recommendation_source(self, db, run_id):
        saved = self.ctx.get(db,'evaluation',run_id)
        case = self.ctx.get(db,'case',saved['case_id'])
        report = saved['response']['report']
        require(report.get('data_mode') != 'real_listings',409,'real_ai_not_supported',
                'Live listings use fact-based filters. The older simulated-score interpreter does not apply to this report.')
        current = self.ctx.current(case,report['profile_version'])
        require(current['fingerprint']==report['profile_fingerprint'],409,'stale_evaluation','Use a recommendation report for current confirmed preferences.')
        return {'case_id':case['case_id'],'run_id':run_id,'profile_version':report['profile_version'],
                'source_digest':digest(report)}, saved

    def source(self, db, kind, ref, body):
        if kind == 'contract':
            return self.contract_source(db,ref,body.get('expected_version'))
        return self.recommendation_source(db,ref)

    def check(self, kind, ref, body, binding):
        with self.ctx.repo.transaction() as db:
            current,_ = self.source(db,kind,ref,body)
            require(current==binding,409,'ai_context_changed','Input context changed. Analyse the latest version again.')

    def decorate(self, record):
        result = dict(record)
        if record['kind']=='contract':
            try:
                with self.ctx.repo.transaction() as db:
                    current,_=self.contract_source(db,record['binding']['review_id'])
                valid=any(c.get('valid') and c.get('value') is not None for c in (record.get('result') or {}).get('candidates',[]))
                result['can_apply']=bool(record['status'] in {'success','partial'} and current==record['binding'] and valid)
            except ApiError:
                result['can_apply']=False
        return result

    def generate(self, kind, ref, body):
        shape(body,('request_id','allow_external_ai','expected_version') if kind=='contract' else ('request_id','allow_external_ai'))
        require(body['allow_external_ai'] is True,403,'ai_consent_required','Provide separate consent for external model processing before submitting.')
        if kind == 'contract':
            require(integer(body['expected_version']) and body['expected_version'] > 0,422,'invalid_input','The review version must be a positive integer.')
        key=kind+':'+ref+':'+request_id(body['request_id'])
        repo=self.ctx.repo
        with repo.transaction() as db:
            binding,saved=self.source(db,kind,ref,body)
            old=self.ctx.receipt(db,'ai_receipt',key,body)
            if old:
                require(old['binding']==binding,409,'ai_context_changed','Inputs bound to the original request changed. Create a new analysis for the current version.')
            if old and 'result' in old:
                completed=old['result']
            else:
                completed=None
                require(not old or old['lease_until']<time.time(),409,'operation_in_progress','This AI request is still processing. Read its status later or retry the original request.')
                token=uid('lease')
                reservation={'input':body,'binding':binding,'analysis_id':old['analysis_id'] if old else uid('ai'),
                             'token':token,'lease_until':time.time()+90,'created_at':old['created_at'] if old else now()}
                repo.put(db,'ai_receipt',key,reservation)
        if completed is not None:
            return self.decorate(completed)
        recorder=CallRecorder(self.ctx.ai_provider)
        result={'analysis_id':reservation['analysis_id'],'kind':kind,'status':'success',
                'created_at':reservation['created_at'],'binding':binding,'result':None,'calls':[]}
        def gateway(context):
            self.check(kind,ref,body,binding)
            return recorder(context)
        try:
            if kind=='contract':
                from .contracts import analyze_saved_contract
                result['result']=analyze_saved_contract(self.ctx,saved,gateway)
                if result['result']['explanation_status']=='failed':
                    result['status']='partial'
                if not any(c.get('valid') and c.get('value') is not None for c in result['result']['candidates']):
                    result['status']='failed'
                    result['error']={'code':'ai_no_valid_candidates','message':'The model returned no verifiable valid candidate values. The original review is retained.'}
            else:
                from rental_agent.ai_explanation import explain_recommendations
                result['result']=explain_recommendations(saved['response']['report'],gateway)
                if not saved['response']['report']['recommendations']:
                    result['status']='skipped'
        except ProviderError as exc:
            result.update(status='failed',error={'code':exc.code,'message':error_message(exc.code)})
        except ApiError:
            result.update(status='stale',error={'code':'ai_context_changed','message':'Processing consent or input context changed. The result cannot be applied.'})
        except (ValueError,TypeError,KeyError):
            result.update(status='failed',error={'code':'ai_invalid_result','message':'The model result failed schema or evidence checks. The original result is retained.'})
        except Exception:
            result.update(status='failed',error={'code':'ai_analysis_failed','message':'AI-assisted analysis did not complete. The original result is retained.'})
        result['calls']=recorder.calls
        stale=False
        with repo.transaction() as db:
            reserved=self.ctx.get(db,'ai_receipt',key)
            require(reserved['token']==token,409,'operation_in_progress','A newer recovery operation took over this request. Reload its latest status.')
            try:
                latest,_=self.source(db,kind,ref,body)
                require(latest==binding,409,'ai_context_changed','Inputs changed.')
            except ApiError:
                stale=True
                result.update(status='stale',error={'code':'ai_context_changed','message':'Processing consent or input context changed. Historical analysis cannot be applied.'})
            reserved['result']=result
            repo.put(db,'ai_receipt',key,reserved)
            repo.put(db,'ai_analysis',result['analysis_id'],result)
            pointer=repo.get(db,'ai_latest',kind+':'+ref)
            previous=repo.get(db,'ai_analysis',pointer['analysis_id']) if pointer else None
            if previous is None or previous['created_at'] <= result['created_at']:
                repo.put(db,'ai_latest',kind+':'+ref,{'analysis_id':result['analysis_id']})
        require(not stale,409,'ai_context_changed','Consent or context changed during analysis. Reload the latest status; the original review is retained.')
        return self.decorate(result)

    def latest(self,kind,ref):
        with self.ctx.repo.transaction() as db:
            self.ctx.get(db,'review' if kind=='contract' else 'evaluation',ref)
            saved=self.ctx.repo.get(db,'ai_latest',kind+':'+ref)
            result=self.ctx.get(db,'ai_analysis',saved['analysis_id']) if saved else None
        return self.decorate(result) if result else None


def error_message(code):
    return {'ai_disabled':'External models are disabled. Configure the backend and restart; original rule results are retained.',
            'ai_not_configured':'The model API is not fully configured. Set its endpoint, model and key in the local backend, then restart.',
            'ai_timeout':'The model call timed out. The original result is retained. Check the service and submit a new AI request.',
            'ai_http_error':'The model service rejected this request. Check the backend API configuration.',
            'ai_connection_error':'The model service is unreachable. The original result is retained.'}.get(code,'The model response could not be read or validated. The original result is retained.')
