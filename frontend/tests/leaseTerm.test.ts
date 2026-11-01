import test from "node:test";
import assert from "node:assert/strict";
import {
  addLeaseMonths,
  applyLeaseChange,
} from "../src/features/contracts/leaseTerm.ts";

test("calendar duration uses anniversaries and clamps month ends including leap years", () => {
  assert.equal(addLeaseMonths("2026-10-01", 12), "2027-10-01");
  assert.equal(addLeaseMonths("2026-08-31", 6), "2027-02-28");
  assert.equal(addLeaseMonths("2027-08-31", 6), "2028-02-29");
  assert.equal(addLeaseMonths("2028-02-29", 12), "2029-02-28");
  assert.equal(addLeaseMonths("2026-13-01", 6), null);
});

test("form changes recompute presets, clear periodic end and retain explicit custom dates", () => {
  const fixed = {
    lease_type: "fixed",
    lease_term_months: 12,
    start_date: "2026-10-01",
    end_date: "2027-10-01",
  };
  assert.equal(
    applyLeaseChange(fixed, { lease_term_months: 6 }).end_date,
    "2027-04-01",
  );
  assert.equal(
    applyLeaseChange(fixed, { start_date: "2026-11-01" }).end_date,
    "2027-11-01",
  );
  assert.equal(applyLeaseChange(fixed, { start_date: null }).end_date, null);
  assert.equal(
    applyLeaseChange(fixed, { lease_type: "periodic" }).end_date,
    null,
  );
  assert.equal(
    applyLeaseChange(fixed, { lease_type: "periodic" }).lease_term_months,
    null,
  );
  assert.equal(
    applyLeaseChange(fixed, { end_date: "2028-01-24" }).lease_term_months,
    null,
  );
  assert.equal(
    applyLeaseChange(fixed, { end_date: "2028-01-24" }).end_date,
    "2028-01-24",
  );
  assert.equal(
    applyLeaseChange({ start_date: "2026-10-01" }, { lease_type: "fixed" })
      .lease_term_months,
    12,
  );
});

test("explicit AI custom dates remain custom when the patch also declares fixed lease type", () => {
  const current = {
    lease_type: "fixed",
    lease_term_months: 6,
    start_date: "2026-08-31",
    end_date: "2027-02-28",
  };
  const patch = {
    lease_type: "fixed",
    lease_term_months: null,
    end_date: "2027-08-31",
  };
  const next = applyLeaseChange(current, patch);
  assert.equal(next.lease_term_months, null);
  assert.equal(next.end_date, "2027-08-31");
  assert.equal(
    applyLeaseChange(next, { start_date: "2026-09-01" }).end_date,
    "2027-08-31",
  );
});

test("clearing a lease type removes its hidden preset", () => {
  const next = applyLeaseChange(
    {
      lease_type: "fixed",
      lease_term_months: 6,
      start_date: "2026-10-01",
      end_date: "2027-04-01",
    },
    { lease_type: undefined },
  );
  assert.equal(next.lease_type, undefined);
  assert.equal(next.lease_term_months, null);
});
