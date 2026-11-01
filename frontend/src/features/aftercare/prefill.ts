import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { Json } from "../../api/types";

export interface PrefillValue {
  value: Json;
  source: "contract_review" | "selected_listing";
  label: string;
  quote?: string | null;
}
export interface TenancyPrefill {
  source_ref: string | null;
  values: Partial<
    Record<
      | "address"
      | "move_out_date"
      | "start_date"
      | "bond_amount"
      | "rent_amount"
      | "rent_period"
      | "furnished",
      PrefillValue
    >
  >;
  warnings: string[];
}

/** Read-only proposals from the selected listing and latest contract review. */
export function useTenancyPrefill(caseId: string, refreshKey: unknown = null) {
  const [prefill, setPrefill] = useState<TenancyPrefill | null>(null);
  useEffect(() => {
    let valid = true;
    api<TenancyPrefill>(
      `/cases/${encodeURIComponent(caseId)}/aftercare/tenancy-prefill`,
    )
      .then((value) => {
        if (valid) setPrefill(value);
      })
      // Prefill is optional help; the form stays fully usable without it.
      .catch(() => {
        if (valid) setPrefill(null);
      });
    return () => {
      valid = false;
    };
  }, [caseId, refreshKey]);
  return prefill;
}
