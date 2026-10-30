import type { HousingAd } from "../../api/catalog";
import { useContext } from "react";
import { CaseContext, currentConfirmation } from "../../app/context";
import { usydDirections } from "./directions";
import { commuteSummary, selectedCommute } from "./commuteSummary";
import "./usydCommute.css";
export { commuteModes } from "./commuteSummary";

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
}: {
  listing: HousingAd;
  mode?: string;
}) {
  const chosen = useMode(listing, mode);
  const summary = selectedCommute(listing.usyd_commute, chosen);
  return (
    <span className="usyd-commute-mini">
      {summary ? (
        <strong className="commute-time">{summary.text}</strong>
      ) : (
        <small>Commute reference needed</small>
      )}
    </span>
  );
}

export default function UsydCommute({ listing }: { listing: HousingAd }) {
  const data = listing.usyd_commute;
  const { items: references } = commuteSummary(data);
  const mode = useMode(listing);
  const summary = selectedCommute(data, mode);
  const items = references.flatMap((item) => {
    const current = selectedCommute(data, item.value);
    return current ? [{ ...item, selected: current }] : [];
  });
  if (summary && !items.some((item) => item.value === mode))
    items.push({
      value: mode,
      label: summary.label,
      minutes: summary.upper,
      estimated: summary.estimated,
      selected: summary,
    });
  return (
    <section
      className="listing-detail-section usyd-commute"
      data-testid="usyd-commute"
    >
      <div className="usyd-commute-title">
        <h3>Commute to USYD main campus</h3>
        {summary && <span>{summary.text}</span>}
      </div>
      <p className="muted small">Camperdown / Darlington · Fisher Library</p>
      <dl className="usyd-mode-grid">
        {items.map((mode) => (
          <div key={mode.value}>
            <dt>{mode.label}</dt>
            <dd>
              <strong>
                {mode.selected?.estimated
                  ? `Estimated ${mode.selected.lower}–${mode.selected.upper}`
                  : `Approx. ${mode.minutes}`}
                <small> minutes</small>
              </strong>
              <a
                className="usyd-map-link"
                href={usydDirections(listing, mode.value)}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`View ${mode.label.toLowerCase()} route in Google Maps`}
              >
                Google Maps ↗
              </a>
            </dd>
          </div>
        ))}
      </dl>
      {!items.length && (
        <a
          className="usyd-map-link"
          href={usydDirections(listing, "public_transport")}
          target="_blank"
          rel="noopener noreferrer"
        >
          Google Maps ↗
        </a>
      )}
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
