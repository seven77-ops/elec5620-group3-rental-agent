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
    ...(h && "suburb" in h ? { suburb: h.suburb } : {}),
    budget_amount: profile.budget?.maximum,
    ...(profile.budget?.period
      ? { budget_period: profile.budget.period as RentalBrief["budget_period"] }
      : {}),
    budget_scope: profile.budget?.scope as RentalBrief["budget_scope"],
    ...(profile.student_commute
      ? {
          commute_mode: profile.student_commute.mode,
          commute_max_minutes: profile.student_commute.maximum_minutes,
          arrival_time: profile.student_commute.arrival_time,
          travel_day: profile.student_commute.travel_day,
          travel_date: profile.student_commute.travel_date,
          max_transfers: profile.student_commute.max_transfers,
        }
      : {}),
    occupants: profile.occupants,
    rental_mode: profile.rental_mode as RentalBrief["rental_mode"],
    ...(h?.min_bedrooms != null ? { min_bedrooms: h.min_bedrooms } : {}),
    ...(h?.min_bathrooms != null ? { min_bathrooms: h.min_bathrooms } : {}),
    ...(h?.min_car_spaces != null ? { min_car_spaces: h.min_car_spaces } : {}),
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
    if ("suburb" in filters) result.suburb = filters.suburb;
    for (const key of [
      "min_bedrooms",
      "min_bathrooms",
      "min_car_spaces",
    ] as const)
      if (filters[key] !== undefined) result[key] = filters[key];
    if (filters.usyd_mode !== undefined)
      result.commute_mode = filters.usyd_mode as RentalBrief["commute_mode"];
    if (filters.usyd_max_minutes !== undefined)
      result.commute_max_minutes = filters.usyd_max_minutes;
    if (filters.usyd_arrival_time !== undefined)
      result.arrival_time = filters.usyd_arrival_time;
    if (filters.usyd_travel_day !== undefined)
      result.travel_day = filters.usyd_travel_day as RentalBrief["travel_day"];
    if (filters.usyd_travel_date !== undefined)
      result.travel_date = filters.usyd_travel_date;
    if (filters.usyd_max_transfers !== undefined)
      result.max_transfers = filters.usyd_max_transfers;
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
    (profile.budget?.maximum == null ||
      profile.budget.hard_limit === false ||
      h.budget_match_mode === "matching_scope" ||
      listing.weekly_rent <= profile.budget?.maximum)
  );
}
