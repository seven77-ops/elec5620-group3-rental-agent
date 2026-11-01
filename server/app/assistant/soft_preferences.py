"""Deterministic, sourced preference ranking after authoritative hard filtering.

This module never retrieves candidates, changes a listing, or interprets numeric
constraints. A score measures documented preference coverage, not suitability.
"""
from copy import deepcopy
from hashlib import sha256
import json
import re
from urllib.parse import urlsplit

from ..areas.evidence import AreaKnowledge, sydney_today


LABELS = {
    'parks': 'Parks and outdoors', 'food': 'Dining', 'shopping': 'Shopping',
    'library': 'Library', 'community': 'Community facilities',
    'walkability': 'Walking paths', 'quiet': 'Quietness', 'safety': 'Safety',
}
PATTERNS = {
    'parks': r'\bparks?\b|\bparklands?\b|公园|户外',
    'food': r'\b(?:dining|restaurants?|food|cafes?)\b|餐饮|餐馆|吃饭',
    'shopping': r'\b(?:shops?|shopping|grocer(?:y|ies)|supermarkets?)\b|超市|购物|买菜|商店',
    'library': r'\blibrar(?:y|ies)\b|图书馆',
    'community': r'\bcommunity\s+(?:facilities|cent(?:re|er)s?)\b|社区设施|社区中心',
    'walkability': r'\b(?:walking\s+(?:paths?|trails?)|walkability|walkable)\b|散步|步道',
    'quiet': r'\bquiet(?:ness)?\b|安静|隔音',
    'safety': r'\b(?:safe|safety)\b|安全|治安',
}
# Full feature labels only: do not search substrings in arbitrary scraped text.
ADVERTISEMENT_FEATURES = {
    'close to shops': 'shopping', 'close to parklands': 'parks',
}
LIMITATIONS = [
    'All hard-filtered matches are retained. Soft preferences change order only; budget, room and commute rules are unchanged.',
    'Scores count distinct requested topics with evidence, not property quality or overall suitability. Unknown means unestablished, not unsuitable.',
    'Property advertisement features are unconfirmed advertiser claims. Suburb facility context does not establish a feature of this property.',
    'Facility presence and advertised proximity do not establish walking distance, a particular grocery store, quietness, safety, availability or an actual commute.',
    'Missing area coverage is not evidence that facilities are absent. Background opinions, stale references and wider or neighboring geography do not score.',
]


def _priority_edits(message):
    """Read topic edits in clause order, keeping negative facts separate from edits."""
    text = message.casefold()
    # Street names are not lifestyle requests.
    text = re.sub(r'\b(?:park|library)\s+(?:road|rd|street|st|lane|ln|avenue|ave)\b', '', text)
    clauses = re.split(r'[,.!?;，。！？；\n]|\bbut\b|但是|但', text)
    for clause in clauses:
        if re.search(r"\b(?:do not|don['’]?t)\s+(?:clear|remove|reset|drop)\b|不要(?:清空|取消|重置|修改)生活偏好", clause):
            continue
        if re.search(
            r'\b(?:no|without)\s+(?:(?:particular|specific|any)\s+)?lifestyle\s+(?:preferences?|priorities|requirements?)\b'
            r'|\b(?:clear|remove|reset|drop)\s+(?:(?:all|my)\s+)*lifestyle\s+(?:preferences?|priorities|requirements?)\b'
            r'|生活偏好(?:不限|没有要求|无要求|都可以)|(?:没有|无)(?:任何)?生活偏好|(?:清空|取消|重置)(?:所有)?生活偏好',
            clause,
        ):
            yield 'clear', []
            continue
        topics = [topic for topic, pattern in PATTERNS.items() if re.search(pattern, clause)]
        if not topics:
            continue
        if re.search(
            r"\b(?:don['’]?t|do not)\s+(?:care|need|want|prioriti[sz]e)\b"
            r"|\b(?:doesn['’]?t|does not)\s+matter\b|\bno\s+longer\s+(?:care|need|want|prioriti[sz]e)\b"
            r'|\b(?:no\s+(?:preference|need|requirement)|not\s+(?:interested|important|a\s+priority)|no\s+longer\s+(?:a\s+)?(?:matters?|important|priority))\b'
            r'|\b(?:drop|remove|ignore|stop\s+prioriti[sz]ing)\b'
            r'|不需要|不要|不在意|不关心|无所谓|不用|不重要|不考虑|不要求|取消|移除',
            clause,
        ):
            yield 'remove', topics
        elif not re.search(r"\b(?:no|not|without|isn['’]?t|aren['’]?t|don['’]?t|do not)\b|没有|并无", clause):
            yield 'add', topics


def explicit_priorities(message):
    """Recognize explicit English/Chinese additions; never infer numeric facts."""
    topics = []
    for operation, mentioned in _priority_edits(message):
        if operation == 'clear':
            topics = []
        elif operation == 'remove':
            topics = [topic for topic in topics if topic not in mentioned]
        else:
            topics = list(dict.fromkeys(topics + mentioned))
    return [topic for topic in LABELS if topic in topics]


def merge_explicit_priorities(brief, message):
    """Apply explicit schema-valid topic edits without touching hard fields."""
    result = deepcopy(brief)
    topics = list(dict.fromkeys(t for t in brief.get('lifestyle_priorities', []) if t in LABELS))
    edited = False
    for operation, mentioned in _priority_edits(message):
        edited = True
        if operation == 'clear':
            topics = []
        elif operation == 'remove':
            topics = [topic for topic in topics if topic not in mentioned]
        else:
            topics = list(dict.fromkeys(topics + mentioned))
    if edited:
        result['lifestyle_priorities'] = topics
    return result


def _advertisement_evidence(row, topics):
    source_url = row.get('source_url', '')
    url = urlsplit(source_url)
    if url.scheme != 'https' or not url.hostname or url.username or url.password:
        return []
    result = []
    seen = set()
    for feature in row.get('features') or []:
        if not isinstance(feature, str):
            continue
        normalized = ' '.join(feature.casefold().rstrip('*').split())
        topic = ADVERTISEMENT_FEATURES.get(normalized)
        if topic not in topics or normalized in seen:
            continue
        seen.add(normalized)
        result.append({
            'evidence_id': f"advertisement:{row['listing_id']}:{topic}",
            'topics': [topic], 'feature': feature, 'status': 'advertised_unconfirmed',
            'claim': f'The property advertisement lists “{feature}”.',
            'limitation': 'Advertiser claim only; distance, current facilities and availability have not been independently verified.',
            'source': {'url': source_url, 'captured_at': row.get('captured_at'),
                       'publisher': row.get('source_platform', 'Public property advertisement')},
        })
    return result


def rank_listings(rows, priorities, catalog, *, knowledge=None, today=None):
    """Return (same listing objects in ranked order, JSON-serializable evidence).

    Call only with the complete result of the existing hard-filter/commute path.
    Equal scores preserve that path's order. No input is mutated or removed.
    """
    today = today or sydney_today()
    knowledge = knowledge if knowledge is not None else AreaKnowledge()
    requested = list(dict.fromkeys(priorities))
    topics = [t for t in requested if t in LABELS]
    area_records = {suburb: knowledge.evidence(suburb, topics, today)
                    for suburb in dict.fromkeys(row['suburb'] for row in rows)}
    items = []
    for index, row in enumerate(rows):
        records = area_records[row['suburb']]
        # Use AreaKnowledge's freshness, kind and scope rules, not raw keywords.
        supporting = [deepcopy(record) for record in records if record['supports_topics']]
        advertised = _advertisement_evidence(row, topics)
        supported = {t for record in supporting for t in record['supports_topics']}
        supported.update(t for evidence in advertised for t in evidence['topics'])
        matched = [t for t in topics if t in supported]
        unknown = [t for t in topics if t not in supported]
        reasons = [f'Advertisement lists “{e["feature"]}” (unconfirmed advertiser claim).'
                   for e in advertised]
        reasons += [f'{LABELS[t]}: sourced suburb facility context in {row["suburb"]}; property distance unknown.'
                    for t in topics if any(t in e['supports_topics'] for e in supporting)]
        notes = []
        if not records:
            notes.append('Area sources have not been curated for this suburb; this is not evidence that facilities are absent.')
        elif not supporting and topics:
            notes.append('No current, appropriately scoped area source establishes these requested topics.')
        if any(t in ('quiet', 'safety') for t in topics):
            notes.append('Quietness and safety are not established by these sources and do not contribute to the score.')
        items.append({
            'listing_id': row['listing_id'], 'suburb': row['suburb'],
            'original_position': index + 1, 'score': len(matched),
            'matched_topics': matched, 'unknown_topics': unknown,
            'reasons': reasons, 'advertisement_evidence': advertised,
            'area_context': {'suburb': row['suburb'], 'has_curated_records': bool(records),
                             'evidence': supporting}, 'notes': notes,
        })
    items.sort(key=lambda item: (-item['score'], item['original_position']))
    ranked = [rows[item['original_position'] - 1] for item in items]
    catalog_suburbs = set(catalog.suburbs)
    curated_suburbs = {record['suburb'] for record in knowledge.records}
    report = {
        'schema_version': 'listing-soft-preferences.v1',
        'ranking_basis': 'Distinct requested topics with traceable evidence; equal scores preserve hard-match order.',
        'checked_at': today.isoformat(), 'catalog_fingerprint': catalog.fingerprint,
        'area_dataset_version': knowledge.version, 'area_evidence_fingerprint': knowledge.fingerprint,
        'priorities': [{'topic': t, 'label': LABELS[t]} for t in topics],
        'unsupported_priorities': [t for t in requested if t not in LABELS],
        'coverage': {
            'matching_listings': len(rows), 'matching_suburbs': len(area_records),
            'matching_suburbs_with_records': sum(bool(records) for records in area_records.values()),
            'matching_listings_with_supported_preferences': sum(bool(item['score']) for item in items),
            'matching_listings_with_advertisement_evidence': sum(bool(item['advertisement_evidence']) for item in items),
            'matching_listings_with_area_support': sum(bool(item['area_context']['evidence']) for item in items),
            'catalog_suburbs': len(catalog_suburbs),
            'catalog_suburbs_with_records': len(catalog_suburbs & curated_suburbs),
        },
        'items': items, 'limitations': list(LIMITATIONS),
    }
    report['fingerprint'] = sha256(json.dumps(report, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return ranked, report


def rank_answer(answer, brief, catalog, *, knowledge=None, today=None):
    """Adapter for assistant service; compare/selection order is never changed."""
    if answer.get('intent') not in ('search', 'collect_preferences', 'recommend_areas') or not brief.get('lifestyle_priorities'):
        return answer
    if 'listings' not in answer:
        return answer
    ranked, report = rank_listings(answer['listings'], brief['lifestyle_priorities'], catalog,
                                   knowledge=knowledge, today=today)
    return {**answer, 'listings': ranked, 'soft_preferences': report}
