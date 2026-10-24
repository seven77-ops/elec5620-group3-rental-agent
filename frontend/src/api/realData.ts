export interface ProviderConfig {
  configured: boolean;
  documentation: string;
  key_present?: boolean;
  use_approved?: boolean;
}
export interface RealConfig {
  coverage: { postcodes: string[]; bedrooms: number[] };
  providers: { domain: ProviderConfig; tfnsw: ProviderConfig };
}
export interface Benchmark {
  period: string;
  sample_size: number;
  q25: number;
  median: number;
  q75: number;
  official_statistic: boolean;
  source_url: string;
  difference_aud: number | null;
  difference_percent: number | null;
}
export interface MarketResult {
  status: string;
  postcode: string;
  bedrooms: number;
  benchmarks: Benchmark[];
  limitations: string[];
}
export interface Point {
  latitude: number;
  longitude: number;
}
export interface RealListing {
  record_id: string;
  source_url: string;
  address: string;
  postcode: string;
  weekly_rent: number;
  rent_scope: string;
  observed_at: string;
  bedrooms: number | null;
  bills_included: boolean | null;
  latitude: number | null;
  longitude: number | null;
  freshness: string;
}
export interface Advertisement {
  listing_id: string;
  source_url: string | null;
  address: string | null;
  advertised_price: string | null;
  bedrooms: number | null;
  latitude: number | null;
  longitude: number | null;
}
export interface DomainResult {
  queried_at: string;
  items: Advertisement[];
  limitations: string[];
}
export interface TripResult {
  queried_at: string;
  query: { origin: Point; destination: Point; arrival_at: string };
  journeys: {
    duration_minutes: number | null;
    leg_travel_minutes: number;
    walking_minutes: number | null;
    transfers: number | null;
    departure_at: string | null;
    arrival_at: string | null;
    services: string[];
  }[];
  limitations: string[];
}
export const postcodeOptions = [
  { value: "2050", label: "2050 · Camperdown 周边" },
  { value: "2042", label: "2042 · Newtown / Enmore 周边" },
  { value: "2008", label: "2008 · Chippendale / Darlington 周边" },
  { value: "2037", label: "2037 · Glebe / Forest Lodge 周边" },
];
export const scopeOptions = [
  { value: "whole_property", label: "整套" },
  { value: "per_room", label: "单间" },
  { value: "per_person", label: "按人" },
];
export const mapUrl = (point: Point) =>
  `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${point.latitude},${point.longitude}`)}`;
