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
    <section className="assistant-listing-results" aria-label="已筛选房源">
      <div className="assistant-listing-results-heading">
        <span>已筛选 {listings.length} 套房源</span>
        <Button
          size="small"
          aria-expanded={expanded}
          onClick={() => {
            setExpanded(!expanded);
            setPage(1);
          }}
        >
          {expanded ? "收起房源" : `查看全部${listings.length}套房源`}
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
              aria-label="已筛选房源分页"
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
