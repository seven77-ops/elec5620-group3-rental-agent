import type { LeaseFields } from "../../api/leaseDraft";

export const leaseDurations = [
  { value: "6", label: "6个月" },
  { value: "12", label: "1年" },
  { value: "24", label: "2年" },
  { value: "36", label: "3年" },
  { value: "60", label: "5年" },
  { value: "custom", label: "自定义日期" },
];
export function addLeaseMonths(
  value: string | null | undefined,
  months: number,
): string | null {
  if (
    !value ||
    !/^\d{4}-\d{2}-\d{2}$/.test(value) ||
    ![6, 12, 24, 36, 60].includes(months)
  )
    return null;
  const [year, month, day] = value.split("-").map(Number);
  const original = new Date(Date.UTC(year, month - 1, day));
  if (
    original.getUTCFullYear() !== year ||
    original.getUTCMonth() !== month - 1 ||
    original.getUTCDate() !== day
  )
    return null;
  const total = year * 12 + month - 1 + months;
  const targetYear = Math.floor(total / 12),
    targetMonth = total % 12;
  if (targetYear > 9999) return null;
  const last = new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate();
  return `${targetYear.toString().padStart(4, "0")}-${(targetMonth + 1).toString().padStart(2, "0")}-${Math.min(day, last).toString().padStart(2, "0")}`;
}
export function applyLeaseChange(
  values: Partial<LeaseFields>,
  changes: Partial<LeaseFields>,
): Partial<LeaseFields> {
  const next = { ...values, ...changes };
  if (next.lease_type === "periodic")
    return { ...next, lease_term_months: null, end_date: null };
  if ("lease_type" in changes && changes.lease_type == null)
    return { ...next, lease_term_months: null };
  if (
    "end_date" in changes &&
    !("start_date" in changes) &&
    !("lease_term_months" in changes)
  )
    next.lease_term_months = null;
  if (
    changes.lease_type === "fixed" &&
    values.lease_type !== "fixed" &&
    !("lease_term_months" in changes) &&
    !("end_date" in changes) &&
    next.lease_term_months == null
  ) {
    next.lease_term_months = next.end_date
      ? ([6, 12, 24, 36, 60].find(
          (n) => addLeaseMonths(next.start_date, n) === next.end_date,
        ) ?? null)
      : 12;
  }
  if (
    next.lease_type === "fixed" &&
    next.lease_term_months != null &&
    ["start_date", "lease_term_months", "lease_type"].some(
      (key) => key in changes,
    )
  ) {
    next.end_date = addLeaseMonths(next.start_date, next.lease_term_months);
  }
  return next;
}
