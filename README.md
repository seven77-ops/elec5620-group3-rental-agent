# ELEC5620 Group 3 · Rental Agent

An English rental assistant integrating the group's four agents through a React/TypeScript frontend and a local FastAPI service. The current team trial is **`codex/group-trial-20261022` / draft PR #7**. Do not merge into `main` yet.

Read the [31 October functional update](docs/frontend/2026-10-31-trial-update.md) for optional commute filtering, the compact weighted display, contact enquiries and the revised contract/knowledge flow. Earlier release notes retain their original stage.

Read the [30 October trial handoff](docs/frontend/2026-10-30-trial-update.md) for installation, optional model configuration, current verification and known limits. The [English manual test prompts](docs/frontend/english-manual-test-questions.md) provide a reproducible checklist; they describe expected behaviour, not completed team acceptance.

## Run locally

Use a new directory to protect your own uncommitted work:

```sh
git clone --branch codex/group-trial-20261022 https://github.com/seven77-ops/elec5620-group3-rental-agent.git
cd elec5620-group3-rental-agent
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements-lock.txt
(cd frontend && npm ci)
.venv/bin/python scripts/dev.py
```

Open <http://127.0.0.1:5173>. Python 3.11+ is required; this publication was checked on macOS with Python 3.13 and Node 22. Windows commands are in the handoff. If ports are occupied, use `--web-port 5197 --api-port 8017`. Stop with Ctrl+C.

Business cases, uploads, operator keys and local indexes live in ignored `.runtime/`; dependencies and credentials are not distributed in Git. The app does not provide production multi-user authentication.

## Optional AI and transport

Copy `.env.example` to your own `.env`; keep keys on the backend. New installations default to AI disabled and Jev routing off. The developer's local credentials and active settings are not shared. Manual forms and the bundled catalogue remain available without external models.

- Configure the complete chat-completions URL, model and your own authorized key for business extraction and drafting.
- Jev uses a separate OpenRouter key and `off`, `shadow` or `active` mode. Continuation and validation rules remain authoritative; uncertain or unavailable classification falls back.
- Public/private retrieval supports local keywords and optional embeddings, fusion and reranking. Configure full endpoints matching your own provider workspace. Build public vectors explicitly with `.venv/bin/python scripts/rag_index.py --embed`; ordinary startup does not call an embedding provider.
- Optional TfNSW MCP setup: `.venv/bin/python scripts/setup_tfnsw_mcp.py`. It requires `uv` and Python 3.12+ in its independent environment. The launcher uses POSIX paths; Windows automatic MCP startup has not been verified. The existing direct transport fallback remains available. See the [MCP implementation record](docs/frontend/2026-10-27-tfnsw-mcp.md).

## Current journey

1. **Requirements and housing:** Agent1 confirmation/versioning, 1,000 real advertisement snapshots across 72 areas, complete hard-filtered results, mode-specific reference commute times, explicit working-condition edits and evidence-backed lifestyle ordering. Unknown facts remain unknown; advertisements are not proof of current availability.
2. **Parallel choices:** save/compare favorites or select directly. A single explicit confirmation saves current needs and the selected home atomically. Inspection questions are read-only; contract facts are entered/reviewed on the contract page. The former separate agent-reply form is removed, with historical records retained.
3. **Contract assistance:** prepare an unsigned NSW template draft or upload a TXT/DOCX/PDF for basic review, including standalone document consent without a selected listing. Review summaries and source questions are available in chat. Private search and external processing require separate consent; changes and revocation invalidate old access.
4. **Aftercare:** source-based tenancy prefill, repair-email preview/rewrite/copy and explicit save, provider information and personal service records, move-out planning and bond-fact follow-up. Drafts are not sent, bookings are not submitted and funds are not handled.
5. **Human review and progress:** an operator-key protected inbox shows pending reviews and durable history across local cases. Release decisions unlock system draft preparation only; they do not approve deductions or determine refunds.
6. **Knowledge:** 14 public documents / 153 chunks, comprising NSW guidance/template material, a University of Sydney guide and product help. Answers expose source quotations and conservative fallbacks. Local private-contract indexes stay separate. Retrieval recall and model source checks are not legal or semantic certification.

Newly authored UI, replies and drafts are English. Original messages, names, documents, quotations and saved facts retain their supplied text; multilingual input remains supported. See [AGENTS.md](AGENTS.md) and the [English release record](docs/frontend/2026-10-30-english-product.md).

## Modules and contribution boundaries

| Module | Responsibility | Reference |
| --- | --- | --- |
| Agent1 | Confirmed rental preferences and versions | [Agent1](agent1/) |
| Agent2 | Listing filtering, evidence, comparison and handoff | [Agent2](agent2/README.md) |
| Agent3 | Contract reading, template drafts and review | [Agent3](agent3/README.md) |
| Agent4 | Move-out tasks, bond facts and human-review gates | [Agent4](agent4/) |
| Shared app | Data adaptation, frontend, AI interaction and integration | [Trial handoff](docs/frontend/2026-10-30-trial-update.md) |

Anda's work covers data, adapters, frontend, AI interaction and integration. Members' original Agent1/3/4 modules and the third-party MCP implementation retain their authorship.

## Team trial

[PR #7](https://github.com/seven77-ops/elec5620-group3-rental-agent/pull/7) · [SCRUM-34](https://breezebee64.atlassian.net/browse/SCRUM-34) · [SCRUM-35](https://breezebee64.atlassian.net/browse/SCRUM-35)

Try the complete flow on your own device. Report reproduction steps, expected/actual behaviour and screenshots to Anda in the group; let Anda coordinate changes to the shared integration. Keep individual module work on separate branches. Data refresh, current availability, cross-device checks, formal M3→M4 coordination and team acceptance remain outstanding.

Historical implementation reports are retained under `docs/frontend/`; their earlier language controls, intermediate commute policies and stage-specific counts are not parallel current features or new acceptance results.
