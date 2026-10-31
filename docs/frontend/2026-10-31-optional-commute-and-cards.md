# Optional commute intake and property cards — 31 October 2026

## Behaviour

- Basic intake collects supplied housing conditions in small steps. A specific area such as Burwood does not require a commute filter.
- After basic intake with any suburb, the assistant offers Add commute filter / Skip commute filter. These prepare explicit replies; the user sends the selected reply.
- Include asks only for missing commute time/mode. Skip survives conversation reload and later budget edits and removes prior commute filters from the working search.
- Existing saved commute constraints remain until explicitly removed. Chat choices and prepared proposals do not silently update the saved profile; the usual confirmation/save is required.
- My rental needs labels commute optional. It does not reintroduce saved filters after a working opt-out; users can add a mode and minute ceiling again later.
- Chat, comparison and commute property cards place details and favorite actions in an equal-width row, followed by one full-width follow-up action. Comparison selection and the confirmed follow-up workflow are retained. Original listing facts and open-plan labels are preserved.

## Verification

- Reproduced the original mobile button offset before the layout fix.
- 48 frontend unit tests and the production build passed.
- 16 existing isolated browser journeys passed: chat, retry, confirmation, favorites, comparison, commute results and requirements syncing.
- Six card/choice/Burwood browser checks passed in the final grouped run. The additional any-suburb skip → reload → save → reopen → add Public transport/45 minutes → save journey passed separately after correcting its dropdown keyboard selection. These cover seven unique new browser scenarios.
- Inspected rendered 360px, 768px and 1440px property cards. Geometry is sampled in one browser frame because the transcript scrolls to new replies.
- 16 focused backend policy/API tests and seven public-guide tests passed. A stable 108-test related run had one exact-state expectation requiring the new explicit include marker; that expectation was updated and its complete five-test workbench module passed, with no production changes after the stable run. Development API/model fixtures use isolated synthetic records and no external provider calls.
- The review found an incidental open-plan label regression; the original catalogue label rendering was restored.

## Local release

The app was backed up and restarted on frontend 5191 / API 8011. Health returned ok and Jev remains configured and active. Logical contents of web.sqlite3, intake.sqlite3 and aftercare.sqlite3 were unchanged. Only reviewed public product-help chunks were refreshed; other chunks and vectors were retained. Operational metadata and the backup location are recorded in .runtime/optional-commute-reload.json. Existing saved conversations are retained; new optional-choice controls appear when the new intake branch is reached.

The presentation interaction examples now explain the optional commute path and a Burwood path without a commute filter.
