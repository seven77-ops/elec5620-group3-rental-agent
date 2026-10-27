import test from "node:test";
import assert from "node:assert/strict";
import { usydDirections } from "../src/features/real-data/directions.ts";

test("map links start at the house and use the same campus reference in each mode", () => {
  const home = { address: "25/124 Parramatta Road, Camperdown", postcode: "2050" };
  for (const [mode, expected] of Object.entries({ walk: "walking", bike: "bicycling", drive: "driving", public_transport: "transit", train: "transit", metro: "transit", bus: "transit" })) {
    const link = new URL(usydDirections(home, mode));
    assert.equal(link.origin, "https://www.google.com");
    assert.equal(link.searchParams.get("api"), "1");
    assert.equal(link.searchParams.get("origin"), "25/124 Parramatta Road, Camperdown NSW 2050");
    assert.equal(link.searchParams.get("destination"), "-33.88630396441765,151.190498785334");
    assert.equal(link.searchParams.get("travelmode"), expected);
    assert.equal(link.searchParams.has("key"), false);
  }
});

test("known building coordinates keep Google and in-app routes on the same starting point", () => {
  const home = { address: "25/124 Parramatta Road, Camperdown", postcode: "2050", usyd_commute: { origin: { latitude: -33.886384, longitude: 151.17822 } } };
  assert.equal(new URL(usydDirections(home, "walk")).searchParams.get("origin"), "-33.886384,151.17822");
  home.usyd_commute.origin.latitude = Number.NaN;
  assert.equal(new URL(usydDirections(home, "walk")).searchParams.get("origin"), "25/124 Parramatta Road, Camperdown NSW 2050");
});
