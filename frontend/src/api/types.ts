export type Json =
  null | boolean | number | string | Json[] | { [key: string]: Json };
export type Dict = Record<string, Json>;
export interface Profile {
  schema_version: string;
  search_id: string;
  profile_version: number;
  budget: {
    currency: string;
    period: string;
    scope: string;
    includes_bills: boolean;
    preferred: number;
    maximum: number;
    hard_limit: boolean;
  };
  occupants: number;
  rental_mode: string;
  destination_id: string;
  arrival_time: string;
  timezone: string;
  commute: {
    modes: string[];
    preferred_minutes: number;
    maximum_minutes: number;
    hard_limit: boolean;
  };
  move_in_window: { from: string; to: string };
  lease_months: number;
  hard_requirements: string[];
  soft_preferences: Record<string, number>;
  weights: Record<string, number>;
}
export interface Confirmation {
  version: number;
  fingerprint: string;
  profile: Profile;
  confirmed_at: string;
  draft_revision: number;
  source?: string;
}
export interface CaseState {
  case_id: string;
  search_id: string;
  draft: {
    draft_id: string;
    revision: number;
    profile: Profile;
    fingerprint: string;
  };
  confirmations: Confirmation[];
  evaluations: {
    run_id: string;
    profile_version: number;
    created_at: string;
  }[];
  selection: Selection | null;
  reviews: { review_id: string; version: number; status: string }[];
  aftercare_case_id: string | null;
  agent1?: {
    case_id: string;
    session_id: string;
    state: string;
    latest_version: number;
    review_token: string | null;
    draft_revision: number;
    warnings: string[];
    input_mode: string;
    live_llm: boolean;
  };
}
export interface Selection {
  listing_id: string;
  profile_version: number;
  selected_at: string;
  listing_snapshot: Dict;
  [key: string]: unknown;
}
export interface Evidence {
  source_ref?: string;
  observed_at?: string;
  source_name?: string;
  page?: number;
  line?: number;
  quote?: string;
}
export interface Listing {
  listing_id: string;
  status?: string;
  rank: number | null;
  score: number | null;
  weekly_cost?: number | null;
  commute_minutes?: number | null;
  walking_minutes?: number | null;
  reasons?: string[];
  tradeoffs?: string[];
  issues?: string[];
  hard_checks?: Record<string, { status: string; reason: string }>;
  score_breakdown?: Record<string, number | null>;
  evidence_refs?: Record<string, Evidence>;
  last_checked_at?: string;
  [key: string]: unknown;
}
export interface Report {
  profile: Profile;
  profile_version: number;
  search_id: string;
  profile_fingerprint: string;
  recommendation_run_id: string;
  dataset_fingerprint: string;
  as_of: string;
  report_status: string;
  counts: Record<string, number>;
  recommendations: Listing[];
  eligible: Listing[];
  pending_confirmation: Listing[];
  excluded: Listing[];
  duplicates: Dict[];
  effective_weights: Record<string, number>;
  clarification_requests: Json[];
  data_limitations: string[];
}
export interface Evaluation {
  run_id: string;
  report: Report;
  comparison: Dict | null;
  comparison_error?: string | Dict;
  agent1_task_id?: string;
  comparison_source?: string;
}
export interface Review {
  review_id: string;
  version: number;
  status: string;
  status_reason?: string | null;
  as_of: string;
  document: { source_name: string; sha256: string; [key: string]: Json };
  fields: Record<
    string,
    { value: Json; evidence?: Evidence; confidence?: number }
  >;
  findings: Dict[];
  questions?: Dict[] | Dict | null;
  question_list?: Dict | null;
  [key: string]: unknown;
}
export interface DemoConfig {
  mode: string;
  clocks: {
    evaluation: string;
    selection: string;
    contract: string;
    aftercare: string;
  };
  profile_template: Profile;
  tenancy_template: Dict;
  agreement_examples: { id: string; name: string }[];
  capabilities: Json;
}
export interface AftercareCase {
  case_id: string;
  version: number;
  tenancy: Dict;
  plan?: Dict | null;
  bond?: Dict | null;
  reminders?: Dict | null;
  [key: string]: unknown;
}
