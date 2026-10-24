"""Offline Australian locality/postcode suggestions independent of listing addresses."""
from functools import lru_cache
import json
from pathlib import Path
from urllib.parse import quote

from ..common import require


@lru_cache(maxsize=1)
def _localities():
    rows = json.loads(Path(__file__).with_name('data').joinpath('au-localities.json').read_text(encoding='utf-8'))
    return tuple((suburb, state, postcode, suburb.casefold()) for suburb, state, postcode in rows)


def search_localities(q: str = '', state: str = ''):
    require(isinstance(q, str) and len(q) <= 80, 422, 'invalid_locality_query',
            'Locality search must be at most 80 characters.')
    require(isinstance(state, str) and len(state) <= 40, 422, 'invalid_locality_state',
            'State filter must be at most 40 characters.')
    query = q.strip().casefold()
    state_filter = state.strip().upper()
    if len(query) < 2:
        return {'items': [], 'source': 'au_postcodes'}
    matches = [r for r in _localities()
               if (not state_filter or r[1] == state_filter)
               and (query in r[3] or query in r[2])]
    matches.sort(key=lambda r: (0 if query in (r[3], r[2]) else
                               1 if r[3].startswith(query) or r[2].startswith(query) else 2,
                               r[3], r[1], r[2]))
    items = [{'id': 'locality:' + state.lower() + ':' + postcode + ':' + quote(suburb.casefold(), safe=''),
              'suburb': suburb, 'state': state, 'postcode': postcode}
             for suburb, state, postcode, _ in matches[:20]]
    return {'items': items, 'source': 'au_postcodes'}
