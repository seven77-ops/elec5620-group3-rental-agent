# Public RAG cited-summary repair

User reported a public Chinese bond/refund question rendering only sources. The stored message has outcome unsupported_claim on the older 49-chunk index, not a retrieval outage. Current 153-chunk reproduction answers but replaces all Chinese summaries with lengthy English source text.

## Authorized implementation

- Keep the private-contract compose path intact. Narrowly correct Chinese statute-year normalization in the shared conservative guard, with regression coverage.
- Public answers receive bounded per-source synthesis plus an independent review/correction pass when the original answer was source-preserving or failed citation/content checks. Synthesis requests are isolated to one source each; each final claim may cite up to three exact passages from that source. It writes the requested-language summary from authorized public passages, then independently checks and corrects each claim against only its cited quotations. Original-draft support and corrected-final support are separate fields. Invalid first-pass text is never trusted or forwarded as a draft.
- Server still resolves exact citation pairs, checks numeric/duration/date support and complete quotation boundaries, rejects unsupported certainty, and atomically accepts only all-valid reviewed claims. A model review is an AI quality check, not human/legal certification.
- No extra cloud pass for local-only requests, private evidence, intentional abstention, missing complete evidence or a provider outage. Bound public first pass and source review so the existing frontend timeout remains practical.
- Present the answer before collapsed evidence. Historical public source-only messages get an explicit read-only “重新总结” action using their original public question; it updates this view, not historic immutable receipts or selections. Private or unauthorized evidence never gets this public retry.

## Checklist

- [x] Failing tests for localized reviewed answers, incorrect citations/numbers/certainty/review rejection, no extra private/local/outage calls, and safe historical retry presentation.
- [x] Implement isolated public summary module/provider task and bounded transport setting; integrate only KnowledgeService.answer.
- [x] Add public chat reply wrapper and explicit fallback diagnostics/retry. Keep original evidence available and do not auto-expand all quotes.
- [x] Real public-question probes for this exact bond question in Chinese and English; original source checks and failure handling regression; isolated browser and frontend build.
- [x] Review privacy/grounding boundaries, preserve current case database during reload, verify local live result, write measured handoff.
