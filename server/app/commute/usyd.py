"""Product scope and verified campus reference, rather than a guessed university POI."""
from copy import deepcopy
import hashlib
import json

DESTINATION = {
    'id':'usyd:camperdown-darlington:fisher-library',
    'label':'悉尼大学 Camperdown / Darlington 主校区 · Fisher Library',
    'latitude':-33.88630396441765, 'longitude':151.190498785334,
    'precision':'official_poi_point_not_entrance', 'accuracy_metres':10,
    'source_url':'https://portal.spatial.nsw.gov.au/server/rest/services/NSW_Features_of_Interest_Category_multiCRS/MapServer/3/query?objectIds=238482&outFields=*&outSR=4326&f=pjson',
    'campus_url':'https://www.sydney.edu.au/about-us/campuses/getting-to-campus.html',
    'reference_note':'以 Fisher Library 官方设施点为统一到校参考；到具体教室及楼内的时间另计。',
}
CAMPUS_FINGERPRINT = hashlib.sha256(json.dumps(DESTINATION,sort_keys=True).encode()).hexdigest()
MODES = ('public_transport','train','metro','bus','drive','bike','walk')
MODE_LABELS = {'public_transport':'公共交通','train':'火车','metro':'地铁','bus':'公交车',
               'drive':'开车','bike':'骑行','walk':'步行','light_rail':'轻轨','ferry':'轮渡'}


def student_brief(brief):
    result=deepcopy(brief)
    result.update(destination_query=DESTINATION['label'],destination_id=DESTINATION['id'])
    # "最多 N 分钟" is an actual ceiling. Flexibility requires a new explicit ceiling.
    if 'commute_max_minutes' in result: result['commute_hard_limit']=True
    return result


def transit_kind(transport):
    product=transport.get('product',{})
    name=' '.join(str(v) for v in (product.get('name',''),transport.get('name',''))).casefold()
    if 'metro' in name: return 'metro'
    return {1:'train',4:'light_rail',5:'bus',7:'bus',9:'ferry',11:'bus'}.get(product.get('class'))
