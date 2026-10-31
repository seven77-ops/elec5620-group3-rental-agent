import test from "node:test";
import assert from "node:assert/strict";
import { refreshedCommute } from "../src/features/real-data/commuteRefresh.ts";
import type { UsydCommute } from "../src/api/catalog.ts";

test("a recovered house keeps a recent personalised trip and fills other modes from the current catalogue", () => {
  const destination = { id: "usyd:camperdown-darlington:fisher-library" };
  const live = {
    status: "planned",
    basis: "scheduled_live_query",
    duration_minutes: 18,
    queried_at: new Date().toISOString(),
    reference_arrival_at: "2026-10-28T10:00:00+11:00",
  };
  const older = {
    origin: null,
    destination,
    modes: { public_transport: live },
    reference_arrival_at: live.reference_arrival_at,
  } as unknown as UsydCommute;
  const fresh = {
    origin: { latitude: -33.886, longitude: 151.178 },
    destination,
    modes: {
      public_transport: { duration_minutes: 12 },
      walk: { duration_minutes: 17 },
    },
  } as unknown as UsydCommute;
  const result = refreshedCommute(older, fresh)!;
  assert.deepEqual(result.origin, fresh.origin);
  assert.equal(result.modes.public_transport.duration_minutes, 18);
  assert.equal(result.modes.walk.duration_minutes, 17);
  assert.equal(result.reference_arrival_at, live.reference_arrival_at);
  const expired = structuredClone(older);
  expired.modes.public_transport.queried_at = "2000-01-01T00:00:00Z";
  assert.equal(
    refreshedCommute(expired, fresh)!.modes.public_transport.duration_minutes,
    12,
  );
  const otherCampus = {
    ...older,
    destination: { ...destination, id: "camden" },
  } as unknown as UsydCommute;
  assert.equal(
    refreshedCommute(otherCampus, fresh)!.modes.public_transport
      .duration_minutes,
    12,
  );
});

test("coordinate recovery retains the chosen filtered route rather than replacing it with a faster generic route", () => {
  const destination = { id: "usyd:camperdown-darlington:fisher-library" };
  const chosen = {
    status: "planned",
    duration_minutes: 60,
    transfers: 0,
    mode: "public_transport",
    queried_at: new Date().toISOString(),
  };
  const older = {
    origin: null,
    destination,
    modes: {},
    selected_transit_route: chosen,
    transit_options: [chosen],
  } as unknown as UsydCommute;
  const fresh = {
    origin: { latitude: -33.886, longitude: 151.178 },
    destination,
    modes: { public_transport: { duration_minutes: 40 } },
  } as unknown as UsydCommute;
  assert.equal(
    refreshedCommute(older, fresh)!.selected_transit_route?.duration_minutes,
    60,
  );
});
