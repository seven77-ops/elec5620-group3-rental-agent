import { Button, Descriptions, Tag } from "antd";
import type {
  BookingStatus,
  HomeSummary,
  LivingProvider,
  Utility,
} from "../../api/living";

const utilityLabels: Record<Utility, string> = {
  electricity: "Electricity",
  gas: "Gas",
  internet: "Internet",
  water: "Water",
};
const statusLabels: Record<BookingStatus, string> = {
  considering: "Considering",
  contacted: "Contacted independently",
  booked: "Booked independently",
  completed: "Completed",
};
export type HomeServiceTarget = {
  tab: "utilities" | "services";
  booking?: string;
};

export default function HomeSavedServices({
  summary,
  providers,
  onOpen,
}: {
  summary: HomeSummary;
  providers: LivingProvider[];
  onOpen: (target: HomeServiceTarget) => void;
}) {
  const bookings = summary.bookings ?? [];
  return (
    <div className="home-saved-services">
      <section aria-label="Saved utility providers">
        <div className="home-saved-heading">
          <h3>Utilities</h3>
          <Button size="small" onClick={() => onOpen({ tab: "utilities" })}>
            Change utilities
          </Button>
        </div>
        <Descriptions
          column={1}
          items={(Object.keys(utilityLabels) as Utility[]).map((key) => {
            const id = summary.profile.utilities[key];
            return {
              key,
              label: utilityLabels[key],
              children: id
                ? providers.find((p) => p.id === id)?.name ||
                  "Provider details unavailable"
                : "Not selected",
            };
          })}
        />
      </section>
      <section aria-label="Saved moving and cleaning">
        <div className="home-saved-heading">
          <h3>Moving and cleaning</h3>
          <Button size="small" onClick={() => onOpen({ tab: "services" })}>
            Choose moving or cleaning
          </Button>
        </div>
        {!bookings.length && <p className="muted">No services saved yet.</p>}
        {[...bookings].reverse().map((booking) => {
          const provider = providers.find((p) => p.id === booking.provider_id);
          const name = provider?.name || "Saved service";
          const category = provider?.categories
            .filter((c) => c === "removalist" || c === "cleaner")
            .map((c) => (c === "removalist" ? "Moving" : "Cleaning"))
            .join(" · ");
          return (
            <article className="home-saved-service" key={booking.booking_id}>
              <div className="home-saved-heading">
                <strong>{name}</strong>
                <Tag>{statusLabels[booking.status]}</Tag>
              </div>
              {category && <p className="muted">{category}</p>}
              {(booking.service_date || booking.quote_amount !== null) && (
                <p className="home-saved-facts">
                  {booking.service_date && (
                    <span>
                      {new Intl.DateTimeFormat("en-AU", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                        timeZone: "UTC",
                      }).format(new Date(booking.service_date + "T12:00:00Z"))}
                    </span>
                  )}
                  {booking.quote_amount !== null && (
                    <strong>
                      AUD {booking.quote_amount.toLocaleString("en-AU")}
                    </strong>
                  )}
                </p>
              )}
              {booking.notes && (
                <p className="living-prewrap">{booking.notes}</p>
              )}
              <Button
                size="small"
                aria-label={`View ${name} record`}
                onClick={() =>
                  onOpen({ tab: "services", booking: booking.booking_id })
                }
              >
                View record
              </Button>
            </article>
          );
        })}
      </section>
    </div>
  );
}
