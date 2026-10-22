import test from "node:test";
import assert from "node:assert/strict";
import { propertyFeatures } from "../src/features/real-data/listingPresentation.ts";

test("source feature noise and inherited property names cannot become facilities", () => {
  const source = [
    "Balcony",
    "Balcony / Deck*",
    "Gas",
    "Unverified feature",
    "Apartments & units for rent in Bexley #### Domain",
    "constructor",
    "__proto__",
    "Gas",
  ];
  assert.deepEqual(propertyFeatures(source), [
    "阳台",
    "阳台 / 露台",
    "燃气设施",
  ]);
  assert.equal(source.length, 8);
});
