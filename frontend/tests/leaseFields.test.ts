import test from "node:test";
import assert from "node:assert/strict";
import {
  applicableLeaseFields,
  missingLeaseFields,
  leaseExtraDefaults,
  applicableLeaseValues,
} from "../src/features/contracts/leaseFields.ts";
import type { LeaseFields } from "../src/api/leaseDraft.ts";

test("contract completion distinguishes both agents and conditional facilities and notice choices", () => {
  const fields = {
    ...leaseExtraDefaults,
    agent_name: "Landlord agency",
    tenant_agent_name: "Tenant representative",
    landlord_email_consent: "yes",
    tenant_email_consent: "no",
    smoke_alarm_type: "battery",
    smoke_battery_replaceable: "yes",
  } as LeaseFields;
  const required = applicableLeaseFields(fields);
  for (const key of [
    "agent_contact",
    "agent_notice_address",
    "tenant_agent_contact",
    "tenant_agent_notice_address",
    "landlord_notice_email",
    "smoke_battery_type",
    "max_occupants",
    "payment_method",
    "tenant_notice_address",
    "water_usage",
  ])
    assert.ok(required.includes(key as keyof LeaseFields), key);
  for (const key of [
    "landlord_notice_address",
    "tenant_notice_email",
    "smoke_backup_type",
  ])
    assert.equal(required.includes(key as keyof LeaseFields), false, key);
  assert.ok(missingLeaseFields(fields).includes("tenant_agent_contact"));
  const plain = applicableLeaseFields({ ...leaseExtraDefaults } as LeaseFields);
  assert.ok(plain.includes("landlord_notice_address"));
  assert.equal(plain.includes("tenant_agent_name"), false);
  const active = applicableLeaseValues({
    ...fields,
    landlord_email_consent: "no",
    landlord_notice_email: "old@example.com",
    smoke_alarm_type: "hardwired",
    smoke_battery_type: "AA",
  });
  assert.equal(active.landlord_notice_email, "");
  assert.equal(active.smoke_battery_type, "");
});
