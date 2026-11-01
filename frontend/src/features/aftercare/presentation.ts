import type { Dict, Json } from "../../api/types";

export function missingTenancyDetails(tenancy: Dict): string[] {
  const missing: string[] = [];
  if (!Array.isArray(tenancy.rooms) || !tenancy.rooms.length)
    missing.push("Room details");
  for (const [key, label] of [
    ["carpeted", "Does the property have carpet?"],
    ["outdoor", "Does the property have an outdoor area?"],
    ["furnished", "Is the property furnished?"],
  ])
    if (tenancy[key] == null) missing.push(label);
  if (tenancy.furnished === true) {
    if (!Array.isArray(tenancy.inventory) || !tenancy.inventory.length)
      missing.push("Furniture inventory");
    else if (!tenancy.inventory_confirmed)
      missing.push("Furniture inventory check");
  }
  return missing;
}

export function tenancySource(value: Json | undefined): string {
  if (typeof value !== "string" || !value) return "Not entered";
  if (value.startsWith("user-entered:")) return "Entered by user";
  if (value.startsWith("review:") || value.startsWith("contract-review:"))
    return "Prefilled from contract review";
  if (value.startsWith("selected-listing:"))
    return "Prefilled from selected property";
  if (value.startsWith("synthetic://")) return "Demo information";
  return "Registered source";
}

const evidenceLabels: Record<string, string> = {
  photo: "Photos",
  receipt: "Receipt",
  condition_report: "Condition report",
  deposit_record: "Bond evidence",
  inspection_record: "Inspection record",
  correspondence: "Correspondence",
  outcome: "Outcome record",
  other: "Other information",
};
export function evidenceKind(value: Json | undefined): string {
  return typeof value === "string" && Object.hasOwn(evidenceLabels, value)
    ? evidenceLabels[value]
    : "Other information";
}

export function clarificationMessages(message: string): string[] {
  const messages: string[] = [];
  if (message.includes("Room layout is unknown"))
    messages.push(
      "Add room details before arranging cleaning tasks for each room.",
    );
  if (message.includes("whether carpeted"))
    messages.push("Confirm whether the property has carpet.");
  if (message.includes("whether outdoor"))
    messages.push("Confirm whether there is an outdoor area.");
  if (message.includes("whether the property is furnished"))
    messages.push("Confirm whether the property is furnished.");
  if (message.includes("Furnished inventory"))
    messages.push(
      "The property is furnished. Complete and check the furniture inventory.",
    );
  if (message.includes("A bond reference or deposit record"))
    messages.push(
      "Add a bond reference or link bond evidence before activating follow-up.",
    );
  return messages.length
    ? messages
    : [
        "Check and complete the information required for this action before continuing.",
      ];
}

// Present generated task titles in plain English; preserve user edits.
const taskTitles: Record<string, string> = {
  "Locate incoming condition records; record missing evidence":
    "Find the move-in condition record; explain if it is missing",
  "Check and clean carpet as appropriate; document existing marks":
    "Inspect and clean carpet as needed; record existing marks",
  "Clear belongings and tidy the supplied outdoor areas":
    "Remove personal items from outdoor areas and tidy up",
  "Verify supplied furniture inventory and discrepancies":
    "Check the landlord furniture inventory and any differences",
  "Arrange final meter readings and close or transfer electricity, gas and internet accounts":
    "Arrange final meter readings and close or transfer electricity, gas, and internet accounts",
  "Remove belongings and arrange personal service/address changes":
    "Remove personal belongings, redirect mail, and update your address",
  "Prepare final inspection photos and compare available condition records":
    "Prepare move-out inspection photos and compare with move-in records",
  "Arrange key return and retain a dated receipt":
    "Return keys and keep a dated receipt",
  "Check the bond refund claim on Rental Bonds Online and record its reference":
    "Check the bond refund application in Rental Bonds Online and record its reference",
  "Check your bond record; record any actual outcome yourself":
    "Check bond records and record the actual outcome yourself",
};
export function taskTitle(value: Json | undefined): string {
  if (typeof value !== "string") return "Unnamed task";
  if (Object.hasOwn(taskTitles, value)) return taskTitles[value];
  const room = /^Clean (.+) and record its condition$/.exec(value);
  if (room) return `Clean “${room[1]}” and record its condition`;
  const item = /^Check supplied inventory: (.+)$/.exec(value);
  if (item) return `Check landlord-provided furniture: ${item[1]}`;
  return value;
}

const gapTexts: Record<string, string> = {
  "Baseline condition report unavailable: supply records or document current condition.":
    "No move-in condition report: add a record or photograph the current condition thoroughly before returning keys.",
};
export function planNotes(plan: Dict): string[] {
  const gaps = ((plan.evidence_gaps as string[]) ?? []).map(
    (g) => gapTexts[g] ?? g,
  );
  const questions = ((plan.clarification_requests as string[]) ?? []).flatMap(
    (q) => clarificationMessages(q),
  );
  return [...questions, ...gaps];
}

/** Sydney wall-clock text for an ISO instant, e.g. 2026-11-14 09:00 AEDT. */
export function sydneyTime(value: Json | undefined, withTime = true): string {
  if (typeof value !== "string" || !value) return "Not provided";
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return value;
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-AU", {
      timeZone: "Australia/Sydney",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      timeZoneName: "short",
    })
      .formatToParts(instant)
      .map((p) => [p.type, p.value]),
  );
  const day = `${parts.year}-${parts.month}-${parts.day}`;
  return withTime
    ? `${day} ${parts.hour}:${parts.minute} ${parts.timeZoneName}`
    : day;
}

/** Today's calendar date in Sydney as YYYY-MM-DD. */
export function sydneyToday(): string {
  return sydneyTime(new Date().toISOString(), false);
}

export function reportedEventAt(day: string, clock: string): string {
  return day && day < sydneyTime(clock, false)
    ? sydneyIso(day, "12:00")
    : clock;
}

/** ISO instant for a Sydney wall-clock date and time, with the offset in force then. */
export function sydneyIso(date: string, time = "09:00"): string {
  const probe = new Date(`${date}T${time}:00Z`);
  const name =
    new Intl.DateTimeFormat("en-AU", {
      timeZone: "Australia/Sydney",
      timeZoneName: "longOffset",
    })
      .formatToParts(probe)
      .find((p) => p.type === "timeZoneName")?.value ?? "GMT+10:00";
  const offset = name.replace("GMT", "") || "+00:00";
  return `${date}T${time}:00${offset}`;
}
