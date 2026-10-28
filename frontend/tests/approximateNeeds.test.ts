import test from "node:test";
import assert from "node:assert/strict";
import {
  approximateNeeds,
  profileNeeds,
  conversationNeeds,
  needsMatch,
} from "../src/features/assistant/needs.ts";
import type { Profile } from "../src/api/types.ts";
import type { Conversation } from "../src/api/assistant.ts";

test("legacy class times never appear in effective rental needs", () => {
  const profile = {
    student_commute: {
      mode: "public_transport",
      maximum_minutes: 30,
      arrival_time: "10:00",
      travel_day: "weekend",
      travel_date: "2000-01-01",
      max_transfers: 1,
    },
  } as Profile;
  const current = profileNeeds(profile);
  assert.equal(current.commute_max_minutes, 30);
  assert.equal(current.max_transfers, 1);
  assert.equal(current.arrival_time, undefined);
  const conversation = {
    dialogue_mode: "search",
    rental_brief: { arrival_time: "10:00" },
    last_search_filters: {
      usyd_arrival_time: "10:00",
      usyd_travel_date: "2000-01-01",
    },
  } as Conversation;
  assert.equal(
    conversationNeeds(conversation, profile).arrival_time,
    undefined,
  );
  assert.equal(
    needsMatch(conversationNeeds(conversation, profile), profile),
    true,
  );
  assert.deepEqual(
    approximateNeeds({
      commute_mode: "bus",
      commute_max_minutes: 30,
      arrival_time: "10:00",
    }),
    { commute_mode: "bus", commute_max_minutes: 30 },
  );
});
