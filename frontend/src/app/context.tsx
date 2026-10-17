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
export const currentConfirmation = (state: CaseState) =>
  state.confirmations.find((c) => c.fingerprint === state.draft.fingerprint);
