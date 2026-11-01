# Whole-branch review

**Final specification verdict: Approved. Final quality verdict: Approved.**

## Resolved Important finding

- **Contract follow-up writes bypass the stale-context gate advertised by the integrated UI/API.** `server/app/adapters/contracts.py:166–177` checks only that the original consent record remains active and case-bound. It does not check that its selected evidence is still current. In contrast, `review_context` reports `consent_active:false` after the current draft/selection changes (`server/app/adapters/contracts.py:65–72`), and the UI says subsequent analysis/modification is paused (`frontend/src/features/Contract.tsx:215–220`). Focused reproduction: create/confirm/evaluate/select/upload normally; save a changed, unconfirmed profile draft; GET review context returns `consent_active:false`; POST corrections with expected version 1 and rent 650 still returns 200, version 2, `Awaiting Human Review`. The operator page posts decisions without consulting this context (`frontend/src/features/Operator.tsx:52–58`), so this is not exclusively a direct-API discrepancy. Load the saved case and require `selection_is_current(case, origin)` inside the same adapter transaction before invoking corrections/questions/decisions. Add a regression that invalidates the current profile/selection and verifies all follow-ups are blocked while historical reads remain available.

- **Fixed and approved at `860bfad`.** `server/app/adapters/contracts.py:169–178` now loads the saved case and requires both active originating consent and `selection_is_current(case, origin)` before analysis, inside the same serialized transaction. That helper additionally verifies case binding and the exact current confirmed selection. The two new regressions (`server/tests/test_api.py:368–399`) exercise both an unconfirmed edited profile and a different selected listing, assert 403 for corrections/questions/authorized decisions, and verify raw reads, exports and immutable history remain unchanged. No remaining Important findings from the reviewed source.

## Verified strengths and scope

- Interface registration and frontend calls agree for case/profile/evaluation/selection, raw contract uploads, restored consent reads, review context/history, mapped M4 commands and downloads (`server/app/routes.py:8–44`, `frontend/src/api/client.ts:18–65`). Raw upload headers and request identity match exactly (`frontend/src/features/ContractUpload.tsx:85–110`).
- Keys are read only from server settings/local launcher storage, are never returned by config, and frontend operator input is component memory (`scripts/dev.py:17–25`, `server/app/settings.py:14–16`, `server/app/adapters/services.py:32–36`, `frontend/src/features/Operator.tsx:19`). The fixed `qa-local-key` occurs only in explicitly documented synthetic browser-test setup and tests, not product startup defaults. Local storage holds the case reference (`frontend/src/app/App.tsx:78,97,132`).
- Runtime databases/uploads/keys, dependencies, bundles, compiler caches and browser-test artifacts are ignored (`.gitignore:1–13`, `frontend/playwright.config.ts:8`). The untracked-file inventory contained source, lockfiles, docs and intentional design assets; no runtime data/keys were present.
- `git diff --name-only origin/main -- agent2 agent3 agent4 integration` produced no paths: original business modules and cross-agent fixtures are unchanged.
- Main server wiring stays small, domain adapters remain separate, immutable inputs and server-owned operator/M4 identities are preserved (`server/app/main.py:9–16`, `server/app/adapters/profiles.py:68–146`, `server/app/adapters/aftercare.py:34–100`).
- Documentation accurately distinguishes the local synthetic implementation from production authentication, real Agent 1/model integration, external delivery and unperformed NFR/user testing (`docs/frontend/verification.md:79–86`). Final browser/launcher result appendices and copied logs/screenshots are still being completed by the controller; this report does not independently claim those pending deliverables are complete.
- The approved focused frontend review is retained at `/private/tmp/elec5620-frontend-final-review.md`. This review checked integration and boundaries rather than duplicating all frontend inspection/browser tests.

## Launcher lifecycle check

- Read `scripts/dev.py:26–48`: it watches both children, propagates a failing return code, terminates the peer and waits with a kill fallback.
- Ran one isolated temporary-directory probe using the actual launcher source and real `npm run dev`, with a temporary stand-in uvicorn module exiting 2 after two seconds and a Python npm-script descendant waiting for 30 seconds. The launcher exited 2 and the npm descendant was no longer alive. No current service/port was touched and no surviving probe process remained. This resolves the concrete concern that terminating npm might leave its dev child running on this tested setup. It does not claim cross-platform process-management guarantees.

## Validation performed

- Read committed server changes since the approved backend rereview and current uncommitted frontend/docs/scripts; inspected API contract, startup configuration, artifact inventory and selected frontend/server call sites.
- One isolated TestClient probe reproduced only the stale-context mutation doubt described above. `RENTAL_RUNTIME_DIR` was set before module import, keeping module-level initialization in the temporary directory.
- `git diff --check` passed. No full test suite rerun; controller-reported 23 + 71 + 25 + 57 + 6 = 182 passing Python tests are supplied evidence, not newly executed by this reviewer.
- No checkout source, index, HEAD or branch state was modified. This report was written only to `/private/tmp`.

## Final fix-only review

- Read commit `860bfad` for the gate and two regressions. No further test rerun: the parent reports the 25 backend tests pass and is rerunning final validation.
- Inspected the updated Vite configuration: the size-based vendor subdivision has been removed in favor of one stable vendor group. The controller is running production end-to-end validation and will disclose the resulting large-chunk warning; this review does not substitute for that pending browser result. The larger chunk itself is a local-demo performance tradeoff, not a correctness blocker.
