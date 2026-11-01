"""Generate a chat preview whose exact text is later saved by a reviewed proposal."""
from copy import deepcopy
import re

from ..common import uid
from ..living.email_ai import RepairEmailAI


def email_options(message, values, previous=None):
    previous = previous or {}
    # Output language is fixed; multilingual input and legacy values remain accepted.
    language = 'en'
    tone = values.get('email_tone', previous.get('email_tone', 'standard'))
    tones = list(re.finditer(r'礼貌|客气|polite|简洁|简短|concise|brief|标准|standard', message, re.I))
    if tones:
        term = tones[-1].group().casefold()
        tone = 'polite' if term in ('礼貌', '客气', 'polite') else 'concise' if term in ('简洁', '简短', 'concise', 'brief') else 'standard'
    return language, tone


def generate_draft(ctx, case_id, values, record, message, previous=None):
    """Only grounded issue text goes to AI. Stored contacts stay local."""
    values = deepcopy(values)
    language, tone = email_options(message, values, previous)
    polished = RepairEmailAI(ctx).polish(case_id, {
        'request_id': uid('repair-draft'), 'allow_external_ai': True,
        'draft': values['description'], 'recipient_name': '',
        'language': language, 'tone': tone, 'title': values['title'],
        'location': values.get('location', ''), 'priority': values['priority'],
    })
    body = polished['body']
    # Add the locally saved property reference without disclosing it to the model.
    if previous:
        address = previous.get('property_address')
        if address is None:
            legacy_body = previous.get('email', {}).get('body', '')
            found = re.search(r'(?m)^(?:地址：|房屋地址：|Property: )(.+)$', legacy_body)
            address = found.group(1) if found else ''
    else:
        address = record['profile'].get('address', '')
    if address and address not in body:
        body += '\n\n' + 'Property: ' + address
    values.update(email_language=language, email_tone=tone, property_address=address,
                  email_draft={'subject': polished['subject'], 'body': body})
    return values, polished['call']


def preview(values, recipient, proposal, repair_id=None):
    return {**values['email_draft'], 'to': recipient, 'language': values['email_language'],
            'tone': values['email_tone'], 'proposal_id': proposal['proposal_id'],
            **({'repair_id': repair_id} if repair_id else {})}
