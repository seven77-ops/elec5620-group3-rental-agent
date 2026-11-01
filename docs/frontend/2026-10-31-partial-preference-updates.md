# Preserve working housing conditions when saving partial preference edits

A budget-only update could be proposed while the user had already collected bedroom, bathroom and commute requirements in chat but had not saved a formal profile. The proposal merged the budget patch only with that sparse saved profile. Confirmation then evaluated a budget-only profile, while the independent commute brief still showed the original conditions in the header.

The proposal now starts with the supplied saved profile, overlays explicit working-chat conditions (with the last search filters as fallback), then applies the new patch last. Missing fields remain missing. Explicit changes still override prior values. A no-commute choice clears saved commute filtering. Preference summaries, saved profile evaluation and the resulting recommendation metadata now describe the same effective conditions.

Confirmation, revision checks, idempotency and Jev routing are unchanged. Existing proposal receipts and historical recommendation messages are not rewritten. A previously affected case can resend its budget edit and explicitly save the corrected full summary to generate new results.

Verification used temporary runtimes, real catalogue filtering and mocked model transport:

- Reproduced lost bedrooms, bathrooms and transit limits before the fix, including a filter-only legacy conversation.
- 51 backend tests passed, including five new regression cases, assistant API, short commute edits and preference intake.
- Three browser tests passed, covering the complete budget-only edit/save/reload flow and existing filter adjustment controls.
- Browser regression checks actual returned listing IDs/counts and each listing's bedroom, bathroom and rent values; backend checks the selected-mode commute limit and transfer limit too.
