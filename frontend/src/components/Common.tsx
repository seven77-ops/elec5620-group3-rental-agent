import {
  Alert,
  Button,
  Collapse,
  Descriptions,
  Drawer,
  Empty,
  Spin,
  Tag,
} from "antd";
import type { ReactNode } from "react";
import { ApiError } from "../api/client";
import type { Json } from "../api/types";
import { userError } from "./errorPresentation";
export function Failure({
  error,
  retry,
  showDetails = true,
}: {
  error: unknown;
  retry?: () => void;
  showDetails?: boolean;
}) {
  if (!error) return null;
  const e = error instanceof Error ? error : new Error(String(error));
  const readable = userError(
    e instanceof ApiError ? e.code : undefined,
    e.message,
  );
  return (
    <Alert
      className="error-message"
      type="error"
      showIcon
      title={readable.title}
      description={
        <>
          <div>{readable.message}</div>
          {retry && (
            <div>
              <Button onClick={retry}>Retry original action</Button>
            </div>
          )}
          {showDetails && (
            <Collapse
              ghost
              size="small"
              items={[
                {
                  key: "details",
                  label: "View details",
                  children: (
                    <JsonDetails
                      value={{
                        message: e.message,
                        ...(e instanceof ApiError
                          ? {
                              code: e.code,
                              request_id: e.requestId,
                              fields: e.fields,
                              status: e.status,
                            }
                          : {}),
                      }}
                    />
                  ),
                },
              ]}
            />
          )}
        </>
      }
    />
  );
}
export function PageTitle({
  title,
  description,
  extra,
}: {
  title: string;
  description?: string;
  extra?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {extra && <div className="heading-actions">{extra}</div>}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <Spin />
      <span>Loading saved case…</span>
    </div>
  );
}
export function Blank({ text, action }: { text: string; action?: ReactNode }) {
  return (
    <div className="empty-surface">
      <Empty description={text}>{action}</Empty>
    </div>
  );
}
const statusNames: Record<string, string> = {
  Reviewed: "Review complete",
  "Awaiting Human Review": "Awaiting human review",
  "Awaiting Resubmission": "Resubmission required",
  "Degraded Summary Only": "Limited summary only",
  "Questions Ready": "Questions ready",
  Draft: "Draft",
  AwaitingOutcome: "Awaiting outcome",
  UnderReview: "Awaiting human review",
  Resolved: "Outcome confirmed",
  Withdrawn: "Withdrawn",
  eligible: "Eligible",
  pending: "To be confirmed",
  excluded: "Excluded",
  pass: "Pass",
  fail: "Fail",
  unknown: "To be checked",
  done: "Completed",
  pending_confirmation: "To be confirmed",
  open: "Open",
  cancelled: "Cancelled",
  todo: "To do",
  Active: "Active",
  Cancelled: "Cancelled",
  scheduled: "Scheduled",
  delivered: "Delivered",
  suppressed: "Stopped",
  released: "Checked",
  closed_by_tenant: "Closed by tenant",
  current: "Current draft",
  superseded: "Superseded",
};
export function Status({ value }: { value: string }) {
  const color = /Reviewed|Questions Ready|Resolved|eligible|pass|done/.test(
    value,
  )
    ? "cyan"
    : /Review|Resubmission|pending|unknown/.test(value)
      ? "gold"
      : /fail|excluded/.test(value)
        ? "red"
        : "default";
  return <Tag color={color}>{statusNames[value] ?? value}</Tag>;
}
export const labels: Record<string, string> = {
  commute: "Commute",
  cost: "Cost",
  housing: "Housing",
  amenities: "Amenities",
  private_bedroom: "Private bedroom",
  private_bathroom: "Private bathroom",
  furnished: "Furniture",
  laundry: "Laundry",
  kitchen_access: "Kitchen",
  address: "Contract address",
  landlord: "Landlord",
  tenant: "Tenant",
  rent_amount: "Contract rent",
  rent_period: "Rent period",
  rent_scope: "Pricing basis",
  currency: "Currency",
  bond: "Bond",
  start_date: "Lease start",
  end_date: "Lease end",
  signed_date: "Signing date",
  per_person: "Per person",
  per_room: "Per room",
  whole_property: "Whole property",
  private_room: "Private room",
  shared_room: "Shared room",
  student_accommodation: "Student accommodation",
  public_transport: "Public transport",
  walk: "Walk",
  drive: "Drive",
  bike: "Cycle",
  week: "Weekly",
  month: "Monthly",
  fortnight: "Fortnightly",
};
export const label = (key: string) => labels[key] ?? key;
export function text(value: unknown): string {
  if (value == null) return "Not provided";
  if (typeof value === "string") return label(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}
export const money = (value?: number | null) =>
  value == null
    ? "Not provided"
    : `AUD ${value.toLocaleString("en-AU", { maximumFractionDigits: 2 })}`;
export function JsonDetails({ value }: { value: unknown }) {
  return <pre className="json-detail">{JSON.stringify(value, null, 2)}</pre>;
}
export function EvidenceDrawer({
  title,
  open,
  onClose,
  children,
}: {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <Drawer
      title={title}
      open={open}
      onClose={onClose}
      size={640}
      className="evidence-drawer"
    >
      {children}
    </Drawer>
  );
}
export function KeyValues({ data }: { data: Record<string, Json> }) {
  return (
    <Descriptions
      column={1}
      size="small"
      items={Object.entries(data).map(([key, value]) => ({
        key,
        label: label(key),
        children: <span className="break-word">{text(value)}</span>,
      }))}
    />
  );
}
