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
}: {
  error: unknown;
  retry?: () => void;
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
              <Button onClick={retry}>重试原操作</Button>
            </div>
          )}
          <Collapse
            ghost
            size="small"
            items={[
              {
                key: "details",
                label: "查看详情",
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
      <span>正在读取已保存的案例…</span>
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
  Reviewed: "复核完成",
  "Awaiting Human Review": "等待人工复核",
  "Awaiting Resubmission": "需要重新提交",
  "Degraded Summary Only": "仅有限摘要",
  "Questions Ready": "问题清单已准备",
  Draft: "草稿",
  AwaitingOutcome: "等待结果",
  UnderReview: "待人工审核",
  Resolved: "已确认结果",
  Withdrawn: "已撤回",
  eligible: "合格",
  pending: "待确认",
  excluded: "已排除",
  pass: "通过",
  fail: "未通过",
  unknown: "待核对",
  done: "已完成",
  pending_confirmation: "待确认",
  open: "待处理",
  cancelled: "已取消",
  todo: "待完成",
  Active: "进行中",
  Cancelled: "已取消",
  scheduled: "待提醒",
  delivered: "已提醒",
  suppressed: "已停止",
  released: "已放行",
  closed_by_tenant: "租客已结案",
  current: "当前草稿",
  superseded: "已过期",
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
  commute: "通勤",
  cost: "费用",
  housing: "居住",
  amenities: "设施",
  private_bedroom: "独立卧室",
  private_bathroom: "独立卫浴",
  furnished: "家具",
  laundry: "洗衣设施",
  kitchen_access: "厨房",
  address: "合同地址",
  landlord: "出租方",
  tenant: "租客",
  rent_amount: "合同租金",
  rent_period: "租金周期",
  rent_scope: "计价对象",
  currency: "币种",
  bond: "押金",
  start_date: "租期开始",
  end_date: "租期结束",
  signed_date: "签署日期",
  per_person: "每人",
  per_room: "每房间",
  whole_property: "整套",
  private_room: "独立房间",
  shared_room: "共享房间",
  student_accommodation: "学生公寓",
  public_transport: "公共交通",
  walk: "步行",
  drive: "驾车",
  bike: "骑行",
  week: "每周",
  month: "每月",
  fortnight: "每两周",
};
export const label = (key: string) => labels[key] ?? key;
export function text(value: unknown): string {
  if (value == null) return "未提供";
  if (typeof value === "string") return label(value);
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}
export const money = (value?: number | null) =>
  value == null
    ? "未提供"
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
