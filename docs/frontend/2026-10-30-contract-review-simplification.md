# Tenant-facing contract review

The review page now starts with the saved document, a readable summary, items to
check and essential contract details. Each finding and extracted detail keeps
its original-source action. Tenants can correct details without changing the
uploaded document.

Private contract questions follow the results. Local search and cloud consent
remain separate; permission controls become secondary after search is enabled.
AI-assisted checking is optional and collapsed initially. It shows only verified
suggestions, their source text and explicit selection/confirmation before saving.
Failed AI checks retain the saved review and offer a plain-language next step.

Contract management groups history, refresh, processing withdrawal and replacement
upload. History shows readable saved fields, findings and questions. The page and
its drawers no longer show JSON exports/objects, model identifiers, timeouts,
request diagnostics, rejection codes, raw candidate-validation reasons or rule
pack identifiers. The shared error component can suppress diagnostics for these
contract surfaces while preserving its existing behaviour elsewhere.

Backend evidence validation, explicit consent, correction versions, human-review
restrictions and late-response guards are unchanged. The display does not borrow
bond currency from an unrelated amount in a quotation; currency is shown only
when bound to the explicit labelled bond amount. The original evidence remains
available.

## Verification

- Production build passed; the existing vendor-size warning remains.
- 47 frontend unit tests passed, including pricing-scope and currency checks.
- 14 contract/chat/private-search/English/mobile browser journeys passed.
- 9 AI application and regression journeys passed, including switching reviews,
  departing a case, newer corrections and same-version question generation.
- The contract-conflict journey passed through operator approval, question
  preparation, manual correction, saved history and consent withdrawal.
- 31 relevant product-help, standalone-contract, AI API and private-search
  security backend tests passed.
- The actual PDF date-conflict screen was inspected in the running local app.
  Its failed AI analysis now shows a short actionable notice instead of invalid
  candidate cards and internal errors. No external model request was needed to
  verify the presentation.

Public help and its canonical snapshot describe the new controls. The 14 live
product-help chunks were refreshed after a SQLite backup; non-product source
chunks and vectors remained unchanged. Operational details are recorded locally
in `.runtime/contract-simple-help-release.json`.

The frontend development server applies these changes immediately on port 5191.
No backend restart or rewrite of existing contract/business records is required.
