import type { UsydCommute } from "../../api/catalog.ts";

export const commuteModes = [
  { value: "public_transport", label: "Public transport" },
  { value: "train", label: "Train" },
  { value: "metro", label: "Metro" },
  { value: "bus", label: "Bus" },
  { value: "drive", label: "Driving" },
  { value: "bike", label: "Cycling" },
  { value: "walk", label: "Walking" },
];
const validMinutes = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0;
const MAX_WALK_REFERENCE_MINUTES = 30;

export function selectedCommute(
  data?: UsydCommute | null,
  mode = "public_transport",
) {
  const label = commuteModes.find((item) => item.value === mode)?.label;
  if (!label) return null;
  const route = data?.modes?.[mode];
  const stamp = route?.queried_at ? Date.parse(route.queried_at) : null;
  const lifetime = route?.status === "planned" ? 7 : 30;
  const fresh =
    stamp === null ||
    (Number.isFinite(stamp) &&
      Date.now() >= stamp &&
      Date.now() - stamp <= lifetime * 86400000);
  if (
    route &&
    fresh &&
    ["planned", "routing_estimate", "ok"].includes(route.status) &&
    validMinutes(route.duration_minutes)
  ) {
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

/** Display-only reference. Eligibility continues to use the user's selected mode. */
export function commuteSummary(data?: UsydCommute | null) {
  const items = commuteModes.flatMap((mode) => {
    const route = data?.modes?.[mode.value];
    if (
      route &&
      ["planned", "routing_estimate", "ok"].includes(route.status) &&
      validMinutes(route.duration_minutes)
    ) {
      if (
        mode.value === "walk" &&
        route.duration_minutes > MAX_WALK_REFERENCE_MINUTES
      )
        return [];
      return [
        {
          ...mode,
          minutes: Math.ceil(route.duration_minutes),
          estimated: false,
        },
      ];
    }
    const estimate = data?.estimates?.[mode.value];
    if (
      estimate &&
      validMinutes(estimate.lower_minutes) &&
      validMinutes(estimate.upper_minutes) &&
      estimate.lower_minutes <= estimate.upper_minutes
    ) {
      if (
        mode.value === "walk" &&
        estimate.upper_minutes > MAX_WALK_REFERENCE_MINUTES
      )
        return [];
      return [
        {
          ...mode,
          minutes: Math.round(
            (estimate.lower_minutes + estimate.upper_minutes) / 2,
          ),
          estimated: true,
        },
      ];
    }
    return [];
  });
  return {
    items,
    average: items.length
      ? Math.round(
          items.reduce((sum, item) => sum + item.minutes, 0) / items.length,
        )
      : null,
  };
}
