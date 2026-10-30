import { Button, Tag } from "antd";
import { HeartFilled, HeartOutlined } from "@ant-design/icons";
import type { HousingAd } from "../../api/catalog";
import { useCase, currentConfirmation } from "../../app/context";
import { useFavorites } from "./FavoritesContext";

export default function ListingActions({
  listing,
  onSelect,
  disabled = false,
  selectDisabled = false,
}: {
  listing: HousingAd;
  onSelect?: (listing: HousingAd) => void;
  disabled?: boolean;
  selectDisabled?: boolean;
}) {
  const { current } = useCase();
  const favorites = useFavorites();
  const saved = favorites.items.some(
    (item) => item.listing.listing_id === listing.listing_id,
  );
  const selected =
    current.selection?.listing_id === listing.listing_id &&
    current.selection.profile_fingerprint ===
      currentConfirmation(current)?.fingerprint;
  return (
    <>
      <Button
        size="small"
        icon={saved ? <HeartFilled /> : <HeartOutlined />}
        aria-label={saved ? "Remove favorite" : "Save listing"}
        aria-pressed={saved}
        disabled={
          disabled ||
          favorites.loading ||
          favorites.busy ||
          Boolean(favorites.error)
        }
        onClick={() => favorites.toggle(listing)}
      >
        {saved ? "Remove favorite" : "Save listing"}
      </Button>
      {selected ? (
        <Tag color="blue">Current follow-up property</Tag>
      ) : (
        <Button
          size="small"
          disabled={disabled || selectDisabled}
          onClick={() => (onSelect ?? favorites.choose)(listing)}
        >
          Select and follow up
        </Button>
      )}
    </>
  );
}
