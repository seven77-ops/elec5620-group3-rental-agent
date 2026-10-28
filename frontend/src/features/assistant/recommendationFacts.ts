import type { HousingAd, HousingFilters } from "../../api/catalog.ts";
import type { RentalBrief } from "../../api/assistant.ts";
import { selectedCommute } from "../real-data/commuteSummary.ts";

export function listingReasons(
  listing: HousingAd,
  criteria: RentalBrief = {},
  filters: HousingFilters = {},
) {
  const reasons: string[] = [];
  const whole =
    criteria.budget_period === "week" &&
    criteria.budget_scope === "whole_property";
  const cap =
    filters.max_weekly_rent ?? (whole ? criteria.budget_amount : undefined);
  if (typeof cap === "number" && cap >= listing.weekly_rent) {
    const saving = Number((cap - listing.weekly_rent).toFixed(2));
    const label = whole ? "预算" : "周租上限";
    reasons.push(
      saving > 0
        ? `比${label}低 AUD ${saving.toLocaleString("en-AU")}/周`
        : `周租符合${label}`,
    );
  }
  const mode =
    filters.usyd_mode || criteria.commute_mode || listing.recommendation_mode;
  if (mode) {
    const summary = selectedCommute(listing.usyd_commute, mode);
    if (summary) reasons.push(summary.text);
  }
  const bedrooms = filters.min_bedrooms ?? criteria.min_bedrooms;
  const bathrooms = filters.min_bathrooms ?? criteria.min_bathrooms;
  if (
    ((bedrooms ?? 0) > 0 || (bathrooms ?? 0) > 0) &&
    listing.bedrooms >= (bedrooms ?? 0) &&
    listing.bathrooms >= (bathrooms ?? 0)
  )
    reasons.push(
      `${listing.bedrooms}卧${bathrooms ? `${listing.bathrooms}卫` : ""}，符合房型要求`,
    );
  const spaces = filters.min_car_spaces ?? criteria.min_car_spaces;
  if (spaces && listing.car_spaces >= spaces)
    reasons.push(`含 ${listing.car_spaces} 个车位`);
  return reasons.slice(0, 4);
}
