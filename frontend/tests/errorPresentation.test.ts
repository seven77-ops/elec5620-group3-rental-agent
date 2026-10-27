import test from "node:test";
import assert from "node:assert/strict";
import { userError } from "../src/components/errorPresentation.ts";
test("profile and selection prerequisites have readable next steps", () => {
  assert.equal(
    userError(
      "unconfirmed_profile",
      "Confirm the exact current saved draft before continuing",
    ).title,
    "先确认租房需求",
  );
  assert.match(
    userError("selection_required", "backend message").message,
    /房源/,
  );
});
test("unknown internal errors are not used as user-facing copy", () => {
  const result = userError(
    "service_unavailable",
    "INTERNAL_BACKEND_DEBUG_MESSAGE",
  );
  assert.doesNotMatch(JSON.stringify(result), /INTERNAL|service_unavailable/);
  assert.match(result.message, /重试/);
});
test("actionable Chinese input messages remain visible", () => {
  assert.equal(
    userError("invalid_input", "结束日期须晚于起租日期。").message,
    "结束日期须晚于起租日期。",
  );
});
