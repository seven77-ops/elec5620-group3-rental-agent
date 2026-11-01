# Contract form and PDF preview implementation plan

**Goal:** Make direct field entry the primary contract assistant flow and show the populated official PDF after user confirmation.

**Architecture:** Reuse existing validated lease fields, source-bound saves and version-specific PDF export. Group form fields by subject, keep AI inside an optional collapsed panel, and load the exact saved PDF into a modal via a revocable blob URL. No change to PDF contents, backend state model or confirmation requirements.

**Constraints:** Preserve original case records; tests use an isolated runtime. Unknown fields stay empty, signatures remain blank. Preview of a saved version must not imply that unsaved changes have been applied. Retain white/blue Ant Design styling, existing review flow and 360px layout. Browser plugin not available; use repository Playwright workflow. No dependency installation, commits or publication.

- [x] Extend `frontend/e2e/lease-draft.spec.ts`: direct-entry headings, AI optional, confirmed save opens version-specific PDF preview; editing must keep preview on the saved version; failed PDF loads can retry; no extra save on preview. Run against isolated 5195/8015 and observe the missing-preview failure.
- [x] Modify `frontend/src/features/contracts/LeaseDraft.tsx`: visible grouped fields for property, parties, rent/term, payment; optional AI collapse; confirm-fill button; saved preview action and unsaved-edit notice. Reuse existing field labels and save payload.
- [x] Add `frontend/src/features/contracts/LeasePdfPreview.tsx`: immutable saved draft input, same-origin fetch of existing PDF endpoint, loading/error/retry states, abort pending fetch on close/unmount, revoke generated object URLs, version-labeled iframe plus download fallback. Save success opens this preview; preview never writes state.
- [x] Update scoped styles in `frontend/src/styles/app.css` and existing AI/browser tests for the collapsed helper. Run focused e2e, frontend build/API tests and server draft tests. Inspect desktop and mobile screenshots including modal; check console and preserve original user data.
- [x] Update feature documentation, remove isolated test services, and leave original preview running with final frontend hot reload.

**Verification commands:**

```sh
env RENTAL_ASSISTANT_TEST_RUNTIME=/tmp/rental-lease-form-preview .venv/bin/python -m uvicorn server.tests.assistant_demo_app:app --host 127.0.0.1 --port 8015 --log-level warning
env RENTAL_DEV_API_PORT=8015 npm --prefix frontend run dev -- --port 5195
env WEB_TEST_BASE_URL=http://127.0.0.1:5195 PLAYWRIGHT_CHROMIUM_EXECUTABLE='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' npm --prefix frontend run test:e2e -- lease-draft.spec.ts candidate-followup.spec.ts
npm --prefix frontend run build
npm --prefix frontend run test:api
.venv/bin/python -m unittest server.tests.test_lease_drafts
git diff --check
```
