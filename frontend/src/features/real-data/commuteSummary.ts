import type { UsydCommute } from "../../api/catalog.ts";

export const commuteModes = [
  { value: "public_transport", label: "公共交通" },
  { value: "train", label: "火车" },
  { value: "metro", label: "地铁" },
  { value: "bus", label: "公交车" },
  { value: "drive", label: "开车" },
  { value: "bike", label: "骑行" },
  { value: "walk", label: "步行" },
];
const validMinutes = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value >= 0;
const MAX_WALK_REFERENCE_MINUTES = 30;

/** Display-only reference. Eligibility continues to use the user's selected mode. */
export function commuteSummary(data?: UsydCommute | null) {
  const items = commuteModes.flatMap((mode) => {
    const route = data?.modes?.[mode.value];
    if (
      route &&
      ["planned", "routing_estimate", "ok"].includes(route.status) &&
      validMinutes(route.duration_minutes)
    ) {
      if (mode.value === "walk" && route.duration_minutes > MAX_WALK_REFERENCE_MINUTES) return [];
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
      if (mode.value === "walk" && estimate.upper_minutes > MAX_WALK_REFERENCE_MINUTES) return [];
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
