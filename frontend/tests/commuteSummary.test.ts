import test from "node:test";
import assert from "node:assert/strict";
import type { UsydCommute } from "../src/api/catalog.ts";
import {
  commuteSummary,
  selectedCommute,
} from "../src/features/real-data/commuteSummary.ts";

test("selected commute uses that mode alone and preserves estimate bounds", () => {
  const source = data({
    public_transport: route(28),
    drive: route(4),
    walk: route(90),
  });
  assert.equal(
    selectedCommute(source, "public_transport")?.text,
    "公共交通约 28 分钟",
  );
  assert.equal(selectedCommute(source, "walk")?.text, "步行约 90 分钟");
  assert.equal(selectedCommute(source, "train"), null);
  const estimate = selectedCommute(
    data(
      {},
      { public_transport: { lower_minutes: 22.2, upper_minutes: 29.8 } },
    ),
    "public_transport",
  );
  assert.equal(estimate?.text, "公共交通估算 22–30 分钟");
  assert.equal(estimate?.upper, 30);
  assert.equal(
    selectedCommute(
      data({}, { bus: { lower_minutes: 50, upper_minutes: 20 } }),
      "bus",
    ),
    null,
  );
});

const data = (modes: object, estimates?: object) =>
  ({ modes, estimates }) as UsydCommute;
const route = (duration_minutes: number | null, status = "planned") => ({
  status,
  duration_minutes,
});
test("average uses exactly the visible travel modes and omits missing rail modes", () => {
  const summary = commuteSummary(
    data({
      public_transport: route(13),
      bus: route(12),
      drive: route(4),
      bike: route(7),
      walk: route(15),
      train: route(null),
      metro: route(null),
    }),
  );
  assert.equal(summary.average, 10);
  assert.deepEqual(
    summary.items.map((item) => item.value),
    ["public_transport", "bus", "drive", "bike", "walk"],
  );
});
test("single mode is valid; unavailable, negative and non-finite values never count as zero", () => {
  assert.equal(
    commuteSummary(
      data({
        public_transport: route(17),
        train: route(0, "unavailable"),
        metro: route(NaN),
        drive: route(-1),
        walk: route(Infinity),
      }),
    ).average,
    17,
  );
  assert.equal(commuteSummary(data({ train: route(null) })).average, null);
  assert.equal(commuteSummary().average, null);
});
test("walking over thirty minutes is hidden and excluded from the displayed average", () => {
  const summary = commuteSummary(
    data({
      public_transport: route(30),
      drive: route(20),
      bike: route(40),
      walk: route(180),
    }),
  );
  assert.equal(summary.average, 30);
  assert.equal(
    summary.items.some((item) => item.value === "walk"),
    false,
  );
  assert.equal(commuteSummary(data({ walk: route(30) })).average, 30);
  assert.equal(commuteSummary(data({ walk: route(30.1) })).average, null);
  assert.equal(
    commuteSummary(data({}, { walk: { lower_minutes: 20, upper_minutes: 40 } }))
      .average,
    null,
  );
});
test("coarse ranges contribute their midpoint, valid route takes precedence and source data stays unchanged", () => {
  const source = data(
    { bus: route(12), walk: route(15.1), public_transport: route(null) },
    {
      public_transport: { lower_minutes: 4, upper_minutes: 20 },
      bus: { lower_minutes: 70, upper_minutes: 90 },
      train: { lower_minutes: 30, upper_minutes: 20 },
    },
  );
  const before = structuredClone(source);
  const summary = commuteSummary(source);
  assert.equal(summary.average, 13);
  assert.equal(summary.items[0].estimated, true);
  assert.deepEqual(
    summary.items.map((item) => item.minutes),
    [12, 12, 16],
  );
  assert.deepEqual(source, before);
});
