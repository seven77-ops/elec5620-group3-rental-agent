import type { HousingAd } from "../../api/catalog";
import { usydDirections } from "./directions";
import { commuteSummary } from "./commuteSummary";
import "./usydCommute.css";
export { commuteModes } from "./commuteSummary";

export function UsydCommuteMini({ listing }: { listing: HousingAd }) {
  const { average } = commuteSummary(listing.usyd_commute);
  return (
    <span className="usyd-commute-mini">
      {average !== null ? (
        <strong className="commute-time">平均通勤约 {average} 分钟</strong>
      ) : (
        <small>通勤参考待补充</small>
      )}
    </span>
  );
}

export default function UsydCommute({ listing }: { listing: HousingAd }) {
  const data = listing.usyd_commute;
  const { items, average } = commuteSummary(data);
  return (
    <section
      className="listing-detail-section usyd-commute"
      data-testid="usyd-commute"
    >
      <div className="usyd-commute-title">
        <h3>到悉大主校区</h3>
        {average !== null && <span>平均通勤约 {average} 分钟</span>}
      </div>
      <p className="muted small">Camperdown / Darlington · Fisher Library</p>
      <dl className="usyd-mode-grid">
        {items.map((mode) => (
          <div key={mode.value}>
            <dt>{mode.label}</dt>
            <dd>
              <strong>
                约 {mode.minutes}
                <small> 分钟</small>
              </strong>
              <a
                className="usyd-map-link"
                href={usydDirections(listing, mode.value)}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`在 Google 地图查看${mode.label}`}
              >
                Google 地图 ↗
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
          Google 地图 ↗
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
