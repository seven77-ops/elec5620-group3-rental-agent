import { Button } from "antd";
import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { ExportOutlined } from "@ant-design/icons";
import type { HousingAd } from "../../api/catalog";
import UsydCommute from "./UsydCommute";
import { refreshedCommute } from "./commuteRefresh";
import { ListingGallery } from "./ListingPhotos";
import "./listingDetails.css";

export default function ListingDetails({ listing }: { listing: HousingAd }) {
  const [current, setCurrent] = useState(listing);
  useEffect(() => {
    let active = true;
    setCurrent(listing);
    // Media may be added after a chat/report snapshot was saved, independently
    // of coordinates. Keep historical housing facts and personalised trips.
    api<HousingAd>(`/listings/${encodeURIComponent(listing.listing_id)}`)
      .then((fresh) => {
        if (
          !active ||
          fresh.listing_id !== listing.listing_id ||
          fresh.source_url !== listing.source_url
        )
          return;
        setCurrent({
          ...listing,
          photos: fresh.photos ?? listing.photos,
          usyd_commute: refreshedCommute(
            listing.usyd_commute,
            fresh.usyd_commute,
          ),
        });
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [listing]);
  return (
    <ListingDetailsBody
      listing={current.listing_id === listing.listing_id ? current : listing}
    />
  );
}

function ListingDetailsBody({ listing }: { listing: HousingAd }) {
  return (
    <article className="listing-detail" data-testid="listing-details">
      <header className="listing-detail-heading">
        <div className="listing-detail-location">
          {listing.suburb} · NSW {listing.postcode}
        </div>
        <h2>{listing.address}</h2>
        <div className="listing-detail-heading-bottom">
          <div
            className="listing-detail-rent"
            data-testid="listing-detail-rent"
          >
            <span>AUD</span> {listing.weekly_rent.toLocaleString("en-AU")}
            <small>/ week</small>
          </div>
        </div>
      </header>
      <ListingGallery key={listing.listing_id} listing={listing} />
      <dl
        className="listing-detail-summary"
        data-testid="listing-detail-summary"
      >
        <div>
          <dt>Bedrooms</dt>
          <dd>
            {listing.bedrooms}
            <small>
              {listing.bedroom_count_basis === "open_plan_as_one"
                ? "Studio"
                : " rooms"}
            </small>
          </dd>
        </div>
        <div>
          <dt>Bathrooms</dt>
          <dd>
            {listing.bathrooms}
            <small> rooms</small>
          </dd>
        </div>
        <div>
          <dt>Car spaces</dt>
          <dd>
            {listing.car_spaces}
            <small> spaces</small>
          </dd>
        </div>
      </dl>
      {listing.bedroom_count_basis === "open_plan_as_one" && (
        <p className="listing-detail-studio">
          The source lists 0 bedrooms. Shown as one open-plan sleeping area,
          rather than a separate bedroom.
        </p>
      )}
      {listing.property_type === "studio" &&
        listing.bedroom_count_basis !== "open_plan_as_one" && (
          <p className="listing-detail-studio">
            This is an open-plan studio. Confirm separate bedrooms at
            inspection.
          </p>
        )}
      <UsydCommute listing={listing} />
      <footer className="listing-detail-source">
        <Button
          aria-label="View Domain listing"
          href={listing.source_url}
          target="_blank"
          rel="noopener noreferrer"
          icon={<ExportOutlined />}
        >
          View Domain listing
        </Button>
      </footer>
    </article>
  );
}
