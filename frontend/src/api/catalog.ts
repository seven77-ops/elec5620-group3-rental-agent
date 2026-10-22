export interface HousingFilters {
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
}
export interface HousingAd {
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
