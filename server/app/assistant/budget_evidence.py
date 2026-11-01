"""Check amounts explicitly present in the current message before changing units."""
import re

DIGITS={c:n for n,chars in enumerate(('零〇','一','二两','三','四','五','六','七','八','九')) for c in chars}
UNITS={'十':10,'百':100,'千':1000,'万':10000}
_SMALL=dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(),range(20)))
_TENS=dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(),range(20,100,10)))
_WORD='(?:'+'|'.join((*_SMALL,*_TENS,'hundred','thousand','and','point'))+')'
_ENGLISH_AMOUNT=re.compile(r'(?<![a-z])'+_WORD+r'(?:[\s-]+'+_WORD+r')*(?![a-z])',re.I)


def _under_hundred(tokens):
    if len(tokens)==1:
        return _SMALL.get(tokens[0],_TENS.get(tokens[0]))
    if len(tokens)==2 and tokens[0] in _TENS and tokens[1] in _SMALL and 1<=_SMALL[tokens[1]]<=9:
        return _TENS[tokens[0]]+_SMALL[tokens[1]]
    return None


def _group(tokens):
    if 'hundred' not in tokens:return _under_hundred(tokens)
    if tokens.count('hundred')!=1:return None
    at=tokens.index('hundred');head=_under_hundred(tokens[:at])
    if head is None or not 1<=head<=99:return None
    tail=tokens[at+1:]
    if tail[:1]==['and']:tail=tail[1:]
    rest=_under_hundred(tail) if tail else 0
    return None if rest is None else head*100+rest


def english_amount(value):
    """Parse one complete cardinal expression; never sum unrelated numbers."""
    tokens=re.split(r'[\s-]+',value.casefold());fraction=0
    if tokens[:1]==['and']:tokens=tokens[1:]
    if 'point' in tokens:
        if tokens.count('point')!=1:return None
        at=tokens.index('point');decimal=tokens[at+1:];tokens=tokens[:at]
        if not 1<=len(decimal)<=2 or any(t not in _SMALL or _SMALL[t]>9 for t in decimal):return None
        fraction=float('0.'+''.join(str(_SMALL[t]) for t in decimal))
    if 'thousand' not in tokens:
        whole=_group(tokens)
    else:
        if tokens.count('thousand')!=1:return None
        at=tokens.index('thousand');head=_group(tokens[:at]);tail=tokens[at+1:]
        if tail[:1]==['and']:tail=tail[1:]
        rest=_group(tail) if tail else 0
        if head is None or rest is None or not 1<=head<=999 or rest>=1000:return None
        whole=head*1000+rest
    return None if whole is None else whole+fraction


def chinese_amount(value):
    whole,_,fraction=value.partition('点')
    total=section=number=0
    last_unit=1
    for c in whole:
        if c in DIGITS:number=DIGITS[c]
        elif c in UNITS:
            unit=UNITS[c];last_unit=unit
            if unit==10000:total+=(section+number)*unit;section=number=0
            else:section+=(number or 1)*unit;number=0
    # Common spoken amounts: 一千二 = 1200, 一百五 = 150.
    if number and last_unit>=100 and whole[-1] in DIGITS and '零' not in whole and '〇' not in whole:
        number*=last_unit//10
    result=total+section+number
    if fraction and all(c in DIGITS for c in fraction):
        result+=float('0.'+''.join(str(DIGITS[c]) for c in fraction))
    return result


def stated_amount(text,amount):
    if amount is None:return False
    values=[float(v.replace(',','')) for v in re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?',text)]
    for match in _ENGLISH_AMOUNT.finditer(text):
        value=english_amount(match[0])
        if value is not None:values.append(value)
    for match in re.finditer(r'[零〇一二两三四五六七八九十百千万点]+',text):
        value=match[0]
        suffix=text[match.end():]
        if any(c in value for c in '百千万') or re.match(r'(?:澳元|澳币|元|块)',suffix):
            values.append(chinese_amount(value))
    return amount in values
