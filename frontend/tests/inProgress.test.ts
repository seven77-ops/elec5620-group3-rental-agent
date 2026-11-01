import test from "node:test";
import assert from "node:assert/strict";
import { inProgressItems } from "../src/features/living/inProgress.ts";
import type { LivingRecord } from "../src/api/living.ts";

test("in-progress collection retains unfinished bookings even after the service date and excludes setup prompts", () => {
  const record = {
    profile: { address: "Fictional home", agent_phone: "", agent_email: "" },
    repairs: [
      { repair_id: "draft", title: "Fictional repair", status: "prepared" },
      { repair_id: "done", title: "Resolved", status: "resolved" },
    ],
    bookings: [
      {
        booking_id: "past",
        provider_id: "provider",
        status: "booked",
        service_date: "2020-01-01",
      },
      {
        booking_id: "quote",
        provider_id: "provider",
        status: "considering",
        service_date: null,
      },
      {
        booking_id: "completed",
        provider_id: "provider",
        status: "completed",
        service_date: "2020-01-01",
      },
    ],
  } as unknown as LivingRecord;
  const items = inProgressItems(record, []);
  assert.deepEqual(
    items.map((item) => item.id),
    ["draft", "past", "quote"],
  );
  assert.equal(items[1].status, "Booked");
  assert.equal(
    items.some((item) => item.id === "contacts"),
    false,
  );
});
