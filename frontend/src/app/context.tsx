import { createContext, useContext } from "react";
import type { CaseState, DemoConfig } from "../api/types";
export interface CaseContextType {
  current: CaseState;
  config: DemoConfig;
  refresh: () => Promise<void>;
  go: (page: string) => void;
}
export const CaseContext = createContext<CaseContextType | null>(null);
export function useCase() {
  const value = useContext(CaseContext);
  if (!value) throw new Error("Case context unavailable");
  return value;
}
export const currentConfirmation = (state: CaseState) => {
  const latest = state.confirmations.at(-1);
  return state.agent1?.state === "Confirmed" &&
    latest?.version === state.agent1.latest_version &&
    latest.draft_revision === state.draft.revision &&
    latest.fingerprint === state.draft.fingerprint
    ? latest
    : undefined;
};
