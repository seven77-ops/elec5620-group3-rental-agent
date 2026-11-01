"""Exact source quotation groups with adjacent conditions retained.

This syntactic grouping is conservative, not a legal completeness classifier.
Groups are original source substrings, never rewritten or truncated. A group
that exceeds the model quote limit is omitted in its entirety.
"""
import re

MAX_QUOTE_CHARS = 3200
_SEPARATOR = re.compile(r'\n[ \t]*\n(?:[ \t]*\n)*')
_LIST = re.compile(r'^\s*(?:[-*+•]\s+|\d+[.)]\s+)')
_LEAD = re.compile(r'(?::|：|\b(?:should|must|may))\s*$', re.I)
_REFERENCE = re.compile(r'^\s*!?\[[^\]]+\]\(https?://.*\)\s*[.!]?\s*$', re.S)
_EXCEPTION = re.compile(r'^\s*(?:this\s+does\s+not\s+apply\s+if\b|however\b|unless\b|exceptions?\b)', re.I)
_ACCORDION = re.compile(r'\bkeyboard_arrow_(?:down|up)\s*$')
_BOUNDARY = re.compile(r'^\s*(?:#{1,6}\s+|(?:[*_-]\s*){3,}$)')


def _plain_start(value):
    # Recognize common Markdown emphasis without rewriting the returned text.
    return value.lstrip().lstrip('*_`').lstrip()


def _is_lead(value):
    return bool(_LEAD.search(value.rstrip().rstrip('*_`').rstrip()))


def _paragraph_spans(text):
    spans = []; start = 0
    for separator in _SEPARATOR.finditer(text):
        if text[start:separator.start()].strip():
            spans.append((start, separator.start()))
        start = separator.end()
    if text[start:].strip(): spans.append((start, len(text)))
    return spans


def source_passages(row):
    """Map quote ids to exact, complete source substrings of at most 3200 chars.

    Short sections remain whole. Longer sections join list lead-ins, separated
    bullet paragraphs, and immediately adjacent exception paragraphs/lists.
    No missing condition is guessed, and oversized groups are not partially
    exposed. The caller resolves quote ids against this same function.
    """
    if not isinstance(row, dict) or not isinstance(row.get('text'), str):
        raise ValueError('A source row with text is required')
    text = row['text'].strip()
    if not text: return {}
    if row.get('source_type') in ('official_guidance','official_template') and row.get('download_url') and type(row.get('page')) is int:
        # Verified public PDFs retain a complete physical page, including its notes.
        # No partial oversized page is exposed as a supposedly complete quotation.
        incomplete=_is_lead(text) or re.search(r'\b(?:or|and|if|unless|provided\s+that)\s*[,;]?\s*$',text,re.I)
        return {'p0':text} if len(text)<=8000 and not incomplete else {}
    if len(text) <= MAX_QUOTE_CHARS:
        return {} if _is_lead(text) else {'p0': text}
    spans = _paragraph_spans(text); groups = []; index = 0
    def paragraph(position):
        start, end = spans[position]
        return text[start:end]
    while index < len(spans):
        start = index; current = paragraph(index); index += 1
        # Captured accordion headings define whole procedures: later pronouns,
        # deadlines and exceptions cannot safely be quoted as unrelated steps.
        if _ACCORDION.search(current):
            while index<len(spans) and not _ACCORDION.search(paragraph(index)) and not _BOUNDARY.match(paragraph(index)):
                index+=1
            value=text[spans[start][0]:spans[index-1][1]]
            if index>start+1 and len(value)<=MAX_QUOTE_CHARS:groups.append(value)
            continue
        incomplete = bool(_EXCEPTION.match(_plain_start(current)))
        needs_list = _is_lead(current)
        if needs_list or _LIST.match(current):
            consumed_list = False
            while index < len(spans) and _LIST.match(paragraph(index)):
                consumed_list = True; index += 1
            if needs_list and not consumed_list:
                incomplete = True
        # An adjacent exception belongs to the preceding rule. Consume its list
        # even if the exception paragraph uses no colon, then any further caveats.
        while index < len(spans):
            exception_index = index
            # Official captures may insert a download/reference link between a
            # rule and its exception. Keep that bridge in the exact substring;
            # it does not turn the exception into an independent rule.
            while exception_index < len(spans) and _REFERENCE.match(paragraph(exception_index)):
                exception_index += 1
            if exception_index >= len(spans) or not _EXCEPTION.match(_plain_start(paragraph(exception_index))):
                break
            index = exception_index
            exception = paragraph(index); index += 1; consumed_list = False
            while index < len(spans) and _LIST.match(paragraph(index)):
                consumed_list = True; index += 1
            if _is_lead(exception) and not consumed_list:
                incomplete = True
        value = text[spans[start][0]:spans[index-1][1]]
        if not incomplete and len(value) <= MAX_QUOTE_CHARS:
            groups.append(value)
    return {f'p{number}': value for number, value in enumerate(groups)}
