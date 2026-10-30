import test from "node:test";
import assert from "node:assert/strict";
import { userError } from "../src/components/errorPresentation.ts";
test("profile and selection prerequisites have readable next steps", () => {
  assert.equal(
    userError(
      "unconfirmed_profile",
      "Confirm the exact current saved draft before continuing",
    ).title,
    "Confirm your rental needs first",
  );
  assert.match(
    userError("selection_required", "backend message").message,
    /Save a property candidate/,
  );
});
test("unknown internal errors are not used as user-facing copy", () => {
  const result = userError(
    "service_unavailable",
    "INTERNAL_BACKEND_DEBUG_MESSAGE",
  );
  assert.doesNotMatch(JSON.stringify(result), /INTERNAL|service_unavailable/);
  assert.match(result.message, /Try again|Retry/);
});
test("actionable English input messages remain visible", () => {
  assert.equal(
    userError("invalid_input", "The end date must be after the start date.")
      .message,
    "The end date must be after the start date.",
  );
});

test("legacy Chinese internal errors receive an English fallback", () => {
  const result = userError(
    "service_unavailable",
    "内部服务暂时不可用，请稍后重试。",
  );
  assert.deepEqual(result, {
    title: "Unable to complete this action",
    message: "Try again later or load the latest information to continue.",
  });
  assert.doesNotMatch(JSON.stringify(result), /[\u3400-\u9fff]/);
});
