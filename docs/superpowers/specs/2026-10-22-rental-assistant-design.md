# Unified rental assistant

User authorized implementation of conversation intent recognition and a cleaner white/blue UI inspired by Dubai AI Broker Assistant, then clarified that conversation spans Agents 1–4 and preference collection belongs to Agent1.

## Product
- A shared AI租房助手 page, prominent in navigation and available from all workflow stages. Agent1 owns preferences, Agent2 owns listings/comparison/explanation, Agent3/4 requests route to their existing modules without inventing new verified capabilities.
- White surfaces, existing blue #174EA6, restrained borders, conversation history rail, welcome suggestions, message bubbles, a bottom composer and real listing cards. No fake property photos. Condense repeated banners and developer-oriented text into optional details.
- Existing real catalogue, preference versions, immutable evaluations, source URLs and user confirmation gates remain authoritative.

## API contract
All below paths have /api/v1 prefix.
GET /cases/{case_id}/assistant/conversations -> {items: ConversationSummary[]}
POST same path with {} -> Conversation
GET /cases/{case_id}/assistant/conversations/{conversation_id} -> Conversation
POST /cases/{case_id}/assistant/conversations/{conversation_id}/messages with {request_id, expected_revision, message, allow_external_ai:true, listing_ids?:string[]} -> Conversation
POST /cases/{case_id}/assistant/proposals/{proposal_id}/apply with {request_id,confirmed:true} -> {case:CaseState,conversation:Conversation}

ConversationSummary: {conversation_id,title,updated_at,message_count}
Conversation: {conversation_id,case_id,title,revision,messages:AssistantMessage[]}
AssistantMessage: {message_id,role:'user'|'assistant',content,agent:'agent1'|'agent2'|'agent3'|'agent4'|'assistant',created_at,intent?:string,listings:HousingAd[],actions:AssistantAction[],calls?:object[]}
AssistantAction: {type:'apply_preferences'|'navigate'|'save_candidate',label,proposal_id?:string,page?:'preferences'|'recommendations'|'contract'|'aftercare',listing_id?:string,run_id?:string,summary?:string[]}

## Behavior and safety
- Model proposes typed intent and data; server validates and executes only predefined actions. Include query history plus authoritative draft/confirmed profile, bounded current catalogue facts, displayed listing IDs and original card order. Explicitly selected IDs take priority over model references.
- Intents: search, update_preferences, compare, explain, market, select, clarify, contract, aftercare, other. Ambiguous units, contradictory budgets, unsupported facts or unclear references clarify instead of inventing.
- Preferences changes produce a version-bound proposal. Server-derived action.summary exposes full consequential proposed budget/scope/bills/occupancy/housing conditions before approval, especially when initial values are examples. Explicit apply confirms Agent1 draft through its public adapter and generates Agent2 report. Preview/search can show real catalogue matches without changing confirmed preferences. No automatic budget relaxation.
- Core housing facts are beds/baths/parking/advertised weekly rent. Rent scope, bills, availability, commute and other unknowns remain unknown. Studio normalization remains intact.
- All persisted entities scoped to case and conversation; external calls outside SQLite transactions. Revision checks and durable request identity prevent duplicate turns; concurrent/stale responses cannot overwrite newer profile or transcript.
- Model failures are recoverable with real errors, no pretend AI or synthetic listings. Require explicit per-use external-AI consent, keep secrets out of payloads/traces.
- ID-validated backend facts provide cards and comparison arithmetic; generated explanations cannot add or alter listing facts. Clarification uses server-owned questions rather than unchecked model prose. Agent3/4 use navigation handoffs this iteration.

## Verification
Backend tests cover history, scoped IDs, confirmation proposal lifecycle, stale state, retries, malformed model data, ambiguity, comparison, market coverage and failure. Browser tests exercise welcome, chat, proposal confirmation, cards, refresh, manual catalogue, mobile, console and error states. Verify real qwen-plus extraction once using public/generic needs and an isolated case/runtime; no external messages sent to people.
