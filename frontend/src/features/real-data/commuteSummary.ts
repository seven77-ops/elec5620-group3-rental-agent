import { chosenTransit, usableRoute } from "./transitJourneys.ts";
import type { UsydCommute } from "../../api/catalog.ts";

export const commuteModes = [
  { value: "public_transport", label: "Public transport" },
  { value: "train", label: "Includes train" },
  { value: "metro", label: "Includes metro" },
  { value: "bus", label: "Includes bus" },
  { value: "drive", label: "Driving" },
  { value: "bike", label: "Cycling" },
  { value: "walk", label: "Walking" },
];
export function commuteChoices(current?: string) {
  const primary = commuteModes
    .filter((item) =>
      ["public_transport", "drive", "bike", "walk"].includes(item.value),
    )
    .map((item) =>
      item.value === "public_transport"
        ? { ...item, label: "Public transport (any combination)" }
        : item,
    );
  const legacy = commuteModes.find(
    (item) =>
      item.value === current && !primary.some((row) => row.value === current),
  );
  return legacy ? [...primary, legacy] : primary;
}
const validMinutes = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0;
const MAX_WALK_REFERENCE_MINUTES = 30;

export function selectedCommute(
  data?: UsydCommute | null,
  mode = "public_transport",
) {
  const label = commuteModes.find((item) => item.value === mode)?.label;
  if (!label) return null;
  const route = ["public_transport", "train", "metro", "bus"].includes(mode)
    ? chosenTransit(data, mode)
    : data?.modes?.[mode];
  if (route && usableRoute(route) && validMinutes(route.duration_minutes)) {
    const minutes = Math.ceil(route.duration_minutes);
    return {
      mode,
      label,
      lower: minutes,
      upper: minutes,
      estimated: false,
      text: `${label} Approx. ${minutes} minutes`,
    };
  }
  const estimate = data?.estimates?.[mode];
  const estimatedAt = estimate?.queried_at
    ? Date.parse(estimate.queried_at)
    : null;
  const estimateDays = ["public_transport", "train", "metro", "bus"].includes(
    mode,
  )
    ? 7
    : 30;
  const estimateFresh =
    estimatedAt === null ||
    (Number.isFinite(estimatedAt) &&
      Date.now() >= estimatedAt &&
      Date.now() - estimatedAt <= estimateDays * 86400000);
  if (
    estimate &&
    estimateFresh &&
    validMinutes(estimate.lower_minutes) &&
    validMinutes(estimate.upper_minutes) &&
    estimate.lower_minutes <= estimate.upper_minutes
  ) {
    const lower = Math.floor(estimate.lower_minutes),
      upper = Math.ceil(estimate.upper_minutes);
    return {
      mode,
      label,
      lower,
      upper,
      estimated: true,
      text: `${label} Estimated ${lower}–${upper} minutes`,
    };
  }
  return null;
}

type Commute = NonNullable<ReturnType<typeof selectedCommute>>;

export function commuteDuration(
  summary: Pick<Commute, "estimated" | "lower" | "upper">,
) {
  return summary.estimated
    ? `Est. ${summary.lower}–${summary.upper} min`
    : `~${summary.upper} min`;
}

export function compactCommute(summary: Commute) {
  const label =
    (
      {
        public_transport: "Transit",
        drive: "Drive",
        bike: "Bike",
        walk: "Walk",
      } as Record<string, string>
    )[summary.mode] ?? summary.label;
  return `${label} · ${commuteDuration(summary)}`;
}

/** Four independent travel choices; never average unlike journeys or modes. */
export function commuteSummary(data?: UsydCommute | null) {
  return {
    items: commuteChoices().flatMap((option) => {
      const summary = selectedCommute(data, option.value);
      if (
        !summary ||
        (option.value === "walk" && summary.upper > MAX_WALK_REFERENCE_MINUTES)
      )
        return [];
      return [
        {
          value: option.value,
          label:
            option.value === "public_transport"
              ? "Public transport"
              : option.label,
          minutes: summary.upper,
          estimated: summary.estimated,
        },
      ];
    }),
  };
}

/** Product defaults for a display reference, not measured travel-use frequencies. */
export const COMMUTE_WEIGHTS: Readonly<Record<string, number>> = Object.freeze({
  public_transport: 50,
  drive: 30,
  bike: 15,
  walk: 5,
});
function durationWeight(mode: string, upperMinutes: number) {
  if (mode === "bike")
    return upperMinutes > 60 ? 0.25 : upperMinutes > 30 ? 0.5 : 1;
  if (mode === "walk")
    return upperMinutes > 30 ? 0.25 : upperMinutes > 15 ? 0.5 : 1;
  return 1;
}
/** Display only: weighting never alters mode-specific eligibility or saved preferences. */
export function commuteOverview(
  data?: UsydCommute | null,
  preferredMode = "public_transport",
) {
  const items = commuteChoices().flatMap((option) => {
    const mode =
      option.value === "public_transport" &&
      ["train", "metro", "bus"].includes(preferredMode)
        ? preferredMode
        : option.value;
    const summary = selectedCommute(data, mode);
    if (
      !summary ||
      (mode === "walk" &&
        summary.upper > MAX_WALK_REFERENCE_MINUTES &&
        preferredMode !== "walk")
    )
      return [];
    const baseWeight = COMMUTE_WEIGHTS[option.value];
    const weight = baseWeight * durationWeight(option.value, summary.upper);
    return [
      {
        value: option.value,
        summary,
        selected: mode === preferredMode,
        baseWeight,
        weight,
        effectiveWeight: 0,
      },
    ];
  });
  if (!items.length) return { items, average: null };
  const totalWeight = items.reduce((sum, item) => sum + item.weight, 0);
  for (const item of items) item.effectiveWeight = item.weight / totalWeight;
  const estimated = items.some((item) => item.summary.estimated);
  const lower =
    items.reduce((sum, item) => sum + item.summary.lower * item.weight, 0) /
    totalWeight;
  const upper =
    items.reduce((sum, item) => sum + item.summary.upper * item.weight, 0) /
    totalWeight;
  return {
    items,
    average: items.length
      ? {
          lower: estimated ? Math.floor(lower) : Math.round(lower),
          upper: estimated ? Math.ceil(upper) : Math.round(upper),
          estimated,
          count: items.length,
        }
      : null,
  };
}
