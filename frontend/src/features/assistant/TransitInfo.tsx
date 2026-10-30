import type { AssistantMessage } from "../../api/assistant";
import "./commuteResults.css";

export default function TransitInfo({
  message,
}: {
  message: AssistantMessage;
}) {
  const info = message.transit_information;
  if (!info) return null;
  return (
    <section
      className="commute-results transit-information"
      aria-label="Listing transport information"
    >
      <h3>
        {info.topic === "nearby" ? "Nearby stops" : "Current service alerts"}
      </h3>
      <p className="small muted">{info.address}</p>
      {info.topic === "nearby" ? (
        <ul className="transit-stop-list">
          {info.stops.map((stop) => (
            <li key={stop.id}>
              <span>{stop.name}</span>
              <small>
                Approx. straight-line distance {stop.distance_m} metres
              </small>
            </li>
          ))}
        </ul>
      ) : (
        <>
          {info.stop_name && <p className="small">Stop: {info.stop_name}</p>}
          {info.alerts.length ? (
            <ul>
              {info.alerts.map((alert, i) => (
                <li key={i}>
                  {alert.title}{" "}
                  {alert.url && (
                    <a
                      href={alert.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      View details ↗
                    </a>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="small muted">
              No current public alerts were found for this stop. Check services
              before travelling.
            </p>
          )}
        </>
      )}
      <a
        className="small"
        href={info.source_url}
        target="_blank"
        rel="noopener noreferrer"
      >
        Transport for NSW ↗
      </a>
    </section>
  );
}
