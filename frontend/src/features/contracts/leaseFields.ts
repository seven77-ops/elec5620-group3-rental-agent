import type { LeaseFields } from "../../api/leaseDraft";
export const leaseLabels: Record<keyof LeaseFields, string> = {
  suburb: "房屋区域（Suburb）",
  state: "房屋 State",
  postcode: "房屋邮编",
  landlord_notice_suburb: "出租方区域（Suburb）",
  landlord_notice_state: "出租方 State",
  landlord_notice_postcode: "出租方邮编",
  tenant_notice_suburb: "租客区域（Suburb）",
  tenant_notice_state: "租客 State",
  tenant_notice_postcode: "租客邮编",
  agent_notice_suburb: "代理区域（Suburb）",
  agent_notice_state: "代理 State",
  agent_notice_postcode: "代理邮编",
  lease_term_months: "租期时长",
  agreement_date: "拟定签约日期",
  agreement_place: "拟定签约地点",
  landlord_name_2: "第二出租方姓名",
  landlord_residence: "出租方通常居住州或国家",
  landlord_phone: "出租方联系电话",
  electrical_repair_name: "紧急电工姓名 / 公司",
  electrical_repair_phone: "紧急电工电话",
  plumbing_repair_name: "紧急水管工姓名 / 公司",
  plumbing_repair_phone: "紧急水管工电话",
  other_repair_name: "其他紧急维修联系人",
  other_repair_phone: "其他紧急维修电话",
  address: "房屋地址",
  rental_mode: "租约适用范围",
  landlord_name: "出租方姓名",
  landlord_contact: "出租方联系方式",
  landlord_notice_address: "出租方送达地址",
  tenant_names: "租客姓名（每行一名）",
  tenant_contact: "租客联系方式",
  tenant_notice_address: "租客送达地址",
  agent_name: "代理姓名",
  agent_contact: "代理联系方式",
  agent_notice_address: "代理送达地址",
  lease_type: "租期类型",
  start_date: "起租日期",
  end_date: "结束日期",
  rent_amount: "拟定租金（AUD）",
  rent_period: "租金周期",
  bond: "拟定押金（AUD）",
  max_occupants: "约定最多居住人数",
  inclusions: "明确包含的设施",
  payment_method: "付款方式",
  payment_details: "付款说明",
  first_rent_date: "首期租金付款日期",
  rent_due_day: "租金付款日",
};
export const leaseExtraDefaults: Partial<LeaseFields> = Object.fromEntries(
  [
    "suburb",
    "state",
    "postcode",
    "landlord_notice_suburb",
    "landlord_notice_state",
    "landlord_notice_postcode",
    "tenant_notice_suburb",
    "tenant_notice_state",
    "tenant_notice_postcode",
    "agent_notice_suburb",
    "agent_notice_state",
    "agent_notice_postcode",
    "agreement_place",
    "landlord_name_2",
    "landlord_residence",
    "landlord_phone",
    "electrical_repair_name",
    "electrical_repair_phone",
    "plumbing_repair_name",
    "plumbing_repair_phone",
    "other_repair_name",
    "other_repair_phone",
  ].map((key) => [key, ""]),
);
leaseExtraDefaults.lease_term_months = null;
leaseExtraDefaults.agreement_date = null;
export const requiredLeaseFields: (keyof LeaseFields)[] = [
  "rental_mode",
  "address",
  "landlord_name",
  "landlord_contact",
  "landlord_notice_address",
  "tenant_names",
  "tenant_contact",
  "lease_type",
  "start_date",
  "rent_amount",
  "rent_period",
  "bond",
];
export const leaseOptions: Partial<
  Record<keyof LeaseFields, { value: string; label: string }[]>
> = {
  rental_mode: [{ value: "whole_property", label: "新州普通整租住宅" }],
  lease_type: [
    { value: "fixed", label: "固定租期" },
    { value: "periodic", label: "持续租约（无结束日期）" },
  ],
  rent_period: [
    { value: "week", label: "每周" },
    { value: "fortnight", label: "每两周" },
    { value: "month", label: "每月" },
  ],
  payment_method: [
    { value: "bank_transfer", label: "电子银行转账" },
    { value: "centrepay", label: "Centrepay" },
    { value: "other", label: "其他方式" },
  ],
};
export function leaseText(key: keyof LeaseFields, value: unknown) {
  if (key === "lease_term_months")
    return value == null
      ? "自定义日期"
      : value === 6
        ? "6个月"
        : `${Number(value) / 12}年`;
  if (value == null || value === "") return "待补充";
  return (
    leaseOptions[key]?.find((o) => o.value === value)?.label ?? String(value)
  );
}
export function missingLeaseFields(fields: LeaseFields) {
  const required =
    fields.lease_type === "fixed"
      ? [...requiredLeaseFields, "end_date" as const]
      : requiredLeaseFields;
  return required.filter((key) => fields[key] == null || fields[key] === "");
}
