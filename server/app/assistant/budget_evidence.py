"""Check amounts explicitly present in the current message before changing units."""
import re

DIGITS={c:n for n,chars in enumerate(('零〇','一','二两','三','四','五','六','七','八','九')) for c in chars}
UNITS={'十':10,'百':100,'千':1000,'万':10000}


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
    for match in re.finditer(r'[零〇一二两三四五六七八九十百千万点]+',text):
        value=match[0]
        suffix=text[match.end():]
        if any(c in value for c in '百千万') or re.match(r'(?:澳元|澳币|元|块)',suffix):
            values.append(chinese_amount(value))
    return amount in values
