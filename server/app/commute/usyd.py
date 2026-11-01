"""Product scope and verified campus reference, rather than a guessed university POI."""
from copy import deepcopy
import hashlib
import json

DESTINATION = {
    'id':'usyd:camperdown-darlington:fisher-library',
    'label':'University of Sydney Camperdown / Darlington main campus · Fisher Library',
    'latitude':-33.88630396441765, 'longitude':151.190498785334,
    'precision':'official_poi_point_not_entrance', 'accuracy_metres':10,
    'source_url':'https://portal.spatial.nsw.gov.au/server/rest/services/NSW_Features_of_Interest_Category_multiCRS/MapServer/3/query?objectIds=238482&outFields=*&outSR=4326&f=pjson',
    'campus_url':'https://www.sydney.edu.au/about-us/campuses/getting-to-campus.html',
    'reference_note':'Fisher Library is the common official campus reference point. Travel to specific classrooms and indoor walking are additional.',
}
# Presentation-only translation must not invalidate existing route evidence.
_HASH_REFERENCE = {**DESTINATION, 'label': "\u6089\u5c3c\u5927\u5b66 Camperdown / Darlington \u4e3b\u6821\u533a \u00b7 Fisher Library",
                   'reference_note': "\u4ee5 Fisher Library \u5b98\u65b9\u8bbe\u65bd\u70b9\u4e3a\u7edf\u4e00\u5230\u6821\u53c2\u8003\uff1b\u5230\u5177\u4f53\u6559\u5ba4\u53ca\u697c\u5185\u7684\u65f6\u95f4\u53e6\u8ba1\u3002"}
CAMPUS_FINGERPRINT = hashlib.sha256(json.dumps(_HASH_REFERENCE,sort_keys=True).encode()).hexdigest()
MODES = ('public_transport','train','metro','bus','drive','bike','walk')
PUBLIC_TRANSPORT_LABEL='Public transport (any combination)'
MODE_LABELS = {'public_transport':'public transport','train':'includes train','metro':'includes metro','bus':'includes bus',
               'drive':'driving','bike':'cycling','walk':'walking','light_rail':'light rail','ferry':'ferry'}


def student_brief(brief):
    result={key:deepcopy(value) for key,value in brief.items() if key not in ("arrival_time","travel_day","travel_date")}
    result.update(destination_query=DESTINATION['label'],destination_id=DESTINATION['id'])
    # "最多 N 分钟" is an actual ceiling. Flexibility requires a new explicit ceiling.
    if 'commute_max_minutes' in result: result['commute_hard_limit']=True
    return result


def transit_kind(transport):
    product=transport.get('product',{})
    name=' '.join(str(v) for v in (product.get('name',''),transport.get('name',''))).casefold()
    if 'metro' in name: return 'metro'
    return {1:'train',4:'light_rail',5:'bus',7:'bus',9:'ferry',11:'bus'}.get(product.get('class'))
