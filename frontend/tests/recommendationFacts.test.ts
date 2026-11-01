import test from "node:test";
import assert from "node:assert/strict";
import type { HousingAd } from "../src/api/catalog.ts";
import { listingReasons } from "../src/features/assistant/recommendationFacts.ts";
const listing = {
  weekly_rent: 820,
  bedrooms: 2,
  bedroom_label: "2",
  bathrooms: 1,
  car_spaces: 0,
  usyd_commute: {
    modes: {
      public_transport: { status: "planned", duration_minutes: 28 },
      drive: { status: "routing_estimate", duration_minutes: 5 },
    },
  },
} as HousingAd;
test("reasons use actual rent difference, selected mode and supplied room conditions", () => {
  const reasons = listingReasons(listing, {
    budget_amount: 900,
    budget_period: "week",
    budget_scope: "whole_property",
    commute_mode: "public_transport",
    min_bedrooms: 2,
  });
  assert.deepEqual(reasons, [
    "Below budget by AUD 80/week",
    "Transit · ~28 min",
    "2 bed, meets your layout needs",
  ]);
});
test("personal budgets, absent modes and unmet floors never become claimed advantages", () => {
  assert.deepEqual(
    listingReasons(listing, {
      budget_amount: 900,
      budget_period: "week",
      budget_scope: "per_person",
      commute_mode: "train",
      min_bedrooms: 3,
    }),
    [],
  );
  assert.deepEqual(listingReasons(listing, {}, { max_weekly_rent: 900 }), [
    "Below weekly rent limit by AUD 80/week",
  ]);
});
