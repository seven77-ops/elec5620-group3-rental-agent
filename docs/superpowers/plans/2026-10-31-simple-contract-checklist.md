# Simple contract review checklist

Approved direction: upload a contract, consent to AI processing, then show real counts and two lists: Needs attention and Passed. Unknown checks belong with attention, never with passed results. Remove the main review page's editing, question-list preparation, private-Q&A, comparison, AI candidate application, history and human-review workflow panels. Keep generated-lease drafting separate, original records immutable, source evidence available, and processing consent revocable. Existing private contract chat/search endpoints and consent boundaries remain intact.

- [x] Add a read-only checklist endpoint, with grounded sidecar previews, true counts and failure/unknown handling. Owner: backend agent; server files and backend tests only.
- [x] Build the compact upload/AI/result flow in new frontend components. Use existing upload, consent and AI endpoints; never auto-apply extracted candidates to saved business data.
- [x] Test date-conflict PDF, clean contract, missing fields, failed AI, consent, sources, refresh and mobile layout. Verify existing drafting and private-search APIs still work.
- [x] Update help/examples, refresh only backed-up product help chunks, reload local backend preserving Jev active mode and business records, and report verified outcomes.
