import type { LeaseFields } from "../../api/leaseDraft";
export const leaseLabels: Record<keyof LeaseFields, string> = {
  tenant_agent_name: "Tenant agent name / company",
  tenant_agent_contact: "Tenant agent contact details",
  tenant_agent_notice_address: "Tenant agent notice address",
  tenant_agent_notice_suburb: "Tenant agent suburb",
  tenant_agent_notice_state: "Tenant agent state",
  tenant_agent_notice_postcode: "Tenant agent postcode",
  corporation_name: "Registered landlord company name",
  corporation_address: "Landlord company business address",
  corporation_suburb: "Landlord company suburb",
  corporation_state: "Landlord company state",
  corporation_postcode: "Landlord company postcode",
  water_usage: "Separate water usage charge",
  electricity_embedded: "Embedded electricity network",
  gas_embedded: "Embedded gas network",
  smoke_alarm_type: "Smoke alarm type",
  smoke_battery_replaceable: "Tenant-replaceable alarm battery",
  smoke_battery_type: "Alarm battery type",
  smoke_backup_replaceable: "Tenant-replaceable backup battery",
  smoke_backup_type: "Backup battery type",
  smoke_strata_responsible:
    "Owners corporation responsible for alarm repair and replacement",
  strata_bylaws: "Strata / community by-laws apply",
  landlord_email_consent: "Landlord agrees to electronic service",
  tenant_email_consent: "Tenant agrees to electronic service",
  landlord_notice_email: "Landlord email for electronic service",
  tenant_notice_email: "Tenant email for electronic service",
  bond_recipient: "Actual bond recipient (leave blank if not paid)",
  suburb: "Property suburb",
  state: "Property state",
  postcode: "Property postcode",
  landlord_notice_suburb: "Landlord suburb",
  landlord_notice_state: "Landlord state",
  landlord_notice_postcode: "Landlord postcode",
  tenant_notice_suburb: "Tenant suburb",
  tenant_notice_state: "Tenant state",
  tenant_notice_postcode: "Tenant postcode",
  agent_notice_suburb: "Landlord agent suburb",
  agent_notice_state: "Landlord agent state",
  agent_notice_postcode: "Landlord agent postcode",
  lease_term_months: "Lease duration",
  agreement_date: "Proposed signing date",
  agreement_place: "Proposed signing location",
  landlord_name_2: "Second landlord name",
  landlord_residence: "Landlord usual state or country of residence",
  landlord_phone: "Landlord phone",
  electrical_repair_name: "Emergency electrician name / company",
  electrical_repair_phone: "Emergency electrician phone",
  plumbing_repair_name: "Emergency plumber name / company",
  plumbing_repair_phone: "Emergency plumber phone",
  other_repair_name: "Other emergency repair contact",
  other_repair_phone: "Other emergency repair phone",
  address: "Property address",
  rental_mode: "Lease scope",
  landlord_name: "Landlord name",
  landlord_contact: "Landlord contact details",
  landlord_notice_address: "Landlord notice address",
  tenant_names: "Tenant names (one per line)",
  tenant_contact: "Tenant contact details",
  tenant_notice_address: "Tenant notice address",
  agent_name: "Landlord agent name / company",
  agent_contact: "Landlord agent contact details (must include phone)",
  agent_notice_address: "Landlord agent notice address",
  lease_type: "Lease type",
  start_date: "Lease start date",
  end_date: "End date",
  rent_amount: "Proposed rent (AUD)",
  rent_period: "Rent period",
  bond: "Proposed bond (AUD)",
  max_occupants: "Maximum agreed occupants",
  inclusions: "Explicitly included amenities",
  payment_method: "Payment method",
  payment_details: "Payment details",
  first_rent_date: "First rent payment date",
  rent_due_day: "Rent due day",
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
  rental_mode: [
    {
      value: "whole_property",
      label: "Standard NSW whole-property residential tenancy",
    },
  ],
  lease_type: [
    { value: "fixed", label: "Fixed term" },
    { value: "periodic", label: "Periodic tenancy (no end date)" },
  ],
  rent_period: [
    { value: "week", label: "Weekly" },
    { value: "fortnight", label: "Fortnightly" },
    { value: "month", label: "Monthly" },
  ],
  payment_method: [
    { value: "bank_transfer", label: "Electronic bank transfer" },
    { value: "centrepay", label: "Centrepay" },
    { value: "other", label: "Other method" },
  ],
};
export function leaseText(key: keyof LeaseFields, value: unknown) {
  if (key === "lease_term_months")
    return value == null
      ? "Custom dates"
      : value === 6
        ? "6 months"
        : `${Number(value) / 12} years`;
  if (value == null || value === "") return "To be completed";
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
    { value: "yes", label: "Yes" },
    { value: "no", label: "No" },
  ];
  leaseExtraDefaults[key] = null;
}
leaseOptions.smoke_alarm_type = [
  { value: "hardwired", label: "Hardwired" },
  { value: "battery", label: "Battery powered" },
  { value: "both", label: "Both" },
];
leaseOptions.bond_recipient = [
  { value: "landlord", label: "Landlord or other recipient" },
  { value: "agent", label: "Landlord agent" },
  { value: "rbo", label: "NSW Fair Trading / Rental Bonds Online" },
];
leaseExtraDefaults.smoke_alarm_type = null;
leaseExtraDefaults.bond_recipient = null;
