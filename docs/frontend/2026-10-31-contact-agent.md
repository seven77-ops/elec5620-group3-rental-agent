> Current naming is **Contact property agent**. The earlier shorter label below records the implementation history, not another current action. See [current trial handoff](2026-10-31-trial-update.md).

# Contact agent

The selected-property banner and historical chat follow-up actions now use the short label **Contact agent**.

The drawer shows the selected address and advertised weekly rent, followed by a prominent **Open listing & contact agent** link to the original HTTP(S) advertisement. Unsupported or missing links receive an unavailable state. Inspection registration and contact happen on that website; the application does not create a booking.

**Prepare enquiry** creates a local English template using the selected address and optional agent name, viewing availability and questions. No API, profile, backend write or external AI consent is needed. Subject and body remain editable. **Copy message** copies the current edited values and reports clipboard failures. A single user-supplied email enables **Open email app**, with the current subject/body encoded into a `mailto:` URL. Sending remains in the user's email client.

Draft state stays while this screen is mounted, including closing/reopening the drawer. A case or selected-listing change resets the composer; refreshing or leaving the screen discards it. Replacing an existing draft requires confirmation. There is no new saved record or automatic send.

**Inspection checklist** starts collapsed and retains the question download. Lease drafting/review buttons remain in the selected-property banner outside the contact drawer.

The canonical English user guide and distributed public help snapshot were updated. The local public index was backed up and republished after verifying that only `product-guide` changed; all 139 existing vectors were preserved. No case, contract, contact or aftercare records were changed.

## Verification

Browser plugin not available; used the repository's Playwright runner with disposable local servers, synthetic cases and isolated databases.

- New browser regression first failed on the absent Contact agent entry.
- Four contact drawer tests passed, covering desktop/mobile, existing saved follow-up compatibility, chat navigation, collapsed checklist/download, template generation, edited copy/email URLs, invalid email, replace-draft cancellation, close/reopen retention and clipboard failure. Contact preparation produced no API POSTs or saved follow-up facts.
- Frontend unit suite: 52 passed, including four template/link tests. The recipient-encoding regression was observed failing before its fix.
- Product-guide tests: 7 passed.
- Frontend production build passed; existing vendor bundle size warning remains.
- Desktop and 360px mobile screenshots reviewed; no horizontal overflow.

Contact-only browser report: `/var/folders/5v/___mfyr531d315xl6b7mm99h0000gn/T/rental-full-journey-1plw8tyc/report/index.html`.

Final combined regression: **10 Playwright tests passed** across contact, direct selection/favorites and the complete rental journey (selection → lease PDF/review → aftercare → repairs → move-out/bond). Existing contract-comparison assertions were updated to expand the currently collapsed panel; the catalogue test waits for initial rows before editing filters. Final report: `/var/folders/5v/___mfyr531d315xl6b7mm99h0000gn/T/rental-full-journey-kamp57yu/report/index.html`.

Live read-only checks: frontend 5191, updated contact module and API health 8011 all returned HTTP 200. Vite serves the new component without a service restart or routing configuration change. `git diff --check` passed.

## Naming clarification

Renamed the entry, drawer title and historical chat action presentation to **Contact property agent**, distinguishing the real-estate contact from the AI assistant. The main external link now reads **Open listing & contact property agent**. Updated the help source/snapshot and local public guide index while retaining existing vectors. Product-guide tests (7), production build and diff checks passed; mobile and edited-enquiry browser checks cover the revised labels.
