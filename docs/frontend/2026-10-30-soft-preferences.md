# Evidence-backed listing preference ordering

The assistant can reorder the complete hard-filtered listing set using explicit
lifestyle priorities. Budget, bedroom/bathroom/parking counts and mode-specific
commute matching remain authoritative. This module never retrieves or drops a
candidate, relaxes a constraint, or calls an embedding/cloud model.

## Service integration

```python
from .soft_preferences import merge_explicit_priorities, rank_answer

brief = merge_brief(memory, intent)
brief = merge_explicit_priorities(brief, body['message'])
# Existing answer/commute/hard-filter construction remains in place.
answer = rank_answer(answer, brief, catalog)
search_filters = answer.pop('_search_filters', None)
```

`rank_answer` acts on `search`, `collect_preferences` and `recommend_areas` only.
Comparison/selection order stays intact. The extractor edits only existing
`lifestyle_priorities` enum values and does not modify hard fields. English and
Chinese topic phrases support additions, explicit removal (for example,
“Shopping no longer matters; prioritize parks” / “买菜无所谓，优先公园”), and
clearing all topics (“No lifestyle preferences” / “生活偏好不限”). Explicit clear
persists an empty list. Clause order resolves subsequent edits; unrelated
preferences remain. Negative property facts and common street-name false
positives do not remove existing preferences.

## Evidence policy

Each requested topic contributes at most one point. Equal scores preserve the
incoming hard-match ordering. This is a count of documented preference coverage,
not a suitability, quality or desirability score. Unknown topics do not remove
listings. Quietness and safety always remain unestablished.

Current official/venue area records must pass `AreaKnowledge.evidence()`'s
freshness, topic and geography checks. Media/resident opinions, stale/future-dated
references, LGA records and neighboring facilities do not score. No neighboring
suburb's facts are borrowed. Missing curation never means facilities are absent.

Only full advertisement feature labels `Close to shops` and `Close to Parklands`
(case-insensitive, optional trailing extraction asterisk) are recognized for the
matching explicit topic. Negative phrases, scraped navigation, unrelated feature
labels and missing/invalid source links cannot contribute. Advertiser proximity
claims remain labeled unconfirmed; they establish no verified property distance.
Sources about shops do not establish a particular grocery store. Area facilities
establish no property feature, walking distance, quietness, safety or commute.

The serialized report contains evidence per listing, source identifiers/URLs,
scope, source dates and limitations, requested/matched/unknown topics, actual
matching-set and catalog coverage, catalog fingerprint, area evidence fingerprint,
dataset version and evaluation date. Its own fingerprint binds the complete
report, including incoming match order. It is a dated snapshot; old reports do
not assert their sources remain current on the date of viewing.

## UI integration

Add `soft_preferences?: SoftPreferenceReport` to the assistant message API type,
importing from `api/softPreferences`. Render the overview once and evidence inside
each listing card:

```tsx
<SoftPreferenceEvidence report={message.soft_preferences} />
<SoftPreferenceEvidence report={message.soft_preferences} listingId={row.listing_id} />
```

The overview shows all hard matches retained, coverage counts, and preferences
unestablished throughout the result set. Individual evidence distinguishes
property advertisement claims from suburb facility context and exposes exact
source references and scope in native keyboard-accessible details. Unknowns and
coverage gaps remain visible, along with a caveat that these sources do not verify
property walking distance, quietness or safety. The component does not truncate
the result set.

## Validation

- `python3 -m unittest server.tests.test_soft_preferences server.tests.test_area_evidence`
- `npm run build` from `frontend`
- `WEB_TEST_BASE_URL=http://127.0.0.1:5187 PLAYWRIGHT_CHROMIUM_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npx playwright test e2e/soft-preferences.spec.ts`

The focused browser test uses an isolated Vite fixture with synthetic source URLs
and does not create cases, call AI, or change live app data. Backend tests include
155 numeric-filter matches and 428 public-transport-filter matches in the current
1000-listing snapshot, asserting unchanged listing facts and identical ID sets.
