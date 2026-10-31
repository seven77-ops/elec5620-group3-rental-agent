import { Button, Pagination } from "antd";
import { useRef, useState, type ReactNode } from "react";
import type { HousingAd } from "../../api/catalog";

export default function ListingResults({
  listings,
  children,
}: {
  listings: HousingAd[];
  children: (listing: HousingAd) => ReactNode;
}) {
  const pageSize = 20;
  const [expanded, setExpanded] = useState(listings.length <= pageSize);
  const [page, setPage] = useState(1);
  const start = useRef<HTMLDivElement>(null);
  const current = Math.min(
    page,
    Math.max(1, Math.ceil(listings.length / pageSize)),
  );
  if (!listings.length) return null;
  return (
    <section
      className="assistant-listing-results"
      aria-label="Filtered listings"
    >
      <div className="assistant-listing-results-heading">
        <span>Filtered {listings.length} listings</span>
        <Button
          size="small"
          aria-expanded={expanded}
          onClick={() => {
            setExpanded(!expanded);
            setPage(1);
          }}
        >
          {expanded
            ? "Collapse listings"
            : `View all ${listings.length} listings`}
        </Button>
      </div>
      {expanded && (
        <>
          <div className="assistant-listings" ref={start}>
            {listings
              .slice((current - 1) * pageSize, current * pageSize)
              .map(children)}
          </div>
          {listings.length > pageSize && (
            <nav
              className="assistant-listing-pagination"
              aria-label="Filtered listing pages"
            >
              <Pagination
                current={current}
                pageSize={pageSize}
                total={listings.length}
                showSizeChanger={false}
                responsive
                onChange={(value) => {
                  setPage(value);
                  start.current?.scrollIntoView({
                    block: "start",
                    behavior: "smooth",
                  });
                }}
              />
            </nav>
          )}
        </>
      )}
    </section>
  );
}
