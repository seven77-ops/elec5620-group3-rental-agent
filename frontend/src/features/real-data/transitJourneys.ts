import type { UsydCommute, UsydRoute } from "../../api/catalog.ts";

const transit = ["public_transport", "train", "metro", "bus"];
const names: Record<string, string> = {
  walk: "Walk",
  train: "Train",
  metro: "Metro",
  bus: "Bus",
  ferry: "Ferry",
  light_rail: "Light rail",
};
export function usableRoute(route?: UsydRoute | null) {
  if (
    !route ||
    !["planned", "routing_estimate", "ok"].includes(route.status) ||
    typeof route.duration_minutes !== "number" ||
    !Number.isFinite(route.duration_minutes) ||
    route.duration_minutes < 0
  )
    return false;
  if (!route.queried_at) return true; // Historical records without a timestamp retain their original reference status.
  const stamp = Date.parse(route.queried_at),
    age = Date.now() - stamp;
  return (
    Number.isFinite(stamp) &&
    age >= 0 &&
    age <= (route.status === "routing_estimate" ? 30 : 7) * 86400000
  );
}
export function journeyKey(route: UsydRoute) {
  return JSON.stringify({
    duration: route.duration_minutes,
    walking: route.walking_minutes ?? null,
    departure: route.departure_at ?? null,
    arrival: route.arrival_at ?? null,
    transfers: route.transfers ?? null,
    modes: [...new Set(route.transit_modes ?? [])].sort(),
    services: route.services ?? [],
    legs: (route.legs ?? []).map((leg) => [
      leg.mode,
      leg.service ?? null,
      leg.from ?? null,
      leg.to ?? null,
      leg.from_stop_id ?? null,
      leg.to_stop_id ?? null,
      leg.platform ?? null,
      leg.duration_minutes,
      leg.departure_at ?? null,
      leg.arrival_at ?? null,
    ]),
  });
}
export function transitJourneys(data?: UsydCommute | null) {
  const routes = [
    ...(data?.transit_options ?? []),
    ...transit.flatMap((mode) =>
      data?.modes?.[mode] ? [data.modes[mode]] : [],
    ),
  ];
  const seen = new Set<string>();
  return routes
    .filter((route) => {
      if (!usableRoute(route)) return false;
      const key = journeyKey(route);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => a.duration_minutes! - b.duration_minutes!)
    .slice(0, 6);
}
export function itineraryLabel(route: UsydRoute) {
  if (route.legs?.length) {
    const parts = route.legs
      .map((leg) => names[leg.mode] ?? "Connection")
      .filter((mode, i, all) => i === 0 || mode !== all[i - 1]);
    return parts.join(" → ");
  }
  const modes = (route.transit_modes ?? [])
    .map((mode) => names[mode])
    .filter(Boolean);
  return modes.length
    ? `${[...new Set(modes)].join(" + ")} route`
    : "Public transport route";
}
export function chosenTransit(
  data?: UsydCommute | null,
  mode = "public_transport",
) {
  const selected = data?.selected_transit_route;
  if (
    usableRoute(selected) &&
    (selected?.mode === mode ||
      (!selected?.mode && mode === "public_transport"))
  )
    return selected;
  const personal = data?.modes?.[mode];
  if (
    personal &&
    ["scheduled_live_query", "recent_checked_query"].includes(
      personal.basis ?? "",
    ) &&
    usableRoute(personal)
  )
    return personal;
  if (mode !== "public_transport")
    return usableRoute(data?.modes?.[mode]) ? data?.modes?.[mode] : undefined;
  return transitJourneys(data)[0];
}
