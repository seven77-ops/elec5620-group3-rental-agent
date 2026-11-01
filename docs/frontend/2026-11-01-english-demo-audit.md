# English product-chain audit — 1 November 2026

## Scope and findings

Checked authored output in `frontend/src`, `server/app`, all four agent packages,
bundled demo data, public knowledge/help, and the visible history workflow.
Chinese input aliases, regular expressions, multilingual regression fixtures,
developer documentation, historical audit reports, publication titles and quoted
source text are deliberately retained. The pinned official PDF's checkbox export
identifier is an internal template key, not translated product copy.

The reported Chinese address originated in the original synthetic listing
catalogue and Agent 3 example files. The earlier catalogue language assertion
excluded every address field, which missed this system-authored fictional data.
The Agent 3 bundled handoff also retained old Chinese assessment and limitation
copy.

## Changes

- Translate the 30 bundled synthetic listing addresses while retaining their
  fictional/nonexistent designation and all other listing facts.
- Regenerate the Agent 3 bundled selection packet through the current Agent 2
  evaluator/handoff builder. Keep the same profile, selection and clocks; refresh
  computed fingerprints and English checks, reasons and limitations.
- Align the bundled contract/correction sample with the selected fictional
  address. Synchronize Agent 2's executable report examples through the evaluator
  and report renderer; save backups of their previous local contents first.
- Render the exact historical fictional address in English on Human review cards,
  contract details and contract history. Require matching `synthetic_demo`,
  `synthetic-fixture`, `data_kind=synthetic`, listing IDs, original snapshot address
  and fixture number. User addresses and arbitrary Chinese strings do not match.
  The projection never writes back to fields, source quotations or databases.
- Extend catalogue checks to include demo addresses and Agent 3 examples; compare
  the bundled selection packet with a newly built packet to detect future drift.

## Date controls

The remaining browser-native date/datetime controls could show Chinese prompts
under Chinese browser/OS settings even when the page language is English.
Replace date, date/time and time controls with the existing Ant Design English locale and explicit
Australian date formats. Preserve ISO string form values, explicit confirmation,
date bounds and local-time-to-Sydney conversion behavior.

## Preservation

No saved business record, user message, original uploaded file, source quotation,
consent or decision was translated or migrated. No external AI calls are needed.
Live reload preserves the effective Jev mode and verifies logical hashes of all
five local databases before and after restarting.

Date range regression: the first shared-control implementation used
`onCalendarChange`, which fires before the library's final bounds validation.
A browser regression reproduced an out-of-range manual date reaching form state.
Use the validated `onChange` callback instead. The component harness verifies both
bounds, the boundary day, the English Clear action, local datetime strings and
24-hour time strings. The Chinese-browser journey verifies the English calendar
and the service record's persisted ISO date and unchanged Chinese user note.


## Verification results

- English/API/operator backend checks: 72 passed.
- Agent 2: 91 passed; Agent 3: 41 passed; handoff integration: 6 passed.
- Frontend unit tests: 73 passed; build and targeted formatting checks passed.
- Existing English/history/operator/living/My home browser scenarios: 19 passed,
  one pre-existing retired flow skipped. Date-specific final rerun: 2 passed.
  The clearing regression uses the date control's English Clear action.
- Compared regenerated synthetic examples with their pre-change backups: all
  numeric, boolean and null facts are unchanged.
- Live read-only browser check: all 5 matching historical demo cards display the
  English alias, while their original API addresses are retained. The bundled
  demo contract download is English.
- Live reload retained Jev `active` and all five database logical hashes.

The existing Vite vendor-bundle size warning remains; no new dependency was added.
Machine-readable results: `2026-11-01-english-demo-audit-check.json`.
