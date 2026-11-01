import { createContext, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { App } from "antd";
import type { HousingAd } from "../../api/catalog";
import { api, newRequestId, post } from "../../api/client";
import { useCase } from "../../app/context";

import FollowupDialog, {
  type SelectionSource,
  type SelectionResult,
} from "./FollowupDialog";

export interface FavoriteHome {
  listing: HousingAd;
  saved_at: string;
  in_catalog: boolean;
}
interface Favorites {
  items: FavoriteHome[];
  loading: boolean;
  busy: boolean;
  error: string | null;
  reload: () => void;
  toggle: (listing: HousingAd) => void;
  choose: (
    listing: HousingAd,
    source?: SelectionSource,
    onSaved?: (value: SelectionResult) => void,
  ) => void;
}
const Context = createContext<Favorites | null>(null);
export const useFavorites = () => {
  const value = useContext(Context);
  if (!value) throw new Error("Favorites context unavailable");
  return value;
};

export default function FavoritesProvider({
  children,
}: {
  children: ReactNode;
}) {
  const { current, config, refresh } = useCase();
  const { message } = App.useApp();
  const [items, setItems] = useState<FavoriteHome[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [selection, setSelection] = useState<{
    listing: HousingAd;
    source: SelectionSource;
    onSaved?: (value: SelectionResult) => void;
  } | null>(null);
  const active = useRef(false);
  const mounted = useRef(true);
  const root = `/cases/${encodeURIComponent(current.case_id)}`;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (config.mode !== "real_listings") {
      setLoading(false);
      return;
    }
    let valid = true;
    setLoading(true);
    api<{ items: FavoriteHome[] }>(root + "/favorites")
      .then((value) => {
        if (valid) {
          setItems(value.items);
          setError(null);
        }
      })
      .catch((e) => {
        if (valid)
          setError(
            e instanceof Error ? e.message : "Could not load favorites.",
          );
      })
      .finally(() => {
        if (valid) setLoading(false);
      });
    return () => {
      valid = false;
    };
  }, [root, revision, config.mode]);

  const toggle = async (listing: HousingAd) => {
    if (active.current || loading) return;
    active.current = true;
    setBusy(true);
    const saved = !items.some(
      (item) => item.listing.listing_id === listing.listing_id,
    );
    try {
      const value = await post<{ items: FavoriteHome[] }>(root + "/favorites", {
        request_id: newRequestId(),
        listing_id: listing.listing_id,
        saved,
      });
      if (!mounted.current) return;
      setItems(value.items);
      setError(null);
      message.success(
        saved ? "Added to favorites." : "Removed from favorites.",
      );
    } catch (e) {
      if (mounted.current)
        message.error(
          e instanceof Error
            ? e.message
            : "Could not save favorite. Please try again.",
        );
    } finally {
      active.current = false;
      if (mounted.current) setBusy(false);
    }
  };
  const choose = (
    listing: HousingAd,
    source: SelectionSource = {},
    onSaved?: (value: SelectionResult) => void,
  ) => {
    setSelection({ listing, source, onSaved });
  };
  return (
    <Context.Provider
      value={{
        items,
        loading,
        busy,
        error,
        reload: () => {
          if (!active.current) setRevision((v) => v + 1);
        },
        toggle,
        choose,
      }}
    >
      {children}
      {selection && (
        <FollowupDialog
          key={selection.listing.listing_id}
          caseId={current.case_id}
          listing={selection.listing}
          source={selection.source}
          replacing={
            current.selection &&
            current.selection.listing_id !== selection.listing.listing_id
              ? String(current.selection.listing_snapshot.address)
              : undefined
          }
          onClose={() => setSelection(null)}
          onSaved={async (value) => {
            await refresh();
            if (!mounted.current) return;
            selection.onSaved?.(value);
            setSelection(null);
            message.success(
              "Property selected. Prepare an inspection or generate a lease draft.",
            );
          }}
        />
      )}
    </Context.Provider>
  );
}
