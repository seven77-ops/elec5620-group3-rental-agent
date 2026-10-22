import { api } from "./client";
import type { HousingAd } from "./catalog";
import type { CaseState } from "./types";
import type { LivingProvider } from "./living";
export interface ConversationSummary {
  conversation_id: string;
  title: string;
  updated_at: string;
  message_count: number;
}
export interface AssistantAction {
  type:
    | "apply_preferences"
    | "apply_living_services"
    | "navigate"
    | "save_candidate"
    | "suggestion";
  label: string;
  message?: string;
  proposal_id?: string;
  page?:
    | "preferences"
    | "recommendations"
    | "recommendations?followup=1"
    | "contract"
    | "contract?mode=draft"
    | "contract?mode=review"
    | "aftercare"
    | `aftercare?tab=${"repairs" | "utilities" | "services" | "moveout" | "bond"}`;
  expected_version?: number;
  applied?: boolean;
  superseded?: boolean;
  listing_id?: string;
  run_id?: string;
  summary?: string[];
}
export interface AssistantMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  agent: "agent1" | "agent2" | "agent3" | "agent4" | "assistant";
  created_at: string;
  intent?: string;
  listings: HousingAd[];
  actions: AssistantAction[];
  providers?: LivingProvider[];
  calls?: object[];
}
export interface Conversation {
  conversation_id: string;
  case_id: string;
  title: string;
  revision: number;
  messages: AssistantMessage[];
  rental_brief?: RentalBrief;
  last_search_filters?: import("./catalog").HousingFilters;
  dialogue_mode?: string;
}
export interface RentalBrief {
  suburb?: string | null;
  budget_amount?: number;
  budget_period?: "week" | "month" | "unknown";
  budget_scope?: "per_person" | "per_room" | "whole_property" | "unknown";
  occupants?: number;
  min_bedrooms?: number;
  min_bathrooms?: number;
  min_car_spaces?: number;
  rental_mode?:
    "private_room" | "shared_room" | "whole_property" | "student_accommodation";
}
export interface AssistantTurn {
  request_id: string;
  expected_revision: number;
  message: string;
  allow_external_ai: true;
  listing_ids?: string[];
}
const root = (caseId: string) =>
  `/cases/${encodeURIComponent(caseId)}/assistant`;
const conversations = (caseId: string) => `${root(caseId)}/conversations`;
function assistantPost<T>(path: string, body: unknown) {
  return api<T>(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    { timeoutMs: 120_000 },
  );
}
export const listConversations = (caseId: string) =>
  api<{ items: ConversationSummary[] }>(conversations(caseId));
export const createConversation = (caseId: string) =>
  assistantPost<Conversation>(conversations(caseId), {});
export const getConversation = (caseId: string, id: string) =>
  api<Conversation>(`${conversations(caseId)}/${encodeURIComponent(id)}`);
export const sendAssistantMessage = (
  caseId: string,
  id: string,
  turn: AssistantTurn,
) =>
  assistantPost<Conversation>(
    `${conversations(caseId)}/${encodeURIComponent(id)}/messages`,
    turn,
  );
export const applyAssistantProposal = (
  caseId: string,
  id: string,
  requestId: string,
) =>
  assistantPost<{ case: CaseState; conversation: Conversation }>(
    `${root(caseId)}/proposals/${encodeURIComponent(id)}/apply`,
    { request_id: requestId, confirmed: true },
  );
export interface WorkspaceRequest {
  request_id: string;
  expected_revision: number;
  expected_profile_fingerprint: string;
}
export const prepareAssistantNeeds = (
  caseId: string,
  id: string,
  body: WorkspaceRequest & { brief: RentalBrief },
) =>
  assistantPost<{
    proposal_id: string;
    summary: string[];
    conversation: Conversation;
  }>(`${conversations(caseId)}/${encodeURIComponent(id)}/proposals`, body);
export const selectAssistantListing = (
  caseId: string,
  id: string,
  body: WorkspaceRequest & { listing_id: string; confirmed: true },
) =>
  assistantPost<{ case: CaseState; conversation: Conversation }>(
    `${conversations(caseId)}/${encodeURIComponent(id)}/selections`,
    body,
  );
