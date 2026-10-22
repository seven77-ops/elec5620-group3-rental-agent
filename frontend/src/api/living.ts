import { api, post } from "./client";
export type Utility = "electricity" | "gas" | "internet" | "water";
export type ProviderCategory =
  "electricity" | "gas" | "internet" | "water" | "removalist" | "cleaner";
export interface LivingProvider {
  id: string;
  name: string;
  categories: ProviderCategory[];
  website: string;
  contact_url: string;
  phone: string | null;
  coverage: string;
  source_url: string;
  checked_on: string;
  notes: string;
}
export interface ProviderDirectory {
  checked_on: string;
  providers: LivingProvider[];
}
export interface LivingProfile {
  address: string;
  suburb: string;
  postcode: string;
  agent_name: string;
  agent_email: string;
  agent_phone: string;
  emergency_phone: string;
  move_out_date: string | null;
  lease_start_date?: string | null;
  lease_end_date?: string | null;
  bedrooms: number | null;
  bathrooms: number | null;
  carpeted: boolean | null;
  has_pets: boolean | null;
  moving_to: string;
  has_elevator: boolean | null;
  own_furniture: string;
  landlord_furniture: string;
  utilities: Record<Utility, string | null>;
  notes: string;
}
export type RepairStatus = "prepared" | "contacted" | "resolved";
export interface RepairValues {
  title: string;
  description: string;
  location: string;
  priority: "normal" | "urgent";
}
export type RepairTone = "standard" | "polite" | "concise";
export interface RepairUpdateValues {
  status?: RepairStatus;
  note?: string;
  email_tone?: RepairTone;
}
export interface RepairEntry extends RepairValues {
  email_tone?: RepairTone;
  updates?: { at: string; note: string; status: RepairStatus }[];
  repair_id: string;
  status: RepairStatus;
  created_at: string;
  email: {
    to: string;
    subject: string;
    body: string;
    delivery_status: "prepared_not_sent";
  };
}
export type BookingStatus =
  "considering" | "contacted" | "booked" | "completed";
export interface BookingValues {
  provider_id: string;
  booking_id?: string;
  service_date: string | null;
  quote_amount: number | null;
  status: BookingStatus;
  notes: string;
}
export interface ServiceBooking extends BookingValues {
  booking_id: string;
  created_at: string;
}
export interface LivingRecord {
  case_id: string;
  version: number;
  profile: LivingProfile;
  repairs: RepairEntry[];
  bookings: ServiceBooking[];
  updated_at: string | null;
  tenancy_source?: Partial<TenancySource> | null;
}
export type LivingWrite = (
  path: string,
  values: LivingProfile | RepairValues | BookingValues | RepairUpdateValues,
  expectedVersion: number,
  onSuccess?: () => void,
) => Promise<boolean>;
const root = (caseId: string) =>
  `/cases/${encodeURIComponent(caseId)}/living-services`;
export const getLivingServices = (caseId: string) =>
  api<LivingRecord>(root(caseId));
export const getLivingProviders = () =>
  api<ProviderDirectory>("/living-providers");
export const writeLivingServices = (
  caseId: string,
  path: string,
  values: unknown,
  expectedVersion: number,
  requestId: string,
) =>
  post<LivingRecord>(`${root(caseId)}${path}`, {
    request_id: requestId,
    expected_version: expectedVersion,
    confirmed: true,
    values,
  });

export interface LivingAttachment {
  attachment_id: string;
  case_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  purpose: "repair" | "receipt" | "moveout";
  repair_id: string | null;
  created_at: string;
  download_url: string;
}
export const getLivingAttachments = (caseId: string) =>
  api<{ items: LivingAttachment[] }>(`${root(caseId)}/attachments`);
export const uploadLivingAttachment = (
  caseId: string,
  file: File,
  purpose: LivingAttachment["purpose"],
  repairId: string | null,
  requestId: string,
) => {
  const query = new URLSearchParams({ purpose });
  if (repairId) query.set("repair_id", repairId);
  return api<LivingAttachment>(`${root(caseId)}/attachments?${query}`, {
    method: "POST",
    headers: {
      "Content-Type": file.type,
      "X-Filename": encodeURIComponent(file.name),
      "X-Request-Id": requestId,
    },
    body: file,
  });
};

export interface TenancySource {
  kind: "lease_draft" | "aftercare";
  id: string;
  version: number;
  label: string;
  token: string;
  current: boolean;
  warning: string;
}
export interface TenancyPreview {
  expected_version: number;
  source: TenancySource | null;
  values: Partial<LivingProfile>;
  previous: Partial<LivingProfile>;
  linked_source: Partial<TenancySource> | null;
  changed: boolean;
}
export const getTenancySource = (caseId: string) =>
  api<TenancyPreview>(`${root(caseId)}/tenancy-source`);
export const importTenancySource = (
  caseId: string,
  preview: TenancyPreview,
  fields: string[],
  requestId: string,
) =>
  post<LivingRecord>(`${root(caseId)}/tenancy-import`, {
    request_id: requestId,
    expected_version: preview.expected_version,
    confirmed: true,
    actual_tenancy_confirmed: true,
    source_token: preview.source?.token,
    fields,
  });
