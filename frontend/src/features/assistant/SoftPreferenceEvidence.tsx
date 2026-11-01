import type { SoftPreferenceReport } from "../../api/softPreferences";
import type { LifestyleTopic } from "../../api/areas";
import "./softPreferenceEvidence.css";

export function SoftPreferenceEvidence({
  report,
  listingId,
}: {
  report: SoftPreferenceReport;
  listingId?: string;
}) {
  const labels = (topics: LifestyleTopic[]) =>
    topics
      .map(
        (topic) =>
          report.priorities.find((p) => p.topic === topic)?.label ?? topic,
      )
      .join(", ");
  if (listingId) {
    const item = report.items.find((entry) => entry.listing_id === listingId);
    if (!item) return null;
    return (
      <section
        className="soft-preference-listing"
        aria-label={`Soft preference evidence for ${listingId}`}
      >
        {item.matched_topics.length > 0 && (
          <p>
            <strong>Documented preference coverage:</strong>{" "}
            {labels(item.matched_topics)}
          </p>
        )}
        {item.unknown_topics.length > 0 && (
          <p className="soft-preference-unknown">
            Unknown: {labels(item.unknown_topics)}
          </p>
        )}
        {(item.advertisement_evidence.length > 0 ||
          item.area_context.evidence.length > 0) && (
          <p className="soft-preference-note">
            These sources do not verify property walking distance, quietness or
            safety.
          </p>
        )}
        {item.notes.map((note) => (
          <p className="soft-preference-note" key={note}>
            {note}
          </p>
        ))}
        {(item.advertisement_evidence.length > 0 ||
          item.area_context.evidence.length > 0) && (
          <details className="soft-preference-sources">
            <summary>Sources and scope</summary>
            {item.advertisement_evidence.length > 0 && (
              <div className="soft-preference-source-group">
                <h4>Property advertisement claims</h4>
                <p>Advertiser claims; independently unverified.</p>
                {item.advertisement_evidence.map((record) => (
                  <article key={record.evidence_id}>
                    <p>{record.claim}</p>
                    <a
                      href={record.source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Public advertisement ↗
                    </a>
                    <p className="soft-preference-note">
                      Captured: {record.source.captured_at ?? "Unknown"}
                    </p>
                    <p className="soft-preference-note">{record.limitation}</p>
                    <p className="soft-preference-reference">
                      Reference: {record.evidence_id}
                    </p>
                  </article>
                ))}
              </div>
            )}
            {item.area_context.evidence.length > 0 && (
              <div className="soft-preference-source-group">
                <h4>Suburb facility context</h4>
                <p>
                  These sources concern {item.suburb}. They do not establish
                  this property's walking distance, quietness or safety.
                </p>
                {item.area_context.evidence.map((record) => (
                  <article key={record.evidence_id}>
                    <p>{record.summary}</p>
                    <a
                      href={record.source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {record.source.publisher} · {record.source.title} ↗
                    </a>
                    <p className="soft-preference-note">
                      Scope: {record.scope_label}
                    </p>
                    <p className="soft-preference-note">
                      Checked: {record.source.checked_at} ·{" "}
                      {record.kind === "official"
                        ? "Official source"
                        : "Venue source"}
                    </p>
                    <p className="soft-preference-note">{record.limitation}</p>
                    <p className="soft-preference-reference">
                      Reference: {record.evidence_id}
                    </p>
                  </article>
                ))}
              </div>
            )}
          </details>
        )}
      </section>
    );
  }
  const coverage = report.coverage;
  const unestablished = report.priorities
    .filter((priority) =>
      report.items.every((item) =>
        item.unknown_topics.includes(priority.topic),
      ),
    )
    .map((priority) => priority.label);
  return (
    <section
      className="soft-preference-overview"
      aria-label="Soft preference ranking"
    >
      <p>
        <strong>Ordered by documented preferences</strong> · All{" "}
        {coverage.matching_listings} hard matches retained
      </p>
      <p>
        Requested:{" "}
        {report.priorities.map((priority) => priority.label).join(", ")}
      </p>
      <p>
        {coverage.matching_listings_with_supported_preferences} /{" "}
        {coverage.matching_listings} listings have evidence for at least one
        requested preference.
      </p>
      {unestablished.length > 0 && (
        <p className="soft-preference-unknown">
          Not established by this evidence: {unestablished.join(", ")}
        </p>
      )}
      <p className="soft-preference-note">
        Area sources cover {coverage.matching_suburbs_with_records} /{" "}
        {coverage.matching_suburbs} matching suburbs (
        {coverage.catalog_suburbs_with_records} / {coverage.catalog_suburbs}{" "}
        across the catalog). Coverage does not imply all requested topics are
        established.
      </p>
      {report.unsupported_priorities.length > 0 && (
        <p className="soft-preference-unknown">
          Unsupported preferences: {report.unsupported_priorities.join(", ")}
        </p>
      )}
      <details className="soft-preference-sources">
        <summary>How this order works</summary>
        <p>{report.ranking_basis}</p>
        {report.limitations.map((limitation) => (
          <p className="soft-preference-note" key={limitation}>
            {limitation}
          </p>
        ))}
        <p className="soft-preference-note">
          Evidence evaluated: {report.checked_at} · Area dataset:{" "}
          {report.area_dataset_version}
        </p>
      </details>
    </section>
  );
}
