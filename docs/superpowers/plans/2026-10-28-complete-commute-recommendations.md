# Complete commute recommendations

Goal: show every eligible house and suburb, provide explicit All filtering, and vary the first page on an explicit refresh without changing confirmed requirements.

1. Add failing backend regressions for more than 12 houses / 5 suburbs, coarse ranges obeying their upper bound, refreshing while preserving the entire eligible set, and continuing scheduled queries beyond the initial 12. Add provider tests for assistant temperature 0.6 versus extraction temperature 0.
2. Return complete eligible discovery results from `commute/cached_plan.py`. Keep precise and coarse provenance in the records; only promote coarse ranges satisfying all selected constraints. Add conversation-aware presentation ordering and refresh handling in `assistant/commute.py` and the intent schema. For explicit arrival queries reuse fresh matching reports and query another bounded set while preserving previously eligible routes. Preserve elapsed-time, deadline, transfer and budget checks.
3. Simplify `CommuteResults.tsx`: use one eligible list, status 已筛选, explicit 全部 followed by all result suburbs, a 公共交通 ≤30分钟 tag, and 12-item pagination. Remove the small date/arrival/criteria row and separate reference/pending lists. Add a 换一批 action preserving all requirements.
4. Verify backend regressions, provider schema/transport tests, build and formatting. Use isolated Playwright cases to exercise All/suburb/page/refresh on desktop and mobile; retain the production case directory when restarting 5191/8011.

Constraints: no resets, commits, changes to catalogue media, invented user times, relaxed maximum durations, or external messages. Existing explicit arrival requirements remain effective. Model variability does not authorize invented listings or weaker constraints.
