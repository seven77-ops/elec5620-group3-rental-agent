export const lifestyleTopics = {
  parks: "Parks and outdoors",
  food: "Food and dining",
  shopping: "Shopping",
  library: "Libraries",
  community: "Community facilities",
  walkability: "Walking paths",
  quiet: "Quiet",
  safety: "Safety",
};
export type LifestyleTopic = keyof typeof lifestyleTopics;
export interface AreaEvidence {
  evidence_id: string;
  suburb: string;
  topics: LifestyleTopic[];
  kind: "official" | "venue" | "media" | "resident_opinion";
  summary: string;
  geographic_scope: string;
  scope_label: string;
  limitation: string;
  freshness: "current_reference" | "needs_review" | "background";
  supports_topics: LifestyleTopic[];
  source: {
    publisher: string;
    title: string;
    url: string;
    published_at: string | null;
    updated_at: string | null;
    data_period: string | null;
    checked_at: string;
  };
}
export interface AreaContext {
  suburb: string;
  matching_count: number;
  min_weekly_rent: number | null;
  max_weekly_rent: number | null;
  matched_topics: LifestyleTopic[];
  missing_topics: LifestyleTopic[];
  match_reasons: string[];
  evidence: AreaEvidence[];
  notes: string[];
}
export interface AreaAdviceReport {
  criteria_summary?: string;
  dataset_version: string;
  fingerprint: string;
  checked_at: string;
  coverage: { covered_suburbs: number; catalog_suburbs: number };
  priorities: { topic: LifestyleTopic; label: string }[];
  budget_applied: boolean;
  areas: AreaContext[];
  limitations: string[];
}
