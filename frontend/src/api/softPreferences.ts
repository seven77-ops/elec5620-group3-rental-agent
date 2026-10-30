import type { AreaEvidence, LifestyleTopic } from "./areas";

export interface AdvertisementPreferenceEvidence {
  evidence_id: string;
  topics: LifestyleTopic[];
  feature: string;
  status: "advertised_unconfirmed";
  claim: string;
  limitation: string;
  source: { url: string; captured_at: string | null; publisher: string };
}

export interface ListingPreferenceEvidence {
  listing_id: string;
  suburb: string;
  original_position: number;
  score: number;
  matched_topics: LifestyleTopic[];
  unknown_topics: LifestyleTopic[];
  reasons: string[];
  advertisement_evidence: AdvertisementPreferenceEvidence[];
  area_context: {
    suburb: string;
    has_curated_records: boolean;
    evidence: AreaEvidence[];
  };
  notes: string[];
}

export interface SoftPreferenceReport {
  schema_version: "listing-soft-preferences.v1";
  ranking_basis: string;
  checked_at: string;
  catalog_fingerprint: string;
  area_dataset_version: string;
  area_evidence_fingerprint: string;
  fingerprint: string;
  priorities: { topic: LifestyleTopic; label: string }[];
  unsupported_priorities: string[];
  coverage: {
    matching_listings: number;
    matching_suburbs: number;
    matching_suburbs_with_records: number;
    matching_listings_with_supported_preferences: number;
    matching_listings_with_advertisement_evidence: number;
    matching_listings_with_area_support: number;
    catalog_suburbs: number;
    catalog_suburbs_with_records: number;
  };
  items: ListingPreferenceEvidence[];
  limitations: string[];
}
