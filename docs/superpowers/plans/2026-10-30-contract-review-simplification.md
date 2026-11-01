# Contract review simplification

The user authorised simplifying the existing contract review screen for tenants,
removing developer information while preserving the main workflows. Continue in
English and retain existing consent, evidence, confirmation and version guards.

## Design

Lead with the saved contract filename, a plain-language review summary and the
issues requiring attention. Show essential contract details together with source
links and a clear edit action. Place private questions after the results. Make
AI-assisted checking optional and secondary; display only verified suggestions,
their source text and explicit confirmation before saving. Failed or stale AI
results explain the next action without exposing internal validation messages.
Group replacement upload, history, refresh and permission withdrawal under
contract management. Remove JSON exports, raw source objects, call diagnostics,
model settings, rule-pack identifiers and internal candidate rejection reasons
from this screen and its drawers. Retain readable review history and human-review
status without implying legal approval.

## Execution and verification

- [x] Add browser regression coverage for a PDF date conflict, hidden developer
  content, failed AI output, source evidence, consent and a 360px viewport.
- [x] Simplify `Contract.tsx`, `ContractUpload.tsx`, `ReviewHistory.tsx` and
  `ai/ContractAi.tsx`. Add a contract-specific presentation helper as needed.
- [x] Allow shared `Failure` to omit diagnostic details only where requested;
  existing screens retain their default behaviour.
- [x] Preserve private contract search and simplify its explanatory copy without
  changing permission or stale-response semantics.
- [x] Update affected browser selectors and verify real AI candidate application,
  consent revocation, review switching, local private search and late responses
  using temporary test runtimes.
- [x] Run the frontend build and unit tests, inspect the live PDF review screen,
  and confirm the saved finding and operator inbox item remain unchanged.

No backend contracts, model evidence rules, existing case records or unrelated
workspace edits are to be rewritten for this presentation change.
