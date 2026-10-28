import { api } from "./client";
import type { HousingAd, UsydRoute } from "./catalog";
import type { CaseState } from "./types";
import type { LivingProvider } from "./living";
import type { LeaseDraft, LeaseFields, LeaseQuestion } from "./leaseDraft";
import type { AreaContext, AreaAdviceReport, LifestyleTopic } from "./areas";
export interface CommuteDestination {
  id: string;
  label: string;
  latitude: number;
  longitude: number;
  precision: string;
  source_url: string;
}
export interface CommuteRecommendation {
  status: "ready" | "partial" | "unavailable";
  destination: CommuteDestination;
  criteria: RentalBrief;
  queried_at: string;
  date: string;
  arrival_time: string;
  total_matching: number;
  evaluated_count: number;
  query_limit: number;
  matching_count?: number;
  basis?: string;
  areas: {
    suburb: string;
    count: number;
    min_weekly_rent: number;
    max_weekly_rent: number;
    fastest_minutes: number | null;
    verified_route_count: number;
    reasons: string[];
    tradeoffs: string[];
    area_context?: AreaContext;
  }[];
  routes: {
    legs?: UsydRoute["legs"];
    listing_id: string;
    status: "ok" | "unavailable" | "unsupported" | "over_limit";
    duration_minutes: number | null;
    walking_minutes: number | null;
    transfers: number | null;
    departure_at: string | null;
    arrival_at: string | null;
    source_url: string;
    route_url?: string;
    origin_precision: string;
    reason: string;
    mode?: string;
    basis?: string;
    transit_modes?: string[];
    services?: string[];
    distance_m?: number | null;
  }[];
  limitations: string[];
  pending_listings?: HousingAd[];
  estimated_listings?: HousingAd[];
  area_knowledge_coverage?: {
    covered_suburbs: number;
    catalog_suburbs: number;
  };
}
export interface SharedCommuteRecommendation {
  conversation_id: string;
  message: AssistantMessage;
  stale: boolean;
  stale_reasons: string[];
}
export interface HousingComparison {
  basis: string;
  recommended_listing_id: string | null;
  summary: string;
  items: {
    listing_id: string;
    matches: string[];
    tradeoffs: string[];
    to_verify: string[];
  }[];
}
export interface EnquiryDraft {
  listing_id: string;
  address: string;
  subject: string;
  body: string;
  questions: string[];
  source_url: string;
}
export interface LeaseChatProposal {
  proposal_id: string;
  status: "pending" | "applied" | "obsolete";
  fields: LeaseFields;
  patch: Partial<LeaseFields>;
  questions: LeaseQuestion[];
  base_version: number;
}
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
  recommendation_criteria?: RentalBrief;
  recommendation_filters?: import("./catalog").HousingFilters;
  recommendation_catalog_fingerprint?: string;
  recommendation_alternatives?: RecommendationAlternative[];
  recommendation_change?: {
    before_count: number;
    after_count: number;
    changes: {
      field: string;
      label: string;
      before: unknown;
      after: unknown;
    }[];
  };
  transit_information?: {
    topic: "nearby" | "alerts";
    listing_id: string;
    address: string;
    queried_at: string;
    source_url: string;
    stop_name: string | null;
    stops: { id: string; name: string; distance_m: number }[];
    alerts: { title: string; url: string | null }[];
  };
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
  comparison?: HousingComparison;
  task_steps?: {
    label: string;
    status: "completed" | "needs_input";
    detail: string;
  }[];
  enquiry?: EnquiryDraft;
  verification_checklist?: { title: string; items: string[] };
  lease_proposal?: LeaseChatProposal;
  destination_options?: CommuteDestination[];
  commute_recommendation?: CommuteRecommendation;
  area_advice?: AreaAdviceReport;
  commute_question?: { fields: string[] };
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
  lifestyle_priorities?: LifestyleTopic[];
  recommend_areas?: boolean;
  destination_query?: string;
  destination_id?: string;
  arrival_time?: string;
  commute_max_minutes?: number;
  commute_hard_limit?: boolean;
  commute_priority?: "balanced" | "rent" | "commute";
  max_transfers?: number;
  travel_day?: "weekday" | "weekend";
  travel_date?: string;
  commute_mode?:
    "public_transport" | "train" | "metro" | "bus" | "walk" | "drive" | "bike";
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
  allow_external_data?: boolean;
  listing_ids?: string[];
}
const root = (caseId: string) =>
  `/cases/${encodeURIComponent(caseId)}/assistant`;
export type RecommendationPatch = Partial<
  Pick<
    RentalBrief,
    | "budget_amount"
    | "suburb"
    | "min_bedrooms"
    | "min_bathrooms"
    | "min_car_spaces"
    | "commute_mode"
    | "commute_max_minutes"
    | "max_transfers"
  >
>;
export interface RecommendationAlternative {
  id: string;
  label: string;
  count: number;
  additional_count: number;
  patch: RecommendationPatch;
}
export interface RecommendationContext {
  criteria: RentalBrief;
  filters: import("./catalog").HousingFilters;
  total: number;
  alternatives: RecommendationAlternative[];
  catalog_fingerprint: string;
  revision: number;
  suburbs: string[];
}
export const getRecommendationContext = (
  caseId: string,
  conversationId: string,
) =>
  api<RecommendationContext | null>(
    `${root(caseId)}/conversations/${encodeURIComponent(conversationId)}/recommendation-context`,
    undefined,
    { allowNull: true },
  );
export const adjustRecommendation = (
  caseId: string,
  conversationId: string,
  body: {
    request_id: string;
    expected_revision: number;
    expected_profile_fingerprint: string;
    catalog_fingerprint: string;
    confirmed: true;
    patch: RecommendationPatch;
  },
) =>
  api<Conversation>(
    `${root(caseId)}/conversations/${encodeURIComponent(conversationId)}/recommendation-adjustments`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
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
export const getCommuteRecommendation = (caseId: string) =>
  api<SharedCommuteRecommendation | null>(
    `${root(caseId)}/commute-recommendation`,
    undefined,
    { allowNull: true },
  );
export const getAreaAdvice = (caseId: string) =>
  api<SharedCommuteRecommendation | null>(
    `${root(caseId)}/area-advice`,
    undefined,
    { allowNull: true },
  );
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
export const applyAssistantLease = (
  caseId: string,
  conversationId: string,
  proposalId: string,
  body: {
    request_id: string;
    expected_revision: number;
    confirmed: true;
    applicability_confirmed: true;
  },
) =>
  assistantPost<{ draft: LeaseDraft; conversation: Conversation }>(
    `${conversations(caseId)}/${encodeURIComponent(conversationId)}/lease-proposals/${encodeURIComponent(proposalId)}/apply`,
    body,
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
export const saveAssistantNeeds = (
  caseId: string,
  id: string,
  body: WorkspaceRequest & { brief: RentalBrief; confirmed: true },
) =>
  assistantPost<{ case: CaseState; conversation: Conversation }>(
    `${conversations(caseId)}/${encodeURIComponent(id)}/requirements`,
    body,
  );
export const selectAssistantListing = (
  caseId: string,
  id: string,
  body: WorkspaceRequest & {
    listing_id: string;
    confirmed: true;
    allow_external_data?: boolean;
  },
) =>
  assistantPost<{ case: CaseState; conversation: Conversation }>(
    `${conversations(caseId)}/${encodeURIComponent(id)}/selections`,
    body,
  );
