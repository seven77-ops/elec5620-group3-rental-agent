import { usableRoute } from "./transitJourneys.ts";
import type { UsydCommute } from "../../api/catalog";

/** Upgrade missing building coordinates without replacing a recent personalised trip. */
export function refreshedCommute(
  older: UsydCommute | null | undefined,
  fresh: UsydCommute | null | undefined,
) {
  if (older?.origin || !fresh?.origin) return older;
  const result = { ...fresh, modes: { ...fresh.modes } };
  const campus = "usyd:camperdown-darlington:fisher-library";
  if (older?.destination.id !== campus || fresh.destination.id !== campus)
    return result;
  for (const [mode, route] of Object.entries(older.modes)) {
    const age = Date.now() - Date.parse(route.queried_at ?? "");
    if (
      ["scheduled_live_query", "recent_checked_query"].includes(
        route.basis ?? "",
      ) &&
      age >= 0 &&
      age <= 30 * 60_000 &&
      ["planned", "ok"].includes(route.status) &&
      route.duration_minutes != null &&
      Number.isFinite(route.duration_minutes)
    ) {
      result.modes[mode] = route;
      result.reference_arrival_at =
        route.reference_arrival_at ?? older.reference_arrival_at;
    }
  }
  if (usableRoute(older.selected_transit_route)) {
    result.selected_transit_route = older.selected_transit_route;
    result.transit_options = older.transit_options;
  }
  return result;
}
