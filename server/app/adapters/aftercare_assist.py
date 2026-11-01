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
REVIEW_STATUS = {'Awaiting Human Review': 'Awaiting human review', 'Awaiting Resubmission': 'Awaiting resubmission',
                 'Degraded Summary Only': 'Limited summary only', 'Questions Ready': 'Questions ready'}
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
    # Require the entire calendar date; a digit in an amount is not date evidence.
    months = ('January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December')
    month = months[parsed.month - 1]
    formats = {value, f'{parsed.day}/{parsed.month}/{parsed.year}',
               f'{parsed.day:02d}/{parsed.month:02d}/{parsed.year}',
               f'{parsed.year}年{parsed.month}月{parsed.day}日'}
    for name in (month, month[:3]):
        formats.update((f'{parsed.day} {name} {parsed.year}',
                        f'{parsed.day:02d} {name} {parsed.year}',
                        f'{name} {parsed.day}, {parsed.year}',
                        f'{name} {parsed.day} {parsed.year}'))
    normalized = ' '.join(quote.casefold().split())
    supported = any(re.search(r'(?<!\w)' + re.escape(candidate.casefold()) + r'(?!\w)', normalized)
                    for candidate in formats)
    # Chinese prose does not require whitespace around its date.
    supported = supported or f'{parsed.year}年{parsed.month}月{parsed.day}日' in quote
    return (value, quote) if parsed <= today and supported else (None, None)


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
                    'label': f"Contract review v{review['version']}" + (f" · line {evidence['line']}" if evidence.get('line') else ''),
                    'quote': evidence.get('quote')}

        if review:
            source_ref = f"contract-review:{review['review_id']}@v{review['version']}"
            for name, key in (('address', 'address'), ('move_out_date', 'end_date'), ('start_date', 'start_date'),
                              ('bond_amount', 'bond'), ('rent_amount', 'rent_amount'), ('rent_period', 'rent_period')):
                found = reviewed(key)
                # A lease end already in the past is not offered as the planned move-out date.
                if found and not (name == 'move_out_date' and str(found['value']) < datetime.now(SYDNEY).date().isoformat()):
                    values[name] = found
            if review['status'] != 'Reviewed':
                status = REVIEW_STATUS.get(review['status'], review['status'])
                warnings.append(f"Contract review status is {status}. Imported details are for checking and do not establish confirmation or signing.")
        if listing.get('address'):
            listed = {'value': listing['address'], 'source': 'selected_listing', 'label': 'Selected listing advertisement snapshot'}
            if 'address' not in values:
                values['address'] = listed
                source_ref = source_ref or f"selected-listing:{selection.get('listing_id')}"
            elif _address(listing['address']) not in _address(values['address']['value']):
                warnings.append(f"The contract address differs from the selected listing address ({listing['address']}). Confirm your actual residential address.")
            if type(listing.get('furnished')) is bool:
                values['furnished'] = {'value': listing['furnished'], 'source': 'selected_listing', 'label': 'Selected listing advertisement snapshot'}
        if not values:
            warnings.append('No selected listing or contract review details are available. Enter actual tenancy details directly.')
        warnings.append('Imported details require checking. Review them against the signed agreement, edit as needed and explicitly confirm.')
        return {'case_id': case_id, 'source_ref': source_ref, 'values': values, 'warnings': warnings}

    def extract_deductions(self, case_id: str, body: dict):
        shape(body, ('allow_external_ai', 'message'))
        require(body['allow_external_ai'] is True, 422, 'ai_consent_required', 'Consent is required to send this text to the configured AI provider.')
        message = body['message']
        require(isinstance(message, str) and message.strip() and len(message) <= MAX_MESSAGE, 422, 'invalid_input',
                f'Paste 1–{MAX_MESSAGE} characters of the original agent or landlord message.')
        with self.ctx.repo.transaction() as db:
            case = self.ctx.get(db, 'case', case_id)
        require(case.get('aftercare_case_id'), 409, 'aftercare_required', 'Confirm tenancy details and create an aftercare case first.')
        # Only the pasted text is sent; it is not stored with the case.
        try:
            output, meta = self.ctx.ai_provider.call({'task': 'aftercare_deduction_extract',
                                                      'response_schema': EXTRACT_SCHEMA, 'message': message})
        except ProviderError as exc:
            disabled = exc.code in {'ai_disabled', 'ai_not_configured'}
            require(False, 503, 'ai_unavailable', 'AI is disabled. Enter the reported deduction claims manually.' if disabled
                    else 'AI is temporarily unavailable. Retry later or enter the reported deduction claims manually.')
        today = datetime.now(SYDNEY).date()
        claims, rejected = checked_claims(output, message)
        event_date, event_quote = checked_event_date(output, message, today)
        return {'claims': claims, 'rejected': rejected, 'event_date': event_date, 'event_date_quote': event_quote,
                'call': {k: v for k, v in meta.items() if k in ('task', 'provider', 'model', 'status', 'duration_ms')},
                'notice': 'These are candidate deductions extracted by AI from the original text. They are reported claims only, not established deductions. Check amounts and reasons before recording them.'}
