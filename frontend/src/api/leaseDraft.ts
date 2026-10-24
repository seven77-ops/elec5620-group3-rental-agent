import { api, post } from "./client";
import { aiPost } from "./ai";
import type { Json } from "./types";
export interface LeaseFields {
  suburb?: string;
  state?: string;
  postcode?: string;
  landlord_notice_suburb?: string;
  landlord_notice_state?: string;
  landlord_notice_postcode?: string;
  tenant_notice_suburb?: string;
  tenant_notice_state?: string;
  tenant_notice_postcode?: string;
  agent_notice_suburb?: string;
  agent_notice_state?: string;
  agent_notice_postcode?: string;
  lease_term_months?: number | null;
  agreement_date?: string | null;
  agreement_place?: string;
  landlord_name_2?: string;
  landlord_residence?: string;
  landlord_phone?: string;
  electrical_repair_name?: string;
  electrical_repair_phone?: string;
  plumbing_repair_name?: string;
  plumbing_repair_phone?: string;
  other_repair_name?: string;
  other_repair_phone?: string;
  address: string;
  landlord_name: string;
  landlord_contact: string;
  landlord_notice_address: string;
  tenant_names: string;
  tenant_contact: string;
  tenant_notice_address: string;
  agent_name: string;
  agent_contact: string;
  agent_notice_address: string;
  rental_mode: "whole_property" | null;
  lease_type: "fixed" | "periodic" | null;
  start_date: string | null;
  end_date: string | null;
  first_rent_date: string | null;
  rent_amount: number | null;
  rent_period: "week" | "fortnight" | "month" | null;
  bond: number | null;
  max_occupants: number | null;
  inclusions: string;
  payment_method: "bank_transfer" | "centrepay" | "other" | null;
  payment_details: string;
  rent_due_day: string;
}
export interface LeaseAddressSuggestion {
  id: string;
  kind: "address" | "locality";
  address: string;
  full_address: string;
  suburb: string;
  state: string;
  postcode: string;
  source_url?: string;
}
export const searchLeaseAddresses = (query: string) =>
  api<{
    items: LeaseAddressSuggestion[];
    source: "local_catalog";
  }>(`/lease-addresses?q=${encodeURIComponent(query)}`);
export interface LeaseLocality {
  id: string;
  suburb: string;
  state: string;
  postcode: string;
}
export const searchLeaseLocalities = (query: string, state: string) =>
  api<{ items: LeaseLocality[]; source: "au_postcodes" }>(
    `/lease-localities?q=${encodeURIComponent(query)}&state=${encodeURIComponent(state.trim().toUpperCase())}`,
  );
export interface LeaseQuestion {
  field: keyof LeaseFields;
  label: string;
  question: string;
}
export interface LeaseTemplate {
  title: string;
  version: string;
  source_page: string;
  source_url: string;
  sha256: string;
}
export interface LeaseContext {
  context_token: string;
  defaults: LeaseFields;
  prefill_sources: Partial<Record<keyof LeaseFields, string>>;
  questions: LeaseQuestion[];
  template: LeaseTemplate;
  sources: {
    case_id: string;
    selection: { listing_id: string; listing_snapshot: Record<string, Json> };
    followup: { version: number };
    profile: { version: number };
  };
}
export interface LeaseDraft {
  draft_id: string;
  case_id: string;
  version: number;
  status: "draft";
  context_token: string;
  fields: LeaseFields;
  sources: LeaseContext["sources"];
  saved_at: string;
  questions: LeaseQuestion[];
  warnings: string[];
  template: LeaseTemplate;
}
export interface LeaseSummary {
  draft_id: string;
  version: number;
  saved_at: string;
  status: "draft";
  source_current: boolean;
  context_token: string;
}
export interface LeaseProposal {
  patch: Partial<LeaseFields>;
  questions: LeaseQuestion[];
  call: { model?: string; simulated?: boolean };
}
export const leaseRoot = (id: string) =>
  `/cases/${encodeURIComponent(id)}/lease-drafts`;
export const getLeaseContext = (id: string) =>
  api<LeaseContext>(leaseRoot(id) + "/context");
export const listLeaseDrafts = (id: string) =>
  api<{ items: LeaseSummary[] }>(leaseRoot(id));
export const getLeaseDraft = (id: string, draft: string, version: number) =>
  api<LeaseDraft>(
    leaseRoot(id) + `/${encodeURIComponent(draft)}?version=${version}`,
  );
export const saveLeaseDraft = (
  id: string,
  body: {
    request_id: string;
    context_token: string;
    expected_version: number;
    confirmed: true;
    applicability_confirmed: true;
    fields: LeaseFields;
    draft_id?: string;
  },
) => post<LeaseDraft>(leaseRoot(id), body);
export const proposeLeaseFields = (
  id: string,
  body: {
    request_id: string;
    context_token: string;
    message: string;
    current_fields: LeaseFields;
    allow_external_ai: true;
  },
) => aiPost<LeaseProposal>(leaseRoot(id) + "/proposals", body);
