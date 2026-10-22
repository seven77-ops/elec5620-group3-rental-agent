import { useState } from "react";
import { Image } from "antd";
import type { HousingAd, HousingPhoto } from "../../api/catalog";
import { displayDate } from "./listingPresentation";
import "./listingPhotos.css";

function observedPhotos(listing: HousingAd): HousingPhoto[] {
  return (listing.photos ?? []).filter((photo) => {
    try {
      const url = new URL(photo.url);
      return (
        url.protocol === "https:" &&
        url.hostname === "rimh2.domainstatic.com.au" &&
        !url.username &&
        !url.password &&
        (!url.port || url.port === "443") &&
        photo.source_url === listing.source_url
      );
    } catch {
      return false;
    }
  });
}
const noPhoto = <span className="listing-photo-empty">暂无照片</span>;
export function ListingThumbnail({
  listing,
  onOpen,
}: {
  listing: HousingAd;
  onOpen: () => void;
}) {
  const photo = observedPhotos(listing)[0];
  const [failed, setFailed] = useState(false);
  return (
    <button
      className="listing-photo-thumb"
      type="button"
      aria-label={`查看 ${listing.address} 照片与详情`}
      onClick={onOpen}
    >
      {photo && !failed ? (
        <img
          key={photo.url}
          src={photo.url}
          alt={`${listing.address} 缩略图`}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      ) : (
        noPhoto
      )}
    </button>
  );
}
export function ListingGallery({ listing }: { listing: HousingAd }) {
  const photos = observedPhotos(listing);
  const [failed, setFailed] = useState<Set<string>>(() => new Set());
  const [preview, setPreview] = useState<string | null>(null);
  const available = photos.filter((photo) => !failed.has(photo.url));
  const current = available.findIndex((photo) => photo.url === preview);
  if (!photos.length)
    return <div className="listing-photo-gallery-empty">{noPhoto}</div>;
  return (
    <section className="listing-photo-gallery" aria-label="原始房源房源照片">
      <Image.PreviewGroup
        items={available.map((photo, index) => ({
          src: photo.url,
          alt: `${listing.address} 房源照片 ${index + 1}`,
          referrerPolicy: "no-referrer",
        }))}
        preview={{
          open: current >= 0,
          current: Math.max(0, current),
          onOpenChange: (open) => {
            if (!open) setPreview(null);
          },
          onChange: (index) => setPreview(available[index]?.url ?? null),
        }}
      >
        <div
          className={`listing-photo-grid listing-photo-count-${photos.length}`}
        >
          {photos.map((photo, index) => (
            <figure key={photo.url}>
              {failed.has(photo.url) ? (
                <div className="listing-photo-gallery-empty">{noPhoto}</div>
              ) : (
                <button
                  type="button"
                  className="listing-photo-preview-button"
                  aria-label={`预览 ${listing.address} 照片 ${index + 1}`}
                  onClick={() => setPreview(photo.url)}
                >
                  <img
                    src={photo.url}
                    alt={`${listing.address} 房源照片 ${index + 1}`}
                    loading="lazy"
                    decoding="async"
                    referrerPolicy="no-referrer"
                    onError={() =>
                      setFailed((previous) => new Set([...previous, photo.url]))
                    }
                  />
                  <span>放大查看</span>
                </button>
              )}
            </figure>
          ))}
        </div>
      </Image.PreviewGroup>
      <div className="listing-photo-caption">
        <a
          href={photos[0].source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          照片来源
        </a>
        <span>
          {photos.length} 张 · 照片采集于 {displayDate(photos[0].captured_at)}
        </span>
      </div>
    </section>
  );
}
