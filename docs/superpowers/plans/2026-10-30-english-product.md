# English-only product release

**Goal:** Make all product-authored UI, agent replies, retrieval answers, generated drafts, guidance and errors English. Keep original user-entered text and source quotations intact.

**Approved direction:** The user explicitly requested the entire product in English permanently. No language switch is required. English input and output become the primary journey; multilingual input recognition can remain for compatibility.

**Architecture:** Translate authored copy at its source, use an English Ant Design/browser locale, enforce English in generation/RAG/email paths, and translate public catalogue descriptions. Do not add runtime machine translation or rewrite saved user records. Preserve Jev active routing, confirmations, consent, version checks and retries.

- [x] Frontend shell/forms/contracts/aftercare: English strings, aria labels, errors, status mappings, en locale and English-only generated-content controls.
- [x] Frontend chat/recommendations/candidates: English suggestions, cards, conversations, notices and readable historical system labels.
- [x] Backend: English deterministic narratives, generated questions and summaries, error messages, prompts and language defaults; public/private RAG and email output always English.
- [x] Public catalogues: translate provider descriptions, plan conditions, area summaries and commute annotations without changing prices, identifiers, URLs, dates or original source quotations.
- [x] Regression migration: update test UI selectors and authored-output expectations using reviewed mappings; retain meaningful multilingual-input coverage. Add English-only policy and rendered-output checks.
- [x] Freeze source and public document snapshots; build, run unit tests and representative browser journeys including housing, contract, repair, aftercare, audit and retrieval.
- [x] Run real-provider English smoke checks using synthetic data only; review generated responses and source citations.
- [x] Independent review, public help update and scoped catalogue/index release; back up and reload the live 5191/8011 workspace, preserving original business records and active Jev.

## Verification boundary

Chinese source aliases and historical/user/source quotations are data, not product copy. Tests must distinguish those from authored UI/output. No secrets or private case documents are sent for development translation. The release may append a translated public utility snapshot and replace public product-help index rows; existing business rows and other knowledge sources remain protected.
