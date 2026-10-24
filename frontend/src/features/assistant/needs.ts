import type { Conversation, RentalBrief } from "../../api/assistant";
import type { Profile } from "../../api/types";
import type { HousingAd } from "../../api/catalog";

export const pendingNeeds = (conversation: Conversation | null) =>
  Boolean(
    conversation?.messages
      .at(-1)
      ?.actions.some((action) => action.type === "apply_preferences"),
  );

export function profileNeeds(profile?: Profile): RentalBrief {
  if (!profile) return {};
  const h = profile.housing_preferences;
  return {
    suburb: h?.suburb ?? null,
    budget_amount: profile.budget.maximum,
    budget_period: "week",
    budget_scope: profile.budget.scope as RentalBrief["budget_scope"],
    occupants: profile.occupants,
    rental_mode: profile.rental_mode as RentalBrief["rental_mode"],
    min_bedrooms: h?.min_bedrooms ?? 0,
    min_bathrooms: h?.min_bathrooms ?? 0,
    min_car_spaces: h?.min_car_spaces ?? 0,
  };
}

export function conversationNeeds(
  conversation: Conversation | null,
  profile?: Profile,
): RentalBrief {
  if (
    (conversation?.dialogue_mode === "collect_preferences" ||
      conversation?.dialogue_mode === "area_advice" ||
      conversation?.dialogue_mode === "recommend_areas") &&
    conversation.rental_brief
  )
    return { ...conversation.rental_brief };
  const result = { ...profileNeeds(profile), ...conversation?.rental_brief };
  const filters = conversation?.last_search_filters;
  if (filters) {
    result.suburb = filters.suburb ?? null;
    for (const key of [
      "min_bedrooms",
      "min_bathrooms",
      "min_car_spaces",
    ] as const)
      result[key] = filters[key] ?? 0;
    if (filters.max_weekly_rent !== undefined) {
      result.budget_amount = filters.max_weekly_rent;
      result.budget_period = "week";
    }
  }
  return result;
}

export function needsMatch(brief: RentalBrief, profile?: Profile) {
  if (!profile) return false;
  const saved = profileNeeds(profile);
  return (Object.keys(saved) as (keyof RentalBrief)[]).every(
    (key) => brief[key] === saved[key],
  );
}

export function listingMatches(listing: HousingAd, profile: Profile) {
  const h = profile.housing_preferences ?? {};
  return (
    (!h.suburb || listing.suburb === h.suburb) &&
    listing.bedrooms >= (h.min_bedrooms ?? 0) &&
    listing.bathrooms >= (h.min_bathrooms ?? 0) &&
    listing.car_spaces >= (h.min_car_spaces ?? 0) &&
    (!profile.budget.hard_limit ||
      h.budget_match_mode === "matching_scope" ||
      listing.weekly_rent <= profile.budget.maximum)
  );
}
