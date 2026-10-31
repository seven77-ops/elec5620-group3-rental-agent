# Contact Agent Implementation Plan

**Goal:** Turn the inspection checklist into an actionable contact drawer with the short entry label “Contact agent”.
**Architecture:** Retain the existing selected-property and contract flows. Use a separate, locally generated enquiry composer keyed by case and listing; no external AI call, sending, booking or persisted personal profile is introduced.
**Stack:** React 19, Ant Design 6, TypeScript, Playwright.

## Constraints
- All authored UI and template text is English; preserve supplied names and questions.
- Display the original listing as the main action only for HTTP(S) URLs.
- Recipient name, preferred time, questions and email are optional. A valid user-supplied email enables an email-client link using the currently edited subject/body.
- Generate locally, let users edit and copy, report copy failures accurately. Re-generation requires explicit confirmation if a draft already exists.
- Checklist starts collapsed and retains its download. Contract actions remain outside the drawer. No booking or delivery status is invented.
- Keep current drafts on drawer close/reopen; reset on case or selected-property changes. Do not persist or auto-send personal content.

## Implementation
- [x] Update candidate follow-up browser tests for the short label, primary listing link, template preparation/edit/copy, collapsed checklist, mobile layout and unchanged saved follow-up facts. Run to observe the missing UI failure.
- [x] Add pure helpers for template creation, HTTP(S) listing validation and validated email-client URLs, with unit tests for no invented details and URL/header encoding.
- [x] Add `InspectionEnquiry.tsx`; update `CandidateFollowup.tsx` and scoped styles. Retain contract buttons in the selected-property banner.
- [x] Update affected selection/full-journey selectors. Run focused browser journeys, frontend unit tests and build. Review the desktop/mobile screenshots and diff.
- [x] Record verification and limitations. Leave unrelated existing work intact; no commit or push is requested.
