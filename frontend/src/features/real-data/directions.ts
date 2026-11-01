/** Ordinary outbound links: no Google SDK, API request or key. */
export function usydDirections(home: { address: string; postcode: string; usyd_commute?: { origin: { latitude: number; longitude: number } | null } | null }, mode: string) {
  const travelmode = ({ walk: "walking", bike: "bicycling", drive: "driving" } as Record<string, string>)[mode] ?? "transit";
  const point = home.usyd_commute?.origin;
  const origin = point && Number.isFinite(point.latitude) && Number.isFinite(point.longitude) && point.latitude >= -37.6 && point.latitude <= -28 && point.longitude >= 140.9 && point.longitude <= 159.2
    ? `${point.latitude},${point.longitude}` : `${home.address} NSW ${home.postcode}`;
  return "https://www.google.com/maps/dir/?" + new URLSearchParams({
    api: "1",
    origin,
    destination: "-33.88630396441765,151.190498785334",
    travelmode,
  });
}
