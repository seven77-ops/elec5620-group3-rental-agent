# Public RAG answers before evidence

## Report and diagnosis

A Chinese bond-refund/dispute question retrieved valid English government passages but displayed only sources. The historical message recorded `unsupported_claim` on the older corpus; its rejected raw model output was not retained, so the exact old rejected sentence cannot be reconstructed. Reproduction also showed that successful Chinese claims were always replaced with long English quotations by the conservative source-preservation guard.

A separate false positive treated `《2010年住宅租赁法》` as a 2010-year duration. Statute-title normalization now treats that year as an identifier while still rejecting an invented year.

## Behavior

- Public answers now synthesize concise requested-language summaries from at most three source items, isolated in separate bounded model calls. Each claim selects one to three exact passages from its own source item; invented or combined-string IDs are rejected.
- An independent source review receives only each claim and its selected quotations. It distinguishes the original draft from a corrected final text, checks material conditions and translations, and can repair a draft. The final text passes numeric/unit/date, citation, status-code, certainty and targeted translation checks again. Invalid results fail atomically.
- Public presentation work shares a 36-second budget after retrieval; initial answer transport is capped at 18 seconds, isolated source calls run concurrently within the remaining budget, and independent review is capped at 8 seconds. No unbounded retry loop.
- The private contract compose path does not invoke the new public summary calls. Local-only requests, provider outages, intentional abstentions and missing passages do not trigger public synthesis.
- Chat displays the answer first, with original English evidence collapsed below. Sources-only failures explicitly explain that summary checking did not complete. Historical public messages have an explicit **重新总结 / Summarize again** action. It uses the original question and language, ignores late responses after unmount/case changes, and does not rewrite stored conversation receipts.
- Private evidence/bindings and local-only results are excluded from the public retry action. The separate knowledge panel keeps its external-AI consent behavior.

AI source review is a model quality check, not a human/legal certification or a proof of semantic entailment. Unsupported or unavailable summaries still retain readable sources and an explicit retry path.

## Verification

- 111 backend tests passed across public summary, answer integrity, source guards, public RAG, private RAG/security, transport, product help, passages and source context.
- 9 isolated browser tests passed, including a new Chinese chat answer, historical retry without conversation mutation, local-only search, private consent/revocation, abstention, product help and university-source labels.
- Frontend production build passed; the existing vendor bundle size warning remains.
- Real public-only Chinese and English bond questions returned `answered` with source-reviewed summaries. English final probe: 24.08 seconds; the reloaded local HTTP endpoint answered the original Chinese question in 26.34 seconds. Development reload backed up the business database and confirmed all 546 object rows unchanged before/after reload. The public answer endpoint itself does not mutate cases.

No private contract, case history or real contact data was sent in these model probes. No historical message was edited to manufacture a passing result.
