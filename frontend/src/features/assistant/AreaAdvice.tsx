import { Button, Tag } from "antd";
import type { AreaContext, AreaAdviceReport } from "../../api/areas";
import { lifestyleTopics } from "../../api/areas";
import "./areaAdvice.css";

const evidenceLabels = {
  official: "Official facilities information",
  venue: "Operator information",
  media: "Media background",
  resident_opinion: "Resident opinions",
};
const topicNames = (topics: (keyof typeof lifestyleTopics)[]) =>
  topics.map((t) => lifestyleTopics[t]).join(", ");

export function AreaEvidenceDetails({ area }: { area: AreaContext }) {
  return (
    <div className="area-evidence-details">
      {area.matched_topics.length > 0 && (
        <p className="area-relevance">
          Relevant to your preferences: {topicNames(area.matched_topics)}
        </p>
      )}
      {area.missing_topics.length > 0 && (
        <p className="area-missing">
          Still unconfirmed: {topicNames(area.missing_topics)}
        </p>
      )}
      {area.notes.map((note) => (
        <p className="muted small" key={note}>
          {note}
        </p>
      ))}
      {area.evidence.length > 0 && (
        <>
          <p className="area-preview">{area.evidence[0].summary}</p>
          <details className="area-sources">
            <summary>View sources and scope</summary>
            {area.evidence.map((record) => (
              <article className="area-source" key={record.evidence_id}>
                <div className="area-source-tags">
                  <Tag color={record.kind === "official" ? "blue" : undefined}>
                    {evidenceLabels[record.kind]}
                  </Tag>
                  {record.freshness === "needs_review" && (
                    <Tag color="orange">Needs rechecking</Tag>
                  )}
                  {record.freshness === "background" && (
                    <Tag>Background reference</Tag>
                  )}
                </div>
                <p>{record.summary}</p>
                <a
                  href={record.source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {record.source.publisher} · {record.source.title} ↗
                </a>
                <p className="muted small">Scope: {record.scope_label}</p>
                <p className="muted small">
                  {record.source.published_at
                    ? `Published: ${record.source.published_at}`
                    : "Publication date not provided"}
                  {record.source.updated_at
                    ? ` · Updated: ${record.source.updated_at}`
                    : ""}
                  {` · Checked: ${record.source.checked_at}`}
                </p>
                {record.source.data_period && (
                  <p className="muted small">
                    Data period: {record.source.data_period}
                  </p>
                )}
                <p className="area-source-limit small">{record.limitation}</p>
              </article>
            ))}
          </details>
        </>
      )}
    </div>
  );
}

export default function AreaAdvice({
  report,
  onSuggest,
  disabled,
}: {
  report?: AreaAdviceReport;
  onSuggest?: (text: string) => void;
  disabled?: boolean;
}) {
  if (!report) return null;
  return (
    <section className="area-advice" aria-label="Area lifestyle advice">
      <div className="area-advice-heading">
        <h3>Find an area that fits your lifestyle</h3>
        <span className="muted small">
          Coverage: {report.coverage.covered_suburbs} /{" "}
          {report.coverage.catalog_suburbs} areas
        </span>
      </div>
      {report.criteria_summary && (
        <p className="small area-criteria">
          Current criteria: {report.criteria_summary}
        </p>
      )}
      {report.priorities.length > 0 ? (
        <div
          className="area-priorities"
          aria-label="Current lifestyle preferences"
        >
          <span className="small muted">Your priorities</span>
          {report.priorities.map((p) => (
            <Tag color="blue" key={p.topic}>
              {p.label}
            </Tag>
          ))}
        </div>
      ) : (
        <p className="muted small">
          Tell me whether parks, dining and shopping, libraries or quiet matter
          most to help narrow the options.
        </p>
      )}
      <p className="muted small">
        The listings below use your current housing criteria
        {report.budget_applied
          ? " and whole-property weekly budget"
          : "; The budget cannot yet be compared directly with advertised weekly rent, so no rent filter was applied"}
        .Lifestyle information is a reference; check the commute separately.
      </p>
      <div className="area-advice-grid">
        {report.areas.map((area) => (
          <article
            key={area.suburb}
            className="area-advice-card"
            aria-label={area.suburb + " Area reference"}
          >
            <h4>{area.suburb}</h4>
            <p className="small">
              Current snapshot: {area.matching_count} listings matching your
              housing criteria
            </p>
            {area.min_weekly_rent != null && (
              <p className="area-inventory-rent">
                AUD {area.min_weekly_rent}
                {area.max_weekly_rent !== area.min_weekly_rent
                  ? `–${area.max_weekly_rent}`
                  : ""}
                <small>/week · advertised rent</small>
              </p>
            )}
            <AreaEvidenceDetails area={area} />
            {onSuggest && area.matching_count > 0 && (
              <Button
                size="small"
                aria-label={`In ${area.suburb} find a home`}
                disabled={disabled}
                onClick={() =>
                  onSuggest(
                    `Keep my budget and housing needs, recommend listings in ${area.suburb} and check the commute to the University of Sydney main campus.`,
                  )
                }
              >
                Find homes in this area
              </Button>
            )}
          </article>
        ))}
      </div>
      {!report.areas.length && (
        <p>
          No areas currently have listings matching these housing and
          comparable-budget criteria. Adjust the criteria and compare again.
        </p>
      )}
      <details className="area-report-notes">
        <summary>Scope of this information</summary>
        <ul>
          {report.limitations.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </details>
    </section>
  );
}
