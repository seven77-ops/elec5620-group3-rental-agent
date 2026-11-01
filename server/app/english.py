"""Keep authored prose English while retaining explicitly supplied proper names."""
import re
import unicodedata
from functools import lru_cache

from lingua import Language, LanguageDetectorBuilder

@lru_cache(maxsize=1)
def _detector():
    # Model files are bundled locally; no text is sent to a language service.
    # Cache the detector, never private prose or its classification results.
    return LanguageDetectorBuilder.from_all_spoken_languages().build()


def untranslated_prose(value, preserved=()):
    """Reject confidently non-English authored prose, preserving supplied data.

    Short labels and ambiguous names are not reliable language samples. Check
    the complete prose and individual sentences so an English greeting cannot
    hide a foreign-language body. Long source excerpts are exempt only when
    actually quoted, not when republished as the whole authored answer.
    """
    prose=value
    for original in sorted((s for s in preserved if isinstance(s,str) and s.strip()),key=len,reverse=True):
        if len(re.findall(r'[^\W\d_]+',original))>3 or re.search(r'[。！？!?]',original):
            for left,right in (('"','"'),('“','”'),('‘','’'),('「','」'),("'","'")):
                prose=prose.replace(left+original+right,' ')
        elif original.strip()!=value.strip():
            prose=re.sub(r'(?<!\w)'+re.escape(original)+r'(?!\w)',' ',prose)
    # Proper names embedded in an authorised source sentence remain literal.
    # An otherwise foreign-language answer cannot exempt itself this way.
    if len(re.findall(r'[A-Za-z]+',prose))>=3:
        for word in re.findall(r'[^\W\d_]+',prose):
            if any('LATIN' not in unicodedata.name(c,'') for c in word) and any(word in original for original in preserved):
                prose=prose.replace(word,' ')
    if any(unicodedata.category(c).startswith('L') and 'LATIN' not in unicodedata.name(c,'') for c in prose):
        return True
    for sample in [prose,*re.split(r'[.!?;\n]+',prose)]:
        if len(re.findall(r'[^\W\d_]+',sample))<3:continue
        scores=_detector().compute_language_confidence_values(sample)
        top=scores[0]
        english=next(s.value for s in scores if s.language==Language.ENGLISH)
        if top.language!=Language.ENGLISH and top.value>=0.65 and top.value-english>=0.35:
            return True
    return False


def supplied_names(draft):
    return re.findall(
        r'(?:我叫|我的名字是|姓名[：:]?|\b(?:my name is|I am|this is|signed|tenant name|building name)\s*[:：]?)\s*'
        r'([^\W\d_]{1,40})(?=[，。；、！!\s,.;]|$)', draft, re.I)
