"""Recognize only complete, unambiguous short edits in an active housing search.

This guards explicit slots against model omissions; complex/negated sentences
stay with the ordinary intent router rather than being parsed as instructions.
"""
import re

MODES = {'公共交通': 'public_transport', '火车': 'train', '地铁': 'metro',
         '公交车': 'bus', '公交': 'bus', '巴士': 'bus', '步行': 'walk',
         '走路': 'walk', '开车': 'drive', '自驾': 'drive', '骑行': 'bike', '骑车': 'bike'}
DIGITS = '零一二三四五六七八九'


def chinese(number):
    if number < 10:
        return DIGITS[number]
    if number < 100:
        tens, units = divmod(number, 10)
        return (DIGITS[tens] if tens > 1 else '') + '十' + (DIGITS[units] if units else '')
    hundreds, rest = divmod(number, 100)
    return DIGITS[hundreds] + '百' + (
        '' if not rest else '零' + DIGITS[rest] if rest < 10 else
        ('一' if rest < 20 else '') + chinese(rest))


NUMBERS = {chinese(number): number for number in range(1, 241)}
PREFIX = r'(?:(?:我想要?|我希望|改成|改为|换成|换为|那就|通勤改成)\s*)?'
MODE = '(?:' + '|'.join(sorted(MODES, key=len, reverse=True)) + ')'
DURATION = r'(?:单程)?(?:最多|不超过|至多|上限|≤)?\s*(?P<minutes>[0-9]{1,3}|[零一二两三四五六七八九十百]{1,8})\s*分钟(?:以内|内)?'
EDIT = re.compile(PREFIX + r'(?P<mode>' + MODE + r')?\s*(?:' + DURATION + r')?(?:到达的房子|到校的房子)?')


ENGLISH_MODES = {'public transport':'public_transport', 'train':'train', 'metro':'metro',
                 'bus':'bus', 'walk':'walk', 'walking':'walk', 'drive':'drive',
                 'driving':'drive', 'bike':'bike', 'cycling':'bike'}
ENGLISH_EDIT = re.compile(
    r'(?:(?:change (?:the commute )?to|switch to|use)\s+)?'
    r'(?P<mode>public transport|train|metro|bus|walking|walk|driving|drive|cycling|bike)?\s*'
    r'(?:(?:one[- ]way\s+)?(?:at most|no more than|within|maximum|up to)?\s*'
    r'(?P<minutes>[0-9]{1,3})\s*(?:minutes?|mins?))?')


def explicit_edit(conversation, text):
    brief = conversation.get('rental_brief', {})
    if conversation.get('dialogue_mode') not in ('recommend_areas', 'search') or not brief:
        return None
    if not any(brief.get(key) for key in ('commute_mode', 'commute_max_minutes', 'recommend_areas')):
        return None
    match = EDIT.fullmatch(text.strip().rstrip('。.!！·').strip())
    modes = MODES
    if not match:
        match = ENGLISH_EDIT.fullmatch(text.strip().rstrip('.!').strip().casefold())
        modes = ENGLISH_MODES
    if not match:
        return None
    patch = {}
    if match['mode']:
        patch['commute_mode'] = modes[match['mode']]
    if match['minutes']:
        raw = match['minutes'].replace('两', '二')
        minutes = int(raw) if raw.isascii() and raw.isdigit() else NUMBERS.get(raw)
        if minutes is None or not 1 <= minutes <= 240:
            return None
        patch['commute_max_minutes'] = minutes
    return {'intent': 'recommend_areas', 'brief_patch': patch} if patch else None
