import test from "node:test";
import assert from "node:assert/strict";
import { contractProcessingScope } from "../src/features/contracts/contractProcessingScope.ts";

test("an independent document is processable before preferences or selection", () => {
  assert.deepEqual(contractProcessingScope(null, undefined), {
    scope: "document",
    allowed: true,
    synthetic: false,
  });
});
test("selected contracts retain the current-confirmation requirement", () => {
  assert.deepEqual(
    contractProcessingScope(
      { profile_version: 2, data_mode: "real_listings" },
      2,
    ),
    { scope: "selection", allowed: true, synthetic: false },
  );
  assert.equal(
    contractProcessingScope(
      { profile_version: 1, data_mode: "real_listings" },
      2,
    ).allowed,
    false,
  );
  assert.equal(
    contractProcessingScope({ profile_version: 1 }, undefined).allowed,
    false,
  );
  assert.equal(
    contractProcessingScope({ profile_version: 1 }, 1).synthetic,
    true,
  );
});
