import test from "node:test";
import assert from "node:assert/strict";
import {
  planNotes,
  sydneyIso,
  sydneyTime,
  taskTitle,
  tenancySource,
  reportedEventAt,
} from "../src/features/aftercare/presentation.ts";

test("generated task titles are shown in English and user edits are kept", () => {
  assert.equal(
    taskTitle("Arrange key return and retain a dated receipt"),
    "Return keys and keep a dated receipt",
  );
  assert.equal(
    taskTitle("Clean Kitchen and living and record its condition"),
    "Clean “Kitchen and living” and record its condition",
  );
  assert.equal(
    taskTitle("Check supplied inventory: Sofa"),
    "Check landlord-provided furniture: Sofa",
  );
  assert.equal(taskTitle("我自己改的任务"), "我自己改的任务");
  assert.equal(taskTitle("constructor"), "constructor");
});

test("instants are shown as Sydney wall-clock time across daylight saving", () => {
  assert.equal(
    sydneyTime("2026-11-14T09:00:00+11:00"),
    "2026-11-14 09:00 AEDT",
  );
  assert.equal(sydneyTime("2026-06-01T00:00:00Z"), "2026-06-01 10:00 AEST");
  assert.equal(
    sydneyTime("2026-10-29T18:59:12.579173+11:00", false),
    "2026-10-29",
  );
  assert.equal(sydneyTime(null), "Not provided");
});

test("Sydney wall-clock input gets the offset in force on that date", () => {
  assert.equal(sydneyIso("2026-12-15", "10:00"), "2026-12-15T10:00:00+11:00");
  assert.equal(sydneyIso("2026-07-01", "09:30"), "2026-07-01T09:30:00+10:00");
});

test("plan notes and tenancy sources are readable", () => {
  assert.deepEqual(
    planNotes({
      evidence_gaps: [
        "Baseline condition report unavailable: supply records or document current condition.",
      ],
      clarification_requests: [],
    }),
    [
      "No move-in condition report: add a record or photograph the current condition thoroughly before returning keys.",
    ],
  );
  assert.equal(
    tenancySource("contract-review:cr-1@v2"),
    "Prefilled from contract review",
  );
  assert.equal(
    tenancySource("selected-listing:domain:1"),
    "Prefilled from selected property",
  );
});

test("reported events retain the supplied demo clock and use Sydney time for earlier days", () => {
  const clock = "2026-10-15T10:00:00+11:00";
  assert.equal(reportedEventAt("2026-10-15", clock), clock);
  assert.equal(
    reportedEventAt("2026-10-14", clock),
    "2026-10-14T12:00:00+11:00",
  );
});
