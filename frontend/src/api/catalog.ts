export interface HousingFilters {
  usyd_mode?: string;
  usyd_arrival_time?: string;
  usyd_travel_day?: string;
  usyd_travel_date?: string;
  usyd_max_transfers?: number;
  usyd_max_minutes?: number;
  suburb?: string;
  min_bedrooms?: number;
  min_bathrooms?: number;
  min_car_spaces?: number;
  max_weekly_rent?: number;
  sort?: string;
}
export interface HousingPhoto {
  url: string;
  source_url: string;
  captured_at: string;
  photo_source_url?: string;
  photo_source_kind?:
    | "same_property_advertisement"
    | "same_property_reference"
    | "same_property_history";
}
export interface UsydRoute {
  legs?: {
    mode: string;
    duration_minutes: number;
    service?: string | null;
    from?: string | null;
    to?: string | null;
    departure_at?: string | null;
    arrival_at?: string | null;
    platform?: string | null;
    alerts?: string[];
  }[];
  basis?: string;
  status: string;
  duration_minutes: number | null;
  distance_m?: number | null;
  source_url: string;
  queried_at?: string;
  reference_arrival_at?: string;
  transit_modes?: string[];
  walking_minutes?: number | null;
  transfers?: number | null;
  reason?: string;
}
export interface CommuteEstimate {
  status: "coarse_estimate";
  level: "street" | "suburb" | "postcode";
  label: string;
  lower_minutes: number;
  upper_minutes: number;
  typical_minutes: number;
  anchor_count: number;
  source_urls: string[];
  queried_at: string;
  reference_arrival_at?: string;
}
export interface UsydCommute {
  estimates?: Record<string, CommuteEstimate>;
  origin: {
    latitude: number;
    longitude: number;
    precision: string;
    source_url: string;
  } | null;
  straight_line_distance_m: number | null;
  modes: Record<string, UsydRoute>;
  destination: {
    id?: string;
    label: string;
    latitude: number;
    longitude: number;
    source_url: string;
    campus_url: string;
  };
  generated_at: string;
  reference_arrival_at?: string;
  reference_note: string;
}
export interface HousingAd {
  usyd_commute?: UsydCommute | null;
  property_type?: string | null;
  bond?: number | null;
  available_from_raw?: string | null;
  photos?: HousingPhoto[];
  listing_id: string;
  source_url: string;
  address: string;
  suburb: string;
  postcode: string;
  bedrooms: number;
  advertised_bedrooms: number;
  bedroom_count_basis: string;
  bedroom_label: string;
  bathrooms: number;
  car_spaces: number;
  weekly_rent: number;
  captured_at: string;
  checked_at: string | null;
  rent_scope: string | null;
  furnishing: string | null;
  available_from: string | null;
  source_observation: {
    detail_read: boolean;
    search_crawl_label: string | null;
    detail_crawl_label: string | null;
  };
  features: string[];
}
export interface HousingCatalog {
  photo_listing_count?: number;
  photo_count?: number;
  total: number;
  suburb_count: number;
  suburbs: string[];
  captured_at: string;
  fingerprint: string;
}
export interface HousingPage {
  total: number;
  items: HousingAd[];
  page: number;
  page_size: number;
  catalog: HousingCatalog;
}
export function filterKey(value: HousingFilters) {
  return JSON.stringify(
    Object.entries({ ...value, sort: value.sort ?? "rent_asc" })
      .filter(([, v]) => v != null)
      .sort(([a], [b]) => a.localeCompare(b)),
  );
}

export interface RecommendationContext {
  profile_version: number | null;
  profile_fingerprint?: string;
  filters: HousingFilters;
  unverified_preferences: string[];
  mapping_policy: string;
}
