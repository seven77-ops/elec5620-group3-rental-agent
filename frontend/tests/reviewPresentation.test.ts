import test from "node:test";
import assert from "node:assert/strict";
import type { Review } from "../src/api/types.ts";
import { contractValue } from "../src/features/contracts/reviewPresentation.ts";

test("bond display does not borrow the currency from another amount in a quotation", () => {
  const review = {
    fields: {
      currency: { value: "AUD" },
      bond: {
        value: 3200,
        evidence: { quote: "Rent AUD 800/week; bond USD 3200." },
      },
    },
  } as unknown as Review;
  assert.doesNotMatch(contractValue(review, "bond"), /AUD/);
  assert.match(contractValue(review, "bond"), /3,200/);
});

test("an explicit labelled bond amount retains its own currency", () => {
  const review = {
    fields: {
      currency: { value: "AUD" },
      bond: { value: 3200, evidence: { quote: "Bond: USD 3200" } },
    },
  } as unknown as Review;
  assert.equal(contractValue(review, "bond"), "USD 3,200");
});

test("rent display keeps monthly and per-person pricing rather than implying whole-property weekly rent", () => {
  const review = {
    fields: {
      currency: { value: "AUD" },
      rent_amount: { value: 1800 },
      rent_period: { value: "month" },
      rent_scope: { value: "per_person" },
    },
  } as unknown as Review;
  assert.equal(
    contractValue(review, "rent_amount"),
    "AUD 1,800 / month · Per person",
  );
});
