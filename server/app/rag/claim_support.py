"""Conservative source-preservation guard; this is not full entailment verification.

Incomplete quotations and unsupported numeric durations are rejected. Conditional
or structured evidence is shown verbatim with its supplied section context, so a
paraphrase cannot silently remove an exception or change OR to AND. No legal
reasoning, missing passage completion, date inference, or translation is generated.
Numeric facts may come from the supplied trusted section path, but a duration
requires a matching amount and unit, not just a clause number. Context-derived
numeric claims are always replaced with the source and label. Callers must first
resolve an authentic quote from the authorized evidence pool.
"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

_SMALL = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(), range(20)))
_TENS = dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(), range(20, 100, 10)))
_WORDS = '|'.join((*_SMALL, *_TENS, 'hundred', 'thousand'))
_AMOUNT = rf'(?:\d[\d,]*(?:\.\d+)?|(?:{_WORDS})(?:[\s-]+(?:and[\s-]+)?(?:{_WORDS}))*)'
_DURATION = re.compile(rf'(?<!\w)(?P<amount>{_AMOUNT})[\s-]+(?:(?P<kind>business|working|calendar)[\s-]+)?(?P<unit>seconds?|minutes?|hours?|days?|weeks?|months?|years?)(?!\w)', re.I)
_CN_DURATION = re.compile(r'(?P<amount>\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百]+)\s*(?:个)?(?P<unit>工作日|自然日|日历日|天|周|星期|个月|月|年)')
_NUMBER = re.compile(r'(?<![\w])\d[\d,]*(?:\.\d+)?(?!\w)')
_CONDITIONAL = re.compile(r'\b(?:if|unless|provided(?:\s+that)?|except|only|subject\s+to|conditional\s+on|usually|generally|normally|typically|most)\b', re.I)
_STRUCTURED = re.compile(r'^\s*(?:[-*+]\s+|\d+[.)]\s+|\|)', re.M)
_MONTHS = {m.lower(): i for i, m in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'), 1)}
_MONTH_PATTERN = '|'.join(_MONTHS)
_DATE_PATTERN = rf'(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|\d{{1,2}}\s+(?:{_MONTH_PATTERN})\s+\d{{4}}|(?:{_MONTH_PATTERN})\s+\d{{1,2}},?\s+\d{{4}}|\d{{4}})'
_REGIME = re.compile(rf'\b(?P<direction>on\s+or\s+after|on\s+or\s+before|prior\s+to|earlier\s+than|later\s+than|before|after|pre[-\s]|post[-\s])\s*(?P<date>{_DATE_PATTERN})(?!\d)', re.I)


def _visible(text):
    # Link destinations and image URLs cannot justify a deadline or amount.
    visible=re.sub(r'https?://\S+', '', re.sub(r'!?\[([^\]]*)\]\([^\n]*?\)', r'\1', text))
    # A year in a Chinese statute title is a numeric identifier, not a lease
    # duration. Keep the number visible so an invented Act year still fails.
    visible=re.sub(r'《(\d{4})年([^》\n]{1,80}(?:法|条例|法案))》',r'《 \1 \2 》',visible)
    # Markdown emphasis/code delimiters are formatting, not part of an Act year.
    # Keep intra-word underscores so arbitrary identifier digits stay unsupported.
    return re.sub(r'(?<!\w)[*_`]+|[*_`]+(?!\w)', '', visible)


def _amount(value):
    try:
        return Decimal(value.replace(',', ''))
    except InvalidOperation:
        pass
    tokens = value.lower().replace('-', ' ').split(); total = 0; group = 0
    for token in tokens:
        if token in _SMALL: group += _SMALL[token]
        elif token in _TENS: group += _TENS[token]
        elif token == 'hundred': group = max(group, 1) * 100
        elif token == 'thousand': total += max(group, 1) * 1000; group = 0
        elif token != 'and': raise ValueError('Unsupported numeric expression')
    return Decimal(total + group)


def _cn_amount(value):
    try: return Decimal(value)
    except InvalidOperation: pass
    digits = {'零':0,'〇':0,'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    total = 0; number = 0
    for token in value:
        if token in digits: number = digits[token]
        elif token in ('十','百'): total += (number or 1) * (10 if token == '十' else 100); number = 0
        else: raise ValueError('Unsupported numeric expression')
    return Decimal(total + number)


def _durations(text):
    found = []
    for match in _DURATION.finditer(text):
        kind = (match['kind'] or '').lower()
        if kind == 'working': kind = 'business'
        unit = match['unit'].lower().rstrip('s')
        found.append(((_amount(match['amount']), kind, unit), match.span()))
    units = {'工作日':('business','day'),'自然日':('calendar','day'),'日历日':('calendar','day'),'天':('','day'),
             '周':('','week'),'星期':('','week'),'个月':('','month'),'月':('','month'),'年':('','year')}
    for match in _CN_DURATION.finditer(text):
        kind, unit = units[match['unit']]
        found.append(((_cn_amount(match['amount']), kind, unit), match.span()))
    return found


def _numeric_support(text, quote, context=''):
    text = _visible(text); quote = _visible(quote); context = _visible(context)
    claimed = _durations(text)
    quoted_durations = {item for item, _ in _durations(quote)}
    supported = quoted_durations | {item for item, _ in _durations(context)}
    used_context = any(item not in quoted_durations for item, _ in claimed)
    if any(item not in supported for item, _ in claimed):
        raise ValueError('Unsupported duration in quoted evidence')
    quoted_values = {_amount(m.group()) for m in _NUMBER.finditer(quote)} | {item[0] for item in quoted_durations}
    values = quoted_values | {_amount(m.group()) for m in _NUMBER.finditer(context)} | {item[0] for item in supported}
    for match in _NUMBER.finditer(text):
        if any(start <= match.start() and match.end() <= end for _, (start, end) in claimed):
            continue
        if _amount(match.group()) not in values:
            raise ValueError('Unsupported number in quoted evidence')
        if _amount(match.group()) not in quoted_values:
            used_context = True
    return used_context


def _date_bounds(value):
    value = value.lower()
    if re.fullmatch(r'\d{4}', value):
        year = int(value); return date(year, 1, 1), date(year, 12, 31)
    if '-' in value:
        year, month, day = map(int, value.split('-'))
    elif value[0].isdigit():
        day, month_name, year = value.split(); day = int(day); month = _MONTHS[month_name]; year = int(year)
    else:
        month_name, day, year = value.replace(',', '').split(); month = _MONTHS[month_name]; day = int(day); year = int(year)
    exact = date(year, month, day); return exact, exact


def _regimes(text):
    result = []
    for match in _REGIME.finditer(text):
        direction = match['direction'].lower()
        before = bool(re.search(r'before|prior|earlier|^pre', direction))
        try: lower, upper = _date_bounds(match['date'])
        except ValueError: continue
        result.append(('before' if before else 'after', lower if before else upper))
    for match in re.finditer(r'(\d{4})年(?:(\d{1,2})月(?:(\d{1,2})日)?)?(之前|以前|之后|以后|前|后)', text):
        year, month, day, direction = match.groups()
        try:
            point = date(int(year), int(month or 1), int(day or 1))
        except ValueError: continue
        result.append(('before' if direction in ('之前','以前','前') else 'after', point))
    return result


def _check_regime(context, question):
    # A comparison can intentionally request both scopes; each exact quote is
    # still labeled. Do not pick one side and silently answer the entire comparison.
    if re.search(r'\bbefore\s+and\s+after\b|\bpre[-\s].*\band\b.*\bpost[-\s]', question, re.I):
        return
    requested = _regimes(question)
    if len({direction for direction, _ in requested}) > 1:
        return
    for source_direction, source_date in _regimes(context):
        for query_direction, query_date in requested:
            if source_direction == query_direction:
                continue
            before_date, after_date = (source_date, query_date) if source_direction == 'before' else (query_date, source_date)
            if before_date <= after_date:
                raise ValueError('Explicit date regime conflicts with source context')


def preserve_claim(text, quote, section_context, question, language='en'):
    """Return a modest paraphrase or exact source with context, or reject it.

    ``section_context`` is the source's trusted ``section_path`` (list of heading
    strings or one string), never a model-created applicability label. A missing
    parent scope cannot be reconstructed here. English conditions/lists and all
    Chinese summaries are preserved as English source text. This intentionally
    reduces fluency; returning unchanged text does not establish entailment.
    """
    if not all(isinstance(value, str) and value.strip() for value in (text, quote, question)) or language not in ('en','zh'):
        raise ValueError('Invalid claim or source input')
    if section_context is None:
        context = ''
    elif isinstance(section_context, str):
        context = section_context.strip()
    elif isinstance(section_context, list) and all(isinstance(part, str) for part in section_context):
        context = ' > '.join(dict.fromkeys(part.strip() for part in section_context if part.strip()))
    else:
        raise ValueError('Invalid source section context')
    visible_quote = _visible(quote).strip().rstrip('*_`').rstrip()
    if visible_quote.endswith((':','：')) or re.search(r'\b(?:or|and|if|unless|provided\s+that)\s*[,;]?\s*$', visible_quote, re.I):
        raise ValueError('incomplete quotation omits conditions or a list')
    visible_context = _visible(context)
    _check_regime(visible_context if _regimes(visible_context) else _visible(quote), question)
    _context_numeric = _numeric_support(text, quote, context)
    preserve = (_context_numeric or language == 'zh' or _CONDITIONAL.search(_visible(quote)) or _CONDITIONAL.search(text)
                or _STRUCTURED.search(quote) or bool(_regimes(visible_context)))
    if preserve:
        replacement = ('Source context: ' + context + '\n\n' if context else '') + quote
        return {'text': replacement, 'adjusted': replacement != text}
    return {'text': text, 'adjusted': False}
