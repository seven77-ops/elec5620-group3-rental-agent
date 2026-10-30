import { createRoot } from "react-dom/client";
import { SoftPreferenceEvidence } from "../../src/features/assistant/SoftPreferenceEvidence";
import type { SoftPreferenceReport } from "../../src/api/softPreferences";

const report: SoftPreferenceReport = {
  schema_version: "listing-soft-preferences.v1", ranking_basis: "Equal scores preserve hard-match order.",
  checked_at: "2026-10-30", catalog_fingerprint: "fixture", area_dataset_version: "fixture",
  area_evidence_fingerprint: "fixture", fingerprint: "fixture",
  priorities: [{ topic: "shopping", label: "Shopping" }, { topic: "quiet", label: "Quietness" }, { topic: "safety", label: "Safety" }],
  unsupported_priorities: [],
  coverage: { matching_listings: 2, matching_suburbs: 2, matching_suburbs_with_records: 1,
    matching_listings_with_supported_preferences: 1, matching_listings_with_advertisement_evidence: 1,
    matching_listings_with_area_support: 1, catalog_suburbs: 72, catalog_suburbs_with_records: 12 },
  items: [
    { listing_id: "b", suburb: "Burwood", original_position: 2, score: 1, matched_topics: ["shopping"],
      unknown_topics: ["quiet", "safety"], reasons: [], notes: [],
      advertisement_evidence: [{ evidence_id: "advertised:b:shopping", topics: ["shopping"], feature: "Close to shops",
        status: "advertised_unconfirmed", claim: "Advertisement lists Close to shops.", limitation: "Walking distance is unverified.",
        source: { url: "https://www.domain.com.au/example-b", captured_at: "2026-10-24", publisher: "Domain" } }],
      area_context: { suburb: "Burwood", has_curated_records: true, evidence: [{ evidence_id: "fixture-retail",
        suburb: "Burwood", topics: ["shopping"], kind: "official", summary: "Retail precinct exists.",
        geographic_scope: "precinct", scope_label: "Retail precinct", limitation: "Property distance unknown.",
        freshness: "current_reference", supports_topics: ["shopping"], source: { publisher: "Council",
          title: "Facilities", url: "https://example.org/council", checked_at: "2026-10-24", published_at: null, updated_at: null, data_period: null } }] } },
    { listing_id: "c", suburb: "Carlton", original_position: 1, score: 0, matched_topics: [],
      unknown_topics: ["shopping", "quiet", "safety"], reasons: [], advertisement_evidence: [],
      area_context: { suburb: "Carlton", has_curated_records: false, evidence: [] },
      notes: ["Area coverage is missing; this is not evidence that facilities are absent."] },
  ],
  limitations: ["All hard matches remain. Facility existence does not establish walking distance, quietness or safety."],
};

createRoot(document.getElementById("root")!).render(
  <main style={{ maxWidth: 680, margin: "0 auto", padding: 12, fontFamily: "sans-serif" }}>
    <SoftPreferenceEvidence report={report} />
    {report.items.map((item) => <SoftPreferenceEvidence key={item.listing_id} report={report} listingId={item.listing_id} />)}
  </main>,
);
