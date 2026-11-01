import test from "node:test";
import assert from "node:assert/strict";
import {
  missingTenancyDetails,
  tenancySource,
  evidenceKind,
} from "../src/features/aftercare/presentation.ts";
test("unknown values remain pending and false values are complete", () => {
  assert.deepEqual(
    missingTenancyDetails({
      rooms: null,
      carpeted: null,
      outdoor: null,
      furnished: null,
    }),
    ["Room details", "Does the property have carpet?", "Does the property have an outdoor area?", "Is the property furnished?"],
  );
  assert.deepEqual(
    missingTenancyDetails({
      rooms: [{ id: "room-1", name: "Bedrooms" }],
      carpeted: false,
      outdoor: false,
      furnished: false,
    }),
    [],
  );
});
test("an empty furnished inventory is not labelled complete even if checked", () => {
  assert.deepEqual(
    missingTenancyDetails({
      rooms: [{}],
      carpeted: true,
      outdoor: false,
      furnished: true,
      inventory: null,
      inventory_confirmed: true,
    }),
    ["Furniture inventory"],
  );
  assert.deepEqual(
    missingTenancyDetails({
      rooms: [{}],
      carpeted: true,
      outdoor: false,
      furnished: true,
      inventory: [{ name: "床" }],
      inventory_confirmed: false,
    }),
    ["Furniture inventory check"],
  );
});
test("sources and evidence have user-facing names without exposing internal references", () => {
  assert.equal(tenancySource("user-entered:tenant-confirmation"), "Entered by user");
  assert.equal(
    tenancySource("review:review-123@1#fields.address"),
    "Prefilled from contract review",
  );
  assert.equal(evidenceKind("deposit_record"), "Bond evidence");
  assert.equal(evidenceKind("other"), "Other information");
  assert.equal(evidenceKind("constructor"), "Other information");
});
