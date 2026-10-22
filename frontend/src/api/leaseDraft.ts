import { api, post } from "./client";
import { aiPost } from "./ai";
import type { Json } from "./types";
export interface LeaseFields {
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
