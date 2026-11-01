# Move-out issue reporting implementation plan

**Goal:** Let tenants report bond, cleaning, repair and other move-out problems directly to the existing protected Human review queue, and follow responses in the same case.

**Architecture:** Agent 4 owns reports as optional data on its existing durable review records. Commands retain version checks, idempotent receipts and operator authentication. Original reports are immutable; tenant additions and operator decisions are appended. No AI or external messaging is involved.

**Constraints:** Preserve existing records and pending review gates. All authored product text is English; original tenant text is preserved. A bond reference, activated bond case or complete cleaning inventory is not required to report an issue. Reports can be added after bond resolution without reopening or changing the saved bond outcome. A bond outcome must not silently close independent issue reports.

- [x] Add API regressions: four categories; no bond required; original text/evidence; retry once; foreign evidence/stale version rejection; reply after return; protected operator completion; durable read after restart; report after closed bond and preserve report when bond closes.
- [x] Add strict `report_issue` and `reply_review` payload contracts. Store original report plus append-only updates on review items; continue using existing operator decisions. Include all linked context in the operator inbox.
- [x] Add focused issue/report components and status presentation. Expose a prominent action above move-out tabs, then show reports, replies and operator history in `Issues & review`. Keep original plan/bond/reminder flows available. Preserve typed input on recoverable failure and close modal on successful retry only.
- [x] Simplify bond source/details copy into a compact facts area with expandable evidence; retain source access and confirmation. Update Human review to display report category, description, requested outcome, amount, references and tenant additions, with clear completion wording for reports.
- [x] Verify real API-backed browser reporting, operator return, tenant supplement and operator completion, reload persistence, mobile layout and failure/retry; run existing aftercare/operator regressions and frontend build. Use temporary synthetic cases only. Reload local services preserving actual configuration and database contents.
