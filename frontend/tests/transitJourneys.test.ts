import test from "node:test";
import assert from "node:assert/strict";
import type { UsydCommute, UsydRoute } from "../src/api/catalog.ts";
import {
  transitJourneys,
  itineraryLabel,
} from "../src/features/real-data/transitJourneys.ts";
import {
  selectedCommute,
  commuteChoices,
} from "../src/features/real-data/commuteSummary.ts";
const route = (patch: Partial<UsydRoute> = {}): UsydRoute => ({
  status: "planned",
  duration_minutes: 50,
  source_url: "https://opendata.transport.nsw.gov.au/",
  queried_at: new Date().toISOString(),
  transit_modes: ["train", "bus"],
  transfers: 1,
  legs: [
    { mode: "walk", duration_minutes: 5 },
    {
      mode: "train",
      duration_minutes: 25,
      service: "T2",
      from: "Burwood",
      to: "Central",
    },
    {
      mode: "bus",
      duration_minutes: 10,
      service: "412",
      from: "Central",
      to: "Campus",
    },
  ],
  ...patch,
});
const data = (modes: object, transit_options?: UsydRoute[]) =>
  ({ modes, transit_options }) as UsydCommute;

test("a mixed itinerary repeated in three category slots is displayed once without averaging", () => {
  const mixed = route();
  const source = data(
    {
      public_transport: mixed,
      train: structuredClone(mixed),
      bus: structuredClone(mixed),
    },
    [mixed],
  );
  const before = structuredClone(source);
  assert.equal(transitJourneys(source).length, 1);
  assert.equal(itineraryLabel(mixed), "Walk → Train → Bus");
  assert.deepEqual(source, before);
});
test("distinct same-duration services remain separate and fastest valid journey wins", () => {
  const mixed = route();
  const bus = route({
    duration_minutes: 50,
    transit_modes: ["bus"],
    transfers: 0,
    legs: [{ mode: "bus", duration_minutes: 50, service: "440" }],
  });
  const faster = route({
    duration_minutes: 40,
    transit_modes: ["train"],
    legs: [{ mode: "train", duration_minutes: 40, service: "T9" }],
  });
  const source = data({}, [mixed, bus, faster]);
  assert.equal(transitJourneys(source).length, 3);
  assert.equal(selectedCommute(source)?.upper, 40);
  assert.equal(itineraryLabel(bus), "Bus");
});
test("stale or invalid options and location-only estimates never invent a transit itinerary", () => {
  assert.equal(
    transitJourneys(
      data({}, [
        route({ queried_at: "2000-01-01T00:00:00Z" }),
        route({ duration_minutes: -1 }),
        route({ duration_minutes: NaN }),
      ]),
    ).length,
    0,
  );
  const source = {
    modes: {},
    estimates: { public_transport: { lower_minutes: 40, upper_minutes: 60 } },
  } as UsydCommute;
  assert.equal(transitJourneys(source).length, 0);
  assert.equal(selectedCommute(source)?.upper, 60);
});
test("missing service/segment evidence stays unspecified and selection honours filtered route", () => {
  assert.equal(
    itineraryLabel(route({ transit_modes: [], legs: undefined })),
    "Public transport route",
  );
  const selected = {
    ...route({ duration_minutes: 60 }),
    mode: "public_transport",
  };
  const source = {
    ...data({ public_transport: route({ duration_minutes: 40 }) }),
    selected_transit_route: selected,
  } as UsydCommute;
  assert.equal(selectedCommute(source)?.upper, 60);
});
test("new selectors use umbrella modes and retain only an existing legacy includes-mode", () => {
  assert.deepEqual(
    commuteChoices().map((row) => row.value),
    ["public_transport", "drive", "bike", "walk"],
  );
  assert.deepEqual(commuteChoices("train").at(-1), {
    value: "train",
    label: "Includes train",
  });
});

test("recent personal journeys retain their query context instead of borrowing a faster snapshot", () => {
  const personal = route({
    duration_minutes: 60,
    basis: "scheduled_live_query",
  });
  const source = data({ public_transport: personal }, [
    route({ duration_minutes: 40 }),
  ]);
  assert.equal(selectedCommute(source)?.upper, 60);
});

test("distinct boarding stop IDs or walking durations do not collapse", () => {
  const a = route({
    legs: [
      {
        mode: "bus",
        duration_minutes: 40,
        service: "440",
        from: "Station",
        from_stop_id: "stop-A",
      },
    ],
  });
  const b = structuredClone(a);
  b.legs![0].from_stop_id = "stop-B";
  assert.equal(transitJourneys(data({}, [a, b])).length, 2);
  assert.equal(
    transitJourneys(
      data({}, [
        route({ legs: undefined, walking_minutes: 5 }),
        route({ legs: undefined, walking_minutes: 20 }),
      ]),
    ).length,
    2,
  );
});
test("explicit filtered selection outranks an older personalised mode observation", () => {
  const source = {
    ...data({
      public_transport: route({
        duration_minutes: 40,
        basis: "scheduled_live_query",
        transfers: 2,
      }),
    }),
    selected_transit_route: {
      ...route({ duration_minutes: 60, transfers: 0 }),
      mode: "public_transport",
    },
  } as UsydCommute;
  assert.equal(selectedCommute(source)?.upper, 60);
});
