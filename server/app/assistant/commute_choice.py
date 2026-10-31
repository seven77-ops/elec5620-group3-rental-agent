"""Explicit, conversation-local commute choices; profile writes require confirmation."""
from copy import deepcopy
import re

FIELDS=('commute_mode','commute_max_minutes','commute_hard_limit','commute_priority','max_transfers',
        'destination_query','destination_id','arrival_time','travel_day','travel_date','recommend_areas')
QUESTION='Would you like to filter by commute to the USYD main campus, or continue without a commute filter?'
YES='Yes, I would like to filter by commute.'
NO='No commute filter, please.'


def requested(brief):
    return brief.get('commute_preference')=='include' or any(brief.get(k) is not None for k in ('commute_mode','commute_max_minutes','max_transfers'))


def optional(brief):
    return not brief.get('suburb') and brief.get('commute_preference') not in ('include','skip') and not requested(brief)


def stated_choice(text):
    """Only explicit commute preferences; knowing a suburb is not an opt-out."""
    if re.search(r'\b(?:do not|don[’\x27]t) (?:want|need) to filter by commute\b|通勤(?:不用|不需要|无需|不要)(?:筛选|过滤|限制)|\bno commute filter\b|\bwithout (?:a )?commute (?:filter|limit)\b|\b(?:do not|don[’\x27]t) (?:need|want) (?:a )?commute (?:filter|limit)\b|(?:不需要|不用|不要|不想)(?:按|考虑)?通勤(?:筛选|限制|过滤)?|不(?:按|以)通勤筛选',text,re.I):
        return 'skip'
    if text.strip()==YES or re.search(r'\b(?:filter by|include|check|prioriti[sz]e) (?:the |my )?commut(?:e|ing)\b|\bcommute (?:filter|limit) (?:please|matters)\b|按通勤|核对通勤|核对到.{0,25}的通勤|上学方不方便|通勤(?:最多|不超过|上限)',text,re.I):
        return 'include'
    return None


def normalize(brief,patch=None,text='',saved=None):
    result=deepcopy(brief);patch=patch or {}
    choice=stated_choice(text) or patch.get('commute_preference')
    if choice is None and any(k in patch for k in ('commute_mode','commute_max_minutes','max_transfers')):
        choice='include'
    if choice is not None:result['commute_preference']=choice
    if result.get('commute_preference')=='skip':
        for key in FIELDS:result.pop(key,None)
    elif saved:
        result.setdefault('commute_mode',saved['mode'])
        result.setdefault('commute_max_minutes',saved['maximum_minutes'])
        if saved.get('max_transfers') is not None:result.setdefault('max_transfers',saved['max_transfers'])
    return result


def without_filters(filters):
    return {k:v for k,v in filters.items() if not k.startswith('usyd_')}
