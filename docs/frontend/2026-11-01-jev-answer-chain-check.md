# Jev answer-chain check - 1 November 2026

Jev is connected to the assistant chat route and is active on the current local service. No application code or effective service configuration was changed for this check.

## Effective configuration and existing live evidence

The running service on port 8011 returned `mode=active`, `configured=true`, `enabled=true`, model `typesafe/jev-1.14`, timeout 3 seconds, confidence threshold 0.65 and margin threshold 0.15. Read-only inspection of routing metadata found recent real housing requests with `source=jev`, `reason=accepted` and successful decisions. No user messages, documents, contacts or keys were printed.

## Actual fresh request

The live backend's effective model configuration was used in a separate process with fresh temporary databases. No saved user records were copied or sent to AI. The question was public: `How do I request repairs in NSW?`

- HTTP 200; route `knowledge`, source `jev`, reason `accepted`.
- Real Jev model `typesafe/jev-1.14-20261014`, confidence 0.99, decision duration 706 ms.
- RAG returned `answered` with three citations; this fresh public index used keywords and reranking.
- Model tasks were `rag_answer`, three `rag_grounded_summary` calls and `rag_summary_check`. No redundant `assistant_intent` call was used for the accepted knowledge route.
- Total request duration was 19.463 seconds. This single observation is not a latency guarantee or a general routing-accuracy benchmark.
- Repeating the identical request returned the same response without additional model calls or routing-audit records.
- The 19 Jev provider/routing regression tests passed, covering active/shadow/off behavior, fallbacks, continuation, consent, mixed tasks and metadata minimisation. These use mock transports separately from the real request above.

Sanitised real-request evidence: [JSON](2026-11-01-jev-answer-chain-real.json).

## Meaning of the integration

The chain is chat message -> state/continuation checks -> optional Jev direction classification -> business extraction or direct RAG -> validation/tool execution -> response. Jev routes a request; the business model and RAG generate the response content. Accepted housing/contract/aftercare routes narrow the intent schema; the existing business validations and explicit saves remain in force.

Explicit short answers, product help and pending task contexts can legitimately bypass Jev. Uncertain or unavailable decisions fall back to the existing model flow. The contract field-extraction button (`lease-drafts/proposals`) and repair-polish button use their own business-model endpoints; their direct calls do not pass through chat routing. Absence of a Jev call for those actions is expected.

Code trace: `frontend/src/api/assistant.ts`, `server/app/assistant/service.py`, `server/app/routing/router.py`, `server/app/routing/jev.py`, `server/app/rag/service.py`. Existing cases and business databases were not mutated by the fresh-request test, and no service restart was needed.
