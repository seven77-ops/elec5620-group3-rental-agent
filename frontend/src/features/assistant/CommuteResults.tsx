import { SoftPreferenceEvidence } from "./SoftPreferenceEvidence";
import { Alert, Button, Pagination, Tag } from "antd";
import { useRef, useState } from "react";
import type { AssistantMessage } from "../../api/assistant";
import type { HousingAd } from "../../api/catalog";
import "./commuteResults.css";
import ListingActions from "../favorites/ListingActions";
import { commuteModes, UsydCommuteMini } from "../real-data/UsydCommute";
import { usydDirections } from "../real-data/directions";
import ListingReasons from "./ListingReasons";

export default function CommuteResults({
  message,
  onSuggest,
  onView,
  onSave,
  disabled,
}: {
  message: AssistantMessage;
  onSuggest?: (text: string) => void;
  onView?: (listing: HousingAd) => void;
  onSave?: (listing: HousingAd) => void;
  disabled?: boolean;
}) {
  const result = message.commute_recommendation;
  const [suburb, setSuburb] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const homes = useRef<HTMLDivElement>(null);
  const suburbs = [
    ...new Set(message.listings.map((listing) => listing.suburb)),
  ];
  const filtered = message.listings.filter(
    (listing) => !suburb || listing.suburb === suburb,
  );
  const pageSize = 12;
  const currentPage = Math.min(
    page,
    Math.max(1, Math.ceil(filtered.length / pageSize)),
  );
  const shown = filtered.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );
  const chooseSuburb = (value: string | null) => {
    setSuburb(value);
    setPage(1);
  };
  if (!message.destination_options?.length && !result) return null;
  if (!result && message.destination_options?.length)
    return (
      <Alert
        type="info"
        title="The destination is now USYD main campus"
        description="Camperdown / Darlington · Fisher Library.Previous destination options have been retired."
        action={
          <Button
            disabled={disabled || !onSuggest}
            onClick={() =>
              onSuggest?.(
                "Keep my budget and housing needs, and recommend homes for commuting to the University of Sydney main campus.",
              )
            }
          >
            Continue with main campus
          </Button>
        }
      />
    );
  if (
    result &&
    result.destination.id !== "usyd:camperdown-darlington:fisher-library"
  )
    return (
      <Alert
        type="info"
        showIcon
        title="These results use a previous campus"
        description="Searches now use the University of Sydney Camperdown / Darlington main campus. Please generate new commute recommendations."
        action={
          <Button
            disabled={disabled || !onSuggest}
            onClick={() =>
              onSuggest?.(
                "Keep my budget and housing needs, and regenerate recommendations for USYD main campus with my original commute limit.",
              )
            }
          >
            Recommend again
          </Button>
        }
      />
    );
  return (
    <section
      className="commute-results"
      aria-label="Commute and area suggestions"
    >
      {result ? (
        <>
          <div className="commute-heading">
            <h3>Find homes near USYD main campus</h3>
            <Tag color="blue">Filtered</Tag>
          </div>
          <p className="commute-destination">
            Go to {result.destination.label}
          </p>
          <div
            className="commute-filter-tags"
            aria-label="Current commute criteria"
          >
            <Tag color="blue">
              {commuteModes.find(
                (m) => m.value === result.criteria.commute_mode,
              )?.label ?? "Public transport"}
              {result.criteria.commute_max_minutes
                ? ` ≤${result.criteria.commute_max_minutes} minutes`
                : ""}
            </Tag>
          </div>
          <p className="muted small">
            Found {result.matching_count ?? message.listings.length} listings
            within your commute criteria
          </p>
          {!message.listings.length && (
            <Alert
              type="info"
              showIcon
              title="No listings match the current criteria"
              description="Adjust your budget or housing needs, or explicitly increase the commute limit."
            />
          )}
          <div
            className="commute-area-buttons"
            role="group"
            aria-label="Browse listings by area"
          >
            <Button
              aria-label="All"
              autoInsertSpace={false}
              type={suburb === null ? "primary" : "default"}
              aria-pressed={suburb === null}
              onClick={() => chooseSuburb(null)}
            >
              All
            </Button>
            {suburbs.map((name) => (
              <Button
                key={name}
                type={suburb === name ? "primary" : "default"}
                aria-pressed={suburb === name}
                onClick={() => chooseSuburb(name)}
              >
                {name}
              </Button>
            ))}
          </div>
          {suburb && !filtered.length && (
            <p className="muted small">
              No listings from this area in the current results.
            </p>
          )}
          <div className="commute-homes" ref={homes}>
            {shown.map((listing) => {
              return (
                <article key={listing.listing_id} className="commute-home">
                  <div>
                    <h4>{listing.address}</h4>
                    <p className="small muted">
                      {listing.bedroom_label} bed · {listing.bathrooms} bath ·{" "}
                      {listing.car_spaces} car spaces
                    </p>
                    <strong className="commute-price">
                      AUD {listing.weekly_rent}
                      <small>/week</small>
                    </strong>
                  </div>
                  <div className="commute-route">
                    <UsydCommuteMini
                      listing={listing}
                      mode={result.criteria.commute_mode}
                    />
                  </div>
                  <ListingReasons
                    listing={listing}
                    criteria={result.criteria}
                    filters={message.recommendation_filters}
                  />
                  {message.soft_preferences && (
                    <SoftPreferenceEvidence
                      report={message.soft_preferences}
                      listingId={listing.listing_id}
                    />
                  )}
                  <div className="commute-actions">
                    {onView ? (
                      <Button size="small" onClick={() => onView(listing)}>
                        Listing details
                      </Button>
                    ) : null}
                    <ListingActions
                      listing={listing}
                      onSelect={onSave}
                      disabled={disabled}
                    />
                    <a
                      href={usydDirections(
                        listing,
                        result.criteria.commute_mode ?? "public_transport",
                      )}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Google Maps ↗
                    </a>
                  </div>
                </article>
              );
            })}
          </div>
          {filtered.length > pageSize && (
            <nav aria-label="Listing pages" className="commute-pagination">
              <Pagination
                current={currentPage}
                total={filtered.length}
                pageSize={pageSize}
                showSizeChanger={false}
                responsive
                onChange={(next) => {
                  setPage(next);
                  homes.current?.scrollIntoView({
                    block: "start",
                    behavior: "smooth",
                  });
                }}
              />
            </nav>
          )}
          {onSuggest && message.listings.length > 0 ? (
            <div className="commute-actions">
              <Button
                disabled={disabled}
                onClick={() =>
                  onSuggest(
                    "Keep all confirmed budget, housing and commute criteria. Show another set of recommendations, prioritising listings I have not seen before.",
                  )
                }
              >
                Show more options
              </Button>
              <Button
                disabled={disabled}
                onClick={() =>
                  onSuggest(
                    "Keep my housing needs and destination, and prioritise lower-rent listings.",
                  )
                }
              >
                Prioritise lower rent
              </Button>
              <Button
                disabled={disabled}
                onClick={() =>
                  onSuggest(
                    "Keep my budget and housing needs, and prioritise shorter commutes.",
                  )
                }
              >
                Prioritise shorter commute
              </Button>
              <Button
                disabled={disabled}
                onClick={() =>
                  onSuggest(
                    "Keep my other requirements. My maximum one-way commute is " +
                      Math.min(
                        240,
                        (result.criteria.commute_max_minutes ?? 40) + 10,
                      ) +
                      " minutes. Please recommend again.",
                  )
                }
              >
                Add 10 minutes to commute
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
