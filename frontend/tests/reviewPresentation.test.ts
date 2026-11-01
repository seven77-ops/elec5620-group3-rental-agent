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

const legacyAddress = "虚构示例楼 6 号房（不存在的地址）";
const syntheticSelection = {
  data_mode: "synthetic_demo",
  listing_id: "DEMO-006",
  listing_snapshot: {
    listing_id: "DEMO-006",
    source: "synthetic-fixture",
    data_kind: "synthetic",
    source_listing_id: "fixture-6",
    address: legacyAddress,
  },
};

test("legacy bundled demo addresses display in English without rewriting saved facts or quotes", () => {
  const review = {
    fields: {
      address: {
        value: legacyAddress,
        evidence: { quote: "Address: " + legacyAddress },
      },
    },
    selection_evidence: syntheticSelection,
  } as unknown as Review;
  const original = structuredClone(review);
  assert.equal(
    contractValue(review, "address"),
    "Fictional Example Building, Unit 6 (nonexistent demo address)",
  );
  assert.deepEqual(review, original);
});

test("original Chinese addresses are preserved unless they match the bundled synthetic fixture provenance", () => {
  for (const selection of [
    undefined,
    {},
    { ...syntheticSelection, data_mode: "real_listings" },
    { ...syntheticSelection, listing_id: "another-listing" },
    {
      ...syntheticSelection,
      listing_snapshot: {
        ...syntheticSelection.listing_snapshot,
        source: "user",
      },
    },
    {
      ...syntheticSelection,
      listing_snapshot: {
        ...syntheticSelection.listing_snapshot,
        data_kind: "real",
      },
    },
    {
      ...syntheticSelection,
      listing_snapshot: {
        ...syntheticSelection.listing_snapshot,
        source_listing_id: "fixture-9",
      },
    },
  ]) {
    const review = {
      fields: { address: { value: legacyAddress } },
      selection_evidence: selection,
    } as unknown as Review;
    assert.equal(contractValue(review, "address"), legacyAddress);
  }
  const original = "用户原始地址：示例路六号";
  assert.equal(
    contractValue(
      {
        fields: { address: { value: original } },
        selection_evidence: syntheticSelection,
      } as unknown as Review,
      "address",
    ),
    original,
  );
});
