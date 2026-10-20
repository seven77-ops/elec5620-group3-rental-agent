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
                403, 'consent_required', '合同处理同意已撤销或选房上下文已变化，历史结果仍可查看。')
        if expected_version is not None:
            require(integer(expected_version) and expected_version == review['version'],409,'version_conflict','请读取当前合同复核版本。')
        return {'case_id':saved['case_id'],'review_id':review_id,'review_version':review['version'],
                'source_digest':digest(review),'document_sha256':review['document']['sha256'],
                'consent_id':saved['consent_id']}, saved

    def recommendation_source(self, db, run_id):
        saved = self.ctx.get(db,'evaluation',run_id)
        case = self.ctx.get(db,'case',saved['case_id'])
        report = saved['response']['report']
        current = self.ctx.current(case,report['profile_version'])
        require(current['fingerprint']==report['profile_fingerprint'],409,'stale_evaluation','请使用当前确认偏好的推荐报告。')
        return {'case_id':case['case_id'],'run_id':run_id,'profile_version':report['profile_version'],
                'source_digest':digest(report)}, saved

    def source(self, db, kind, ref, body):
        if kind == 'contract':
            return self.contract_source(db,ref,body.get('expected_version'))
        return self.recommendation_source(db,ref)

    def check(self, kind, ref, body, binding):
        with self.ctx.repo.transaction() as db:
            current,_ = self.source(db,kind,ref,body)
            require(current==binding,409,'ai_context_changed','输入上下文已变化，请按最新版本重新分析。')

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
        require(body['allow_external_ai'] is True,403,'ai_consent_required','请单独同意本次外部模型处理后再提交。')
        if kind == 'contract':
            require(integer(body['expected_version']) and body['expected_version'] > 0,422,'invalid_input','复核版本必须为正整数。')
        key=kind+':'+ref+':'+request_id(body['request_id'])
        repo=self.ctx.repo
        with repo.transaction() as db:
            binding,saved=self.source(db,kind,ref,body)
            old=self.ctx.receipt(db,'ai_receipt',key,body)
            if old and 'result' in old:
                require(old['binding']==binding,409,'ai_context_changed','原请求绑定的输入已变化，请按当前版本新建分析。')
                completed=old['result']
            else:
                completed=None
                require(not old or old['lease_until']<time.time(),409,'operation_in_progress','本次 AI 请求仍在处理，请稍后读取或重试原请求。')
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
                    result['error']={'code':'ai_no_valid_candidates','message':'模型未返回可核对的有效候选值，原复核结果保留。'}
            else:
                from rental_agent.ai_explanation import explain_recommendations
                result['result']=explain_recommendations(saved['response']['report'],gateway)
                if not saved['response']['report']['recommendations']:
                    result['status']='skipped'
        except ProviderError as exc:
            result.update(status='failed',error={'code':exc.code,'message':error_message(exc.code)})
        except ApiError:
            result.update(status='stale',error={'code':'ai_context_changed','message':'处理同意或输入上下文已变化，结果不可应用。'})
        except (ValueError,TypeError,KeyError):
            result.update(status='failed',error={'code':'ai_invalid_result','message':'模型结果未通过结构或证据校验，原结果保留。'})
        except Exception:
            result.update(status='failed',error={'code':'ai_analysis_failed','message':'AI 辅助分析未完成，原结果保留。'})
        result['calls']=recorder.calls
        stale=False
        with repo.transaction() as db:
            reserved=self.ctx.get(db,'ai_receipt',key)
            require(reserved['token']==token,409,'operation_in_progress','请求已由新的恢复操作接管，请读取最新状态。')
            try:
                latest,_=self.source(db,kind,ref,body)
                require(latest==binding,409,'ai_context_changed','输入已变化。')
            except ApiError:
                stale=True
                result.update(status='stale',error={'code':'ai_context_changed','message':'处理同意或输入上下文已变化，历史分析不可应用。'})
            reserved['result']=result
            repo.put(db,'ai_receipt',key,reserved)
            repo.put(db,'ai_analysis',result['analysis_id'],result)
            pointer=repo.get(db,'ai_latest',kind+':'+ref)
            previous=repo.get(db,'ai_analysis',pointer['analysis_id']) if pointer else None
            if previous is None or previous['created_at'] <= result['created_at']:
                repo.put(db,'ai_latest',kind+':'+ref,{'analysis_id':result['analysis_id']})
        require(not stale,409,'ai_context_changed','分析期间同意或上下文已变化，请读取最新状态；原复核结果保留。')
        return self.decorate(result)

    def latest(self,kind,ref):
        with self.ctx.repo.transaction() as db:
            self.ctx.get(db,'review' if kind=='contract' else 'evaluation',ref)
            saved=self.ctx.repo.get(db,'ai_latest',kind+':'+ref)
            result=self.ctx.get(db,'ai_analysis',saved['analysis_id']) if saved else None
        return self.decorate(result) if result else None


def error_message(code):
    return {'ai_disabled':'外部模型功能尚未开启；请在后端配置并重启服务，原规则结果保留。',
            'ai_not_configured':'模型 API 尚未完整配置；请在本机后端填写地址、模型和密钥后重启。',
            'ai_timeout':'模型调用超时，原结果保留；可检查服务后发起新的 AI 请求。',
            'ai_http_error':'模型服务拒绝了本次请求，请检查后端 API 配置。',
            'ai_connection_error':'无法连接模型服务，原结果保留。'}.get(code,'模型响应未通过读取或校验，原结果保留。')
