import type { LeaseFields } from "../../api/leaseDraft";
export const leaseLabels: Record<keyof LeaseFields, string> = {
  tenant_agent_name: "租客代理姓名 / 公司",
  tenant_agent_contact: "租客代理联系方式",
  tenant_agent_notice_address: "租客代理送达地址",
  tenant_agent_notice_suburb: "租客代理区域（Suburb）",
  tenant_agent_notice_state: "租客代理 State",
  tenant_agent_notice_postcode: "租客代理邮编",
  corporation_name: "出租公司登记名称",
  corporation_address: "出租公司营业地址",
  corporation_suburb: "出租公司区域（Suburb）",
  corporation_state: "出租公司 State",
  corporation_postcode: "出租公司邮编",
  water_usage: "是否另付用水费",
  electricity_embedded: "是否为嵌入式供电",
  gas_embedded: "是否为嵌入式供气",
  smoke_alarm_type: "烟雾报警器类型",
  smoke_battery_replaceable: "报警器电池是否可由租客更换",
  smoke_battery_type: "报警器电池型号",
  smoke_backup_replaceable: "备用电池是否可由租客更换",
  smoke_backup_type: "备用电池型号",
  smoke_strata_responsible: "物业法人是否负责报警器维修更换",
  strata_bylaws: "是否适用物业 / 社区规约",
  landlord_email_consent: "出租方是否同意电子送达",
  tenant_email_consent: "租客是否同意电子送达",
  landlord_notice_email: "出租方电子送达邮箱",
  tenant_notice_email: "租客电子送达邮箱",
  bond_recipient: "押金实际交付对象（未交付请留空）",
  suburb: "房屋区域（Suburb）",
  state: "房屋 State",
  postcode: "房屋邮编",
  landlord_notice_suburb: "出租方区域（Suburb）",
  landlord_notice_state: "出租方 State",
  landlord_notice_postcode: "出租方邮编",
  tenant_notice_suburb: "租客区域（Suburb）",
  tenant_notice_state: "租客 State",
  tenant_notice_postcode: "租客邮编",
  agent_notice_suburb: "出租方中介区域（Suburb）",
  agent_notice_state: "出租方中介 State",
  agent_notice_postcode: "出租方中介邮编",
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
  agent_name: "出租方中介姓名 / 公司",
  agent_contact: "出租方中介联系方式（须含电话）",
  agent_notice_address: "出租方中介送达地址",
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
    "tenant_agent_name",
    "tenant_agent_contact",
    "tenant_agent_notice_address",
    "tenant_agent_notice_suburb",
    "tenant_agent_notice_state",
    "tenant_agent_notice_postcode",
    "corporation_name",
    "corporation_address",
    "corporation_suburb",
    "corporation_state",
    "corporation_postcode",
    "smoke_battery_type",
    "smoke_backup_type",
    "landlord_notice_email",
    "tenant_notice_email",
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
  "tenant_names",
  "tenant_contact",
  "lease_type",
  "start_date",
  "rent_amount",
  "rent_period",
  "bond",
  "tenant_notice_address",
  "max_occupants",
  "payment_method",
  "payment_details",
  "first_rent_date",
  "rent_due_day",
  "water_usage",
  "electricity_embedded",
  "gas_embedded",
  "smoke_alarm_type",
  "strata_bylaws",
  "landlord_email_consent",
  "tenant_email_consent",
  "electrical_repair_name",
  "electrical_repair_phone",
  "plumbing_repair_name",
  "plumbing_repair_phone",
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
export function applicableLeaseFields(
  fields: LeaseFields,
): (keyof LeaseFields)[] {
  const required = [...requiredLeaseFields];
  required.push(
    "suburb",
    "state",
    "postcode",
    "tenant_notice_suburb",
    "tenant_notice_state",
    "tenant_notice_postcode",
  );
  if (fields.lease_type === "fixed") required.push("end_date");
  for (const [prefix, parts] of [
    [
      "agent",
      [
        "name",
        "contact",
        "notice_address",
        "notice_suburb",
        "notice_state",
        "notice_postcode",
      ],
    ],
    [
      "tenant_agent",
      [
        "name",
        "contact",
        "notice_address",
        "notice_suburb",
        "notice_state",
        "notice_postcode",
      ],
    ],
    ["corporation", ["name", "address", "suburb", "state", "postcode"]],
  ] as const) {
    const keys = parts.map((part) => `${prefix}_${part}` as keyof LeaseFields);
    if (keys.some((key) => Boolean(fields[key]))) required.push(...keys);
  }
  if (
    ![
      fields.agent_name,
      fields.agent_contact,
      fields.agent_notice_address,
    ].some(Boolean)
  )
    required.push(
      "landlord_notice_address",
      "landlord_notice_suburb",
      "landlord_notice_state",
      "landlord_notice_postcode",
      "landlord_phone",
    );
  if (fields.other_repair_name || fields.other_repair_phone)
    required.push("other_repair_name", "other_repair_phone");
  if (["battery", "both"].includes(fields.smoke_alarm_type ?? "")) {
    required.push("smoke_battery_replaceable");
    if (fields.smoke_battery_replaceable === "yes")
      required.push("smoke_battery_type");
  }
  if (["hardwired", "both"].includes(fields.smoke_alarm_type ?? "")) {
    required.push("smoke_backup_replaceable");
    if (fields.smoke_backup_replaceable === "yes")
      required.push("smoke_backup_type");
  }
  if (fields.strata_bylaws === "yes") required.push("smoke_strata_responsible");
  if (fields.landlord_email_consent === "yes")
    required.push("landlord_notice_email");
  if (fields.tenant_email_consent === "yes")
    required.push("tenant_notice_email");
  return [...new Set(required)];
}
export function missingLeaseFields(fields: LeaseFields) {
  return applicableLeaseFields(fields).filter(
    (key) => fields[key] == null || fields[key] === "",
  );
}

export function applicableLeaseValues(fields: LeaseFields): LeaseFields {
  const result = { ...fields };
  if (result.landlord_email_consent !== "yes")
    result.landlord_notice_email = "";
  if (result.tenant_email_consent !== "yes") result.tenant_notice_email = "";
  if (!["battery", "both"].includes(result.smoke_alarm_type ?? "")) {
    result.smoke_battery_replaceable = null;
    result.smoke_battery_type = "";
  } else if (result.smoke_battery_replaceable !== "yes")
    result.smoke_battery_type = "";
  if (!["hardwired", "both"].includes(result.smoke_alarm_type ?? "")) {
    result.smoke_backup_replaceable = null;
    result.smoke_backup_type = "";
  } else if (result.smoke_backup_replaceable !== "yes")
    result.smoke_backup_type = "";
  if (result.strata_bylaws !== "yes") result.smoke_strata_responsible = null;
  return result;
}

export const yesNoLeaseFields = [
  "water_usage",
  "electricity_embedded",
  "gas_embedded",
  "smoke_battery_replaceable",
  "smoke_backup_replaceable",
  "smoke_strata_responsible",
  "strata_bylaws",
  "landlord_email_consent",
  "tenant_email_consent",
] as const;
for (const key of yesNoLeaseFields) {
  leaseOptions[key] = [
    { value: "yes", label: "是" },
    { value: "no", label: "否" },
  ];
  leaseExtraDefaults[key] = null;
}
leaseOptions.smoke_alarm_type = [
  { value: "hardwired", label: "硬接线" },
  { value: "battery", label: "电池供电" },
  { value: "both", label: "两种都有" },
];
leaseOptions.bond_recipient = [
  { value: "landlord", label: "出租方或其他收款人" },
  { value: "agent", label: "出租方中介" },
  { value: "rbo", label: "NSW Fair Trading / Rental Bonds Online" },
];
leaseExtraDefaults.smoke_alarm_type = null;
leaseExtraDefaults.bond_recipient = null;
