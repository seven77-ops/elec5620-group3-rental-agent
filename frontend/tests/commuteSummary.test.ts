import test from "node:test";
import assert from "node:assert/strict";
import type { UsydCommute } from "../src/api/catalog.ts";
import {
  commuteSummary,
  selectedCommute,
  compactCommute,
  commuteDuration,
} from "../src/features/real-data/commuteSummary.ts";

test("selected commute uses that mode alone and preserves estimate bounds", () => {
  const source = data({
    public_transport: route(28),
    drive: route(4),
    walk: route(90),
  });
  assert.equal(
    selectedCommute(source, "public_transport")?.text,
    "Public transport Approx. 28 minutes",
  );
  assert.equal(
    selectedCommute(source, "walk")?.text,
    "Walking Approx. 90 minutes",
  );
  assert.equal(selectedCommute(source, "train"), null);
  const estimate = selectedCommute(
    data(
      {},
      { public_transport: { lower_minutes: 22.2, upper_minutes: 29.8 } },
    ),
    "public_transport",
  );
  assert.equal(estimate?.text, "Public transport Estimated 22–30 minutes");
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
test("compact commute copy keeps mode, approximation and complete estimate bounds", () => {
  const source = data({ public_transport: route(20), drive: route(8) });
  const transit = selectedCommute(source)!;
  assert.equal(compactCommute(transit), "Transit · ~20 min");
  assert.equal(commuteDuration(transit), "~20 min");
  assert.equal(
    compactCommute(selectedCommute(source, "drive")!),
    "Drive · ~8 min",
  );
  const estimate = selectedCommute(
    data(
      {},
      {
        public_transport: { lower_minutes: 22.2, upper_minutes: 29.8 },
      },
    ),
  )!;
  assert.equal(compactCommute(estimate), "Transit · Est. 22–30 min");
  assert.equal(
    compactCommute(selectedCommute(data({ train: route(45) }), "train")!),
    "Includes train · ~45 min",
  );
});
test("travel summary contains four independent choices and no cross-mode average", () => {
  const summary = commuteSummary(
    data({
      public_transport: route(13),
      bus: route(12),
      drive: route(4),
      bike: route(7),
      walk: route(15),
    }),
  );
  assert.deepEqual(
    summary.items.map((item) => item.value),
    ["public_transport", "drive", "bike", "walk"],
  );
  assert.equal(summary.items[0].minutes, 12);
  assert.equal("average" in summary, false);
});
test("invalid and unavailable references never become zero-minute commutes", () => {
  assert.equal(
    commuteSummary(
      data({
        train: route(0, "unavailable"),
        metro: route(NaN),
        drive: route(-1),
        walk: route(Infinity),
      }),
    ).items.length,
    0,
  );
  assert.equal(commuteSummary().items.length, 0);
});
test("walking over thirty minutes is omitted from comparison but still available when explicitly selected", () => {
  const source = data({
    public_transport: route(30),
    drive: route(20),
    bike: route(40),
    walk: route(180),
  });
  assert.equal(
    commuteSummary(source).items.some((item) => item.value === "walk"),
    false,
  );
  assert.equal(selectedCommute(source, "walk")?.upper, 180);
  assert.equal(commuteSummary(data({ walk: route(30) })).items.length, 1);
  assert.equal(commuteSummary(data({ walk: route(30.1) })).items.length, 0);
});
test("estimate ranges stay intact; supported journeys take precedence without changing source data", () => {
  const source = data(
    { bus: route(12), walk: route(15.1), public_transport: route(null) },
    {
      public_transport: { lower_minutes: 4, upper_minutes: 20 },
      bus: { lower_minutes: 70, upper_minutes: 90 },
    },
  );
  const before = structuredClone(source);
  const summary = commuteSummary(source);
  assert.equal(summary.items[0].estimated, false);
  assert.deepEqual(
    summary.items.map((item) => item.minutes),
    [12, 16],
  );
  assert.deepEqual(source, before);
});

test("overview weights each visible travel category once while retaining mode-specific filtering references", async () => {
  const { commuteOverview } =
    await import("../src/features/real-data/commuteSummary.ts");
  const source = {
    ...data({
      public_transport: route(25),
      train: route(25),
      bus: route(25),
      drive: route(14),
      bike: route(42),
      walk: route(180),
    }),
    selected_transit_route: { ...route(39), mode: "public_transport" },
  } as UsydCommute;
  const before = structuredClone(source);
  const overview = commuteOverview(source, "public_transport");
  assert.deepEqual(
    overview.items.map((row) => [row.value, row.summary.upper]),
    [
      ["public_transport", 39],
      ["drive", 14],
      ["bike", 42],
    ],
  );
  assert.deepEqual(overview.average, {
    lower: 31,
    upper: 31,
    estimated: false,
    count: 3,
  });
  assert.equal(selectedCommute(source, "public_transport")?.upper, 39);
  assert.deepEqual(source, before);
  assert.equal(
    commuteOverview(source, "walk").items.find((row) => row.selected)?.summary
      .upper,
    180,
  );
});
test("overview weights range endpoints without substituting missing values with zero", async () => {
  const { commuteOverview } =
    await import("../src/features/real-data/commuteSummary.ts");
  const source = data(
    { drive: route(20), bike: route(null) },
    { public_transport: { lower_minutes: 35, upper_minutes: 50 } },
  );
  const overview = commuteOverview(source);
  assert.equal(overview.items.length, 2);
  assert.deepEqual(overview.average, {
    lower: 29,
    upper: 39,
    estimated: true,
    count: 2,
  });
  assert.equal(commuteOverview(data({ drive: route(null) })).average, null);
});

test("weighted overview defaults to transit 50, driving 30, cycling 15 and walking 5 percent", async () => {
  const { commuteOverview } =
    await import("../src/features/real-data/commuteSummary.ts");
  const source = data({
    public_transport: route(50),
    drive: route(20),
    bike: route(20),
    walk: route(10),
  });
  const result = commuteOverview(source);
  assert.deepEqual(
    result.items.map((item) => [
      item.value,
      item.baseWeight,
      item.weight,
      item.effectiveWeight,
    ]),
    [
      ["public_transport", 50, 50, 0.5],
      ["drive", 30, 30, 0.3],
      ["bike", 15, 15, 0.15],
      ["walk", 5, 5, 0.05],
    ],
  );
  assert.equal(result.average?.upper, 35);
});
test("long cycling and walking lose influence while missing modes renormalize instead of becoming zero", async () => {
  const { commuteOverview } =
    await import("../src/features/real-data/commuteSummary.ts");
  const result = commuteOverview(
    data({
      public_transport: route(60),
      drive: route(27),
      bike: route(109),
      walk: route(180),
    }),
  );
  assert.equal(result.average?.upper, 50);
  assert.equal(
    result.items.find((item) => item.value === "bike")?.weight,
    3.75,
  );
  assert.ok(
    Math.abs(
      result.items.reduce((sum, item) => sum + item.effectiveWeight, 0) - 1,
    ) < 1e-12,
  );
  assert.equal(
    result.items.some((item) => item.value === "walk"),
    false,
  );
  const longWalk = commuteOverview(data({ walk: route(60) }), "walk");
  assert.equal(longWalk.items[0].weight, 1.25);
  assert.equal(longWalk.items[0].effectiveWeight, 1);
  assert.equal(longWalk.average?.upper, 60);
  assert.equal(
    commuteOverview(data({ bike: route(31), walk: route(16) })).items[0].weight,
    7.5,
  );
  assert.equal(
    commuteOverview(data({ bike: route(31), walk: route(16) })).items[1].weight,
    2.5,
  );
});
