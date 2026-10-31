import type { HousingAd } from "../../api/catalog";
import { useContext } from "react";
import { CaseContext, currentConfirmation } from "../../app/context";
import { usydDirections } from "./directions";
import {
  compactCommute,
  commuteOverview,
  commuteDuration,
  commuteSummary,
  selectedCommute,
} from "./commuteSummary";
import "./usydCommute.css";
export { commuteModes, commuteChoices } from "./commuteSummary";

function useMode(listing: HousingAd, mode?: string) {
  const context = useContext(CaseContext);
  return (
    mode ||
    listing.recommendation_mode ||
    (context
      ? currentConfirmation(context.current)?.profile?.student_commute?.mode
      : undefined) ||
    "public_transport"
  );
}
export function UsydCommuteMini({
  listing,
  mode,
  overview = true,
  showLabel = false,
}: {
  listing: HousingAd;
  mode?: string;
  overview?: boolean;
  showLabel?: boolean;
}) {
  const selectedMode = useMode(listing, mode);
  const summary = selectedCommute(listing.usyd_commute, selectedMode);
  if (overview) {
    const result = commuteOverview(listing.usyd_commute, selectedMode);
    if (!result.average)
      return (
        <span className="usyd-commute-mini">
          <small>Check route</small>
        </span>
      );
    return (
      <div
        role="group"
        className="usyd-commute-mini usyd-commute-overview"
        aria-label="Commute to USYD"
      >
        <strong className="commute-time">
          {showLabel ? "Commute " : ""}
          {commuteDuration(result.average).replace(/^~/, "")}
        </strong>
      </div>
    );
  }
  return (
    <span className="usyd-commute-mini" aria-label={summary?.text}>
      {summary ? (
        <strong className="commute-time">{compactCommute(summary)}</strong>
      ) : (
        <small>Check route</small>
      )}
    </span>
  );
}
export default function UsydCommute({ listing }: { listing: HousingAd }) {
  const data = listing.usyd_commute,
    mode = useMode(listing);
  const summary = selectedCommute(data, mode);
  const transitSummary = selectedCommute(
    data,
    ["train", "metro", "bus"].includes(mode) ? mode : "public_transport",
  );
  const roads = commuteSummary(data).items.filter(
    (item) => item.value !== "public_transport",
  );
  if (
    ["walk", "bike", "drive"].includes(mode) &&
    summary &&
    !roads.some((item) => item.value === mode)
  )
    roads.push({
      value: mode,
      label: summary.label,
      minutes: summary.upper,
      estimated: summary.estimated,
    });
  return (
    <section
      className="listing-detail-section usyd-commute"
      data-testid="usyd-commute"
    >
      <div className="usyd-commute-title">
        <h3>Commute to USYD</h3>
      </div>
      <dl className="usyd-mode-grid">
        <div data-mode="public_transport">
          <dt>Public transport</dt>
          <dd>
            <strong>
              {transitSummary ? commuteDuration(transitSummary) : "Check route"}
            </strong>
            {["train", "metro", "bus"].includes(mode) && (
              <small>Includes {mode}</small>
            )}
            <a
              className="usyd-map-link"
              href={usydDirections(listing, "public_transport")}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Check public transport directions in Google Maps"
            >
              Google Maps ↗
            </a>
          </dd>
        </div>
        {roads.map((item) => {
          const current = selectedCommute(data, item.value)!;
          return (
            <div key={item.value} data-mode={item.value}>
              <dt>{item.label}</dt>
              <dd>
                <strong>{commuteDuration(current)}</strong>
                <a
                  className="usyd-map-link"
                  href={usydDirections(listing, item.value)}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={`View ${item.label.toLowerCase()} route in Google Maps`}
                >
                  Google Maps ↗
                </a>
              </dd>
            </div>
          );
        })}
      </dl>
      <details className="usyd-route-notes">
        <summary>Route information</summary>
        {transitSummary?.estimated && (
          <p>Nearby-route estimate; services and transfers unverified.</p>
        )}
        <p>
          Destination: USYD Camperdown / Darlington · Fisher Library. Times are
          approximate, per journey, and include recorded walking, waiting and
          transfers. Check your departure time in Google Maps.
        </p>
      </details>
      <div className="usyd-commute-sources">
        <a
          href="https://opendata.transport.nsw.gov.au/dataset/trip-planner-apis"
          target="_blank"
          rel="noopener noreferrer"
        >
          TfNSW
        </a>
        <a
          href="https://routing.openstreetmap.de/about.html"
          target="_blank"
          rel="noopener noreferrer"
        >
          © OpenStreetMap / FOSSGIS
        </a>
      </div>
    </section>
  );
}
