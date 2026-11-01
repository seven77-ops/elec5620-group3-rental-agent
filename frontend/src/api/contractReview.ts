import { api } from "./client";
import type { Evidence } from "./types";

export interface ContractCheck {
  id: string;
  label: string;
  status: "passed" | "issue" | "needs_confirmation";
  detail: string;
  value?: string | number | null;
  evidence: Evidence[];
  question?: string;
}
export interface ContractChecklist {
  review_id: string;
  review_version: number;
  document_name: string;
  total: number;
  passed: ContractCheck[];
  attention: ContractCheck[];
  analysis: {
    status:
      "not_run" | "success" | "partial" | "failed" | "stale" | "unavailable";
    analysis_id?: string;
  };
  summary: string;
}
export const getContractChecklist = (reviewId: string) =>
  api<ContractChecklist>(
    `/contract-reviews/${encodeURIComponent(reviewId)}/checklist`,
  );
