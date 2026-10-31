import type { HousingAd, HousingFilters } from "../../api/catalog.ts";
import type { RentalBrief } from "../../api/assistant.ts";
import {
  compactCommute,
  selectedCommute,
} from "../real-data/commuteSummary.ts";

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
    const label = whole ? "budget" : "weekly rent limit";
    reasons.push(
      saving > 0
        ? `Below ${label} by AUD ${saving.toLocaleString("en-AU")}/week`
        : `Weekly rent meets ${label}`,
    );
  }
  const mode =
    filters.usyd_mode || criteria.commute_mode || listing.recommendation_mode;
  if (mode) {
    const summary = selectedCommute(listing.usyd_commute, mode);
    if (summary) reasons.push(compactCommute(summary));
  }
  const bedrooms = filters.min_bedrooms ?? criteria.min_bedrooms;
  const bathrooms = filters.min_bathrooms ?? criteria.min_bathrooms;
  if (
    ((bedrooms ?? 0) > 0 || (bathrooms ?? 0) > 0) &&
    listing.bedrooms >= (bedrooms ?? 0) &&
    listing.bathrooms >= (bathrooms ?? 0)
  )
    reasons.push(
      `${listing.bedrooms} bed${bathrooms ? ` · ${listing.bathrooms} bath` : ""}, meets your layout needs`,
    );
  const spaces = filters.min_car_spaces ?? criteria.min_car_spaces;
  if (spaces && listing.car_spaces >= spaces)
    reasons.push(`Includes ${listing.car_spaces} car spaces`);
  return reasons.slice(0, 4);
}
