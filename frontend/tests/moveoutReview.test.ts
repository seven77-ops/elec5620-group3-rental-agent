import test from "node:test";
import assert from "node:assert/strict";
import { reviewState } from "../src/features/aftercare/issuePresentation.ts";

test("tenant updates return reports to the queue without deleting operator decisions", () => {
  const review = {
    status: "open",
    decisions: [
      {
        decision: "return",
        at: "2026-10-31T03:00:00Z",
        note: "Please add evidence",
      },
    ],
    updates: [],
  };
  assert.equal(reviewState(review).label, "More information needed");
  assert.equal(
    reviewState({ ...review, updates: [{ at: "2026-10-31T03:01:00Z" }] }).label,
    "Awaiting human review",
  );
  assert.equal(
    reviewState({ ...review, status: "released" }).label,
    "Review complete",
  );
  assert.equal(
    reviewState({ ...review, status: "open", decisions: [] }).label,
    "Awaiting human review",
  );
  assert.equal(
    reviewState({
      ...review,
      decisions: [{ decision: "hold", at: "2026-10-31T03:00:00Z" }],
    }).label,
    "In review",
  );
});
