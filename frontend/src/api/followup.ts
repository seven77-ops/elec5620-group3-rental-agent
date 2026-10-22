import { api, post } from "./client";
import type { Confirmation, Selection } from "./types";
export interface CandidateFacts {
  stage: "research" | "viewing" | "application";
  availability: "unknown" | "available" | "unavailable";
  rent_amount: number | null;
  rent_period: "unknown" | "week" | "fortnight" | "month";
  rent_scope: "unknown" | "per_person" | "per_room" | "whole_property";
  bills: "unknown" | "included" | "excluded";
  bond: number | null;
  start_date: string | null;
  end_date: string | null;
  landlord: string;
  viewing_note: string;
  source_note: string;
  notes: string;
}
export interface CandidateFollowup {
  case_id: string;
  listing_id: string;
  selection_signature: string;
  version: number;
  facts: CandidateFacts;
  provenance: "user_recorded";
  updated_at: string | null;
}
export interface RealContractContext {
  selection: Selection;
  profile: Confirmation;
  followup: CandidateFollowup;
  captured_at: string;
  checks: {
    key: string;
    label: string;
    source: string;
    reference_value: string | number | null;
    contract_value: string | number | null;
    status: "match" | "different" | "missing" | "basis_unknown";
  }[];
}
const root = (id: string) =>
  `/cases/${encodeURIComponent(id)}/candidate-followup`;
export const getFollowup = (id: string) => api<CandidateFollowup>(root(id));
export const saveFollowup = (
  id: string,
  body: {
    request_id: string;
    expected_version: number;
    selection_signature: string;
    confirmed: true;
    facts: CandidateFacts;
  },
) => post<CandidateFollowup>(root(id), body);
