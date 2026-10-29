"""Agent 4 assistance around the original module: tenancy prefill and AI deduction reading.

Neither endpoint changes a case. Prefill only proposes values that the tenant confirms in the
tenancy form; extracted deductions are candidates the tenant edits before recording an update.
"""
from datetime import date, datetime
import math
import re
from zoneinfo import ZoneInfo

from ..ai.provider import ProviderError
from ..common import require, shape

SYDNEY = ZoneInfo('Australia/Sydney')
MAX_MESSAGE = 8000
MAX_CLAIMS = 10
REVIEW_STATUS = {'Awaiting Human Review': '等待人工复核', 'Awaiting Resubmission': '需要重新提交',
                 'Degraded Summary Only': '仅有限摘要', 'Questions Ready': '问题清单已准备'}
EXTRACT_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['claims', 'event_date', 'event_date_quote'],
    'properties': {'claims': {'type': 'array', 'maxItems': MAX_CLAIMS, 'items': {'type': 'object', 'additionalProperties': False,
        'required': ['amount', 'reason', 'quote'], 'properties': {'amount': {'type': 'number'}, 'reason': {'type': 'string'},
        'quote': {'type': 'string'}}}}, 'event_date': {'type': ['string', 'null']}, 'event_date_quote': {'type': ['string', 'null']}}}
DRAFT_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['statement_ids', 'closing'],
    'properties': {'statement_ids': {'type': 'array', 'items': {'type': 'string'}}, 'closing': {'const': 'itemisation'}}}


def _address(value):
    return ' '.join(re.sub(r'[^\w ]', ' ', (value or '').casefold()).split())


def _amounts(quote):
    """Dollar figures literally present in a quote, e.g. '$1,250.50' -> 1250.5."""
    return {float(m.replace(',', '')) for m in re.findall(r'\d[\d,]*(?:\.\d{1,2})?', quote)}


def checked_claims(output, message):
    """Keep only claims whose amount and quote are literally supported by the message."""
    claims, rejected = [], 0
    for item in output.get('claims') if isinstance(output.get('claims'), list) else []:
        try:
            amount, reason, quote = item['amount'], item['reason'].strip(), item['quote']
            valid = (type(amount) in (int, float) and math.isfinite(amount) and 0 < amount <= 100_000
                     and isinstance(quote, str) and quote.strip() and quote in message
                     and round(float(amount), 2) in _amounts(quote) and 0 < len(reason) <= 300)
        except (KeyError, TypeError, AttributeError):
            valid = False
        if not valid or len(claims) >= MAX_CLAIMS:
            rejected += 1
            continue
        claims.append({'amount': round(float(amount), 2), 'amount_cents': round(float(amount) * 100),
                       'reason': reason, 'quote': quote})
    return claims, rejected


def checked_event_date(output, message, today):
    value, quote = output.get('event_date'), output.get('event_date_quote')
    if not isinstance(value, str) or not isinstance(quote, str) or not quote or quote not in message:
        return None, None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None, None
    # A stated date must be visible in the quote (day number) and not in the future.
    return (value, quote) if parsed <= today and str(parsed.day) in quote else (None, None)


class AftercareAssist:
    def __init__(self, ctx):
        self.ctx = ctx

    def gateway(self, context):
        """Agent 4's constrained draft selection: the model may only pick catalogue IDs."""
        result, _ = self.ctx.ai_provider.call({'task': 'aftercare_draft_select', 'response_schema': DRAFT_SCHEMA, **context})
        return result

    def tenancy_prefill(self, case_id: str):
        repo = self.ctx.repo
        with repo.transaction() as db:
            case = self.ctx.get(db, 'case', case_id)
            selection = case.get('selection') or {}
            listing = selection.get('listing_snapshot') or {}
            saved = repo.get(db, 'review', case['reviews'][-1]['review_id']) if case.get('reviews') else None
        review = saved['review'] if saved else None
        fields = (review or {}).get('fields') or {}
        values, warnings, source_ref = {}, [], None

        def reviewed(name):
            field = fields.get(name) or {}
            if field.get('value') in (None, ''):
                return None
            evidence = field.get('evidence') or {}
            return {'value': field['value'], 'source': 'contract_review',
                    'label': f"合同复核 v{review['version']}" + (f" · 第{evidence['line']}行" if evidence.get('line') else ''),
                    'quote': evidence.get('quote')}

        if review:
            source_ref = f"contract-review:{review['review_id']}@v{review['version']}"
            for name, key in (('address', 'address'), ('move_out_date', 'end_date'), ('start_date', 'start_date'),
                              ('bond_amount', 'bond'), ('rent_amount', 'rent_amount'), ('rent_period', 'rent_period')):
                found = reviewed(key)
                if found:
                    values[name] = found
            if review['status'] != 'Reviewed':
                status = REVIEW_STATUS.get(review['status'], review['status'])
                warnings.append(f"合同复核状态为“{status}”，带入内容仅供核对，不代表合同已确认或已签署。")
        if listing.get('address'):
            listed = {'value': listing['address'], 'source': 'selected_listing', 'label': '已选房源广告快照'}
            if 'address' not in values:
                values['address'] = listed
                source_ref = source_ref or f"selected-listing:{selection.get('listing_id')}"
            elif _address(listing['address']) not in _address(values['address']['value']):
                warnings.append(f"合同地址与已选房源地址（{listing['address']}）不一致，请确认实际租住地址。")
            if type(listing.get('furnished')) is bool:
                values['furnished'] = {'value': listing['furnished'], 'source': 'selected_listing', 'label': '已选房源广告快照'}
        if not values:
            warnings.append('暂无已选房源或合同复核资料，可以直接填写实际租约资料。')
        warnings.append('带入的是待核对资料：请对照实际签署的租约修改后再明确确认。')
        return {'case_id': case_id, 'source_ref': source_ref, 'values': values, 'warnings': warnings}

    def extract_deductions(self, case_id: str, body: dict):
        shape(body, ('allow_external_ai', 'message'))
        require(body['allow_external_ai'] is True, 422, 'ai_consent_required', '请先同意将这段文字发送至配置的 AI。')
        message = body['message']
        require(isinstance(message, str) and message.strip() and len(message) <= MAX_MESSAGE, 422, 'invalid_input',
                f'请粘贴 1–{MAX_MESSAGE} 个字符的中介或房东原文。')
        with self.ctx.repo.transaction() as db:
            case = self.ctx.get(db, 'case', case_id)
        require(case.get('aftercare_case_id'), 409, 'aftercare_required', '请先确认租约资料并创建租后案件。')
        # Only the pasted text is sent; it is not stored with the case.
        try:
            output, meta = self.ctx.ai_provider.call({'task': 'aftercare_deduction_extract',
                                                      'response_schema': EXTRACT_SCHEMA, 'message': message})
        except ProviderError as exc:
            disabled = exc.code in {'ai_disabled', 'ai_not_configured'}
            require(False, 503, 'ai_unavailable', 'AI 未启用，请直接手动填写扣款主张。' if disabled
                    else 'AI 暂时不可用，请稍后重试或手动填写扣款主张。')
        today = datetime.now(SYDNEY).date()
        claims, rejected = checked_claims(output, message)
        event_date, event_quote = checked_event_date(output, message, today)
        return {'claims': claims, 'rejected': rejected, 'event_date': event_date, 'event_date_quote': event_quote,
                'call': {k: v for k, v in meta.items() if k in ('task', 'provider', 'model', 'status', 'duration_ms')},
                'notice': '以下是 AI 从原文读取的候选扣款主张，仅作为“报告的主张”，不代表扣款成立。请核对金额和原因后再记录。'}
