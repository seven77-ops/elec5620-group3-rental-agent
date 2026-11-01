# Simple contract review: upload, analyse, read two lists

The real-listing contract review page now provides one authorised upload-and-analyse action, followed by actual check totals and two lists: Needs attention and Passed. Source quotations are expandable within each item. Internal enum values are displayed as ordinary English.

The page no longer presents editing/history, field-candidate selection/application, property comparison, private search setup, question-list preparation or human-review blocking panels. Lease drafting remains a separate tab. Private contract search remains available through chat with its existing independent permissions. Processing can be stopped without deleting historical results.

A new read-only checklist endpoint combines source-backed field presence and supported consistency checks with exact-bound, re-validated AI candidates in memory. It does not change the saved review, original document, version, selected property, tenancy or operator workflow. Missing fields, special clauses without a supported conclusion, stale references and incomplete AI analysis remain attention items. No fixed number of checks is invented. Successful field presence is explicitly distinguished from establishing the legal validity of every clause.

The simplified upload uses independently consented document processing, so no property selection is required. AI permission is collected explicitly before the document is sent to the configured service. Upload and model errors retain readable document checks. Existing version, receipt and consent enforcement stays in the underlying APIs.

## Source-grounding repair

A real Qwen run reproduced the former failure: all seven candidates quoted lines that did not equal the PDF's original raw lines. Extraction requests now include the authoritative original line numbers, page numbers and unmodified quotes in source_lines, alongside the original document. Model instructions tell it to copy these references. The exact-source validator remains strict; no invalid candidate is converted into a correction.

A second real-provider run against only the synthetic date-conflict PDF succeeded. All seven candidates passed source validation, and the checklist returned 12 checks: 11 passed, one date-order issue. Both extraction and explanation calls succeeded. Records were created only in a disposable runtime. Metadata: .runtime/contract-checklist-real.json.

## Verification

- 75 focused backend checks passed across checklist, AI API/provider, standalone upload, source analysis and product help. Final checklist wording was checked again: 22 passed.
- 13 browser regressions passed across review, English product and separate private-chat search. Final compact review and mobile checks passed again: 4 passed.
- Full isolated rental journey passed: housing, favourites, selection, lease drafting, simplified contract review, aftercare, repairs, move-out and bond follow-up.
- Frontend production build and whitespace checks passed. Existing Vite vendor-size advisory remains.
- Desktop and 360px previews were inspected. Simulated documents and mocked transport were used except for the explicitly noted synthetic-PDF real-provider smoke check.
- Product help and its canonical snapshot were updated together. Only backed-up product-help index chunks were refreshed; other chunks and vectors were verified unchanged. Local service reloads preserve AI configuration, active Jev mode, ports and saved databases.

Existing uploaded reviews and failed sidecars are historical records. They are not silently regenerated or overwritten. The user can grant a new AI review from the compact result page, or upload another contract.
