import test from "node:test";
import assert from "node:assert/strict";
import {
  planNotes,
  sydneyIso,
  sydneyTime,
  taskTitle,
  tenancySource,
} from "../src/features/aftercare/presentation.ts";

test("generated task titles are shown in Chinese and user edits are kept", () => {
  assert.equal(
    taskTitle("Arrange key return and retain a dated receipt"),
    "交还钥匙并保留注明日期的收据",
  );
  assert.equal(
    taskTitle("Clean Kitchen and living and record its condition"),
    "清洁「Kitchen and living」并记录状况",
  );
  assert.equal(taskTitle("Check supplied inventory: Sofa"), "核对房东提供的家具：Sofa");
  assert.equal(taskTitle("我自己改的任务"), "我自己改的任务");
  assert.equal(taskTitle("constructor"), "constructor");
});

test("instants are shown as Sydney wall-clock time across daylight saving", () => {
  assert.equal(sydneyTime("2026-11-14T09:00:00+11:00"), "2026-11-14 09:00 AEDT");
  assert.equal(sydneyTime("2026-06-01T00:00:00Z"), "2026-06-01 10:00 AEST");
  assert.equal(sydneyTime("2026-10-29T18:59:12.579173+11:00", false), "2026-10-29");
  assert.equal(sydneyTime(null), "未提供");
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
    ["没有入住时的房屋状况报告：请补充记录，或在交钥匙前全面拍照记录现状。"],
  );
  assert.equal(tenancySource("contract-review:cr-1@v2"), "合同复核预填");
  assert.equal(tenancySource("selected-listing:domain:1"), "已选房源预填");
});
