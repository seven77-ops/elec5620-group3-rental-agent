import type { HousingAd, HousingFilters } from "../../api/catalog";
import type { RentalBrief } from "../../api/assistant";
import { listingReasons } from "./recommendationFacts";
import "./recommendationControls.css";

export default function ListingReasons({
  listing,
  criteria,
  filters,
}: {
  listing: HousingAd;
  criteria?: RentalBrief;
  filters?: HousingFilters;
}) {
  const reasons = listingReasons(listing, criteria, filters);
  return reasons.length ? (
    <ul className="recommendation-reasons" aria-label="推荐理由">
      {reasons.map((reason) => (
        <li key={reason}>{reason}</li>
      ))}
    </ul>
  ) : null;
}
