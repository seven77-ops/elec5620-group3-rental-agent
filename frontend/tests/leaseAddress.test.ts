import test from "node:test";
import assert from "node:assert/strict";
import { isLocalityQuery } from "../src/features/contracts/leaseAddress.ts";

test("locality and postal-only searches never become a street address", () => {
  const locality = { suburb: "Redfern", state: "NSW", postcode: "2016" };
  for (const query of [
    "Redfern",
    "2016",
    "Redfern 2016",
    "Redfern, NSW 2016",
    " redfern ,  nsw 2016 ",
    "NSW 2016",
  ])
    assert.equal(isLocalityQuery(query, locality), true, query);
  for (const query of [
    "Redfern, Unit 2001",
    "Unit 20, Example Street, Redfern 2016",
    "10 George Street",
  ])
    assert.equal(isLocalityQuery(query, locality), false, query);
});
