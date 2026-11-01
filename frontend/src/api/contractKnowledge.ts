import { api, newRequestId } from "./client";
import type { KnowledgeAnswer } from "./knowledge";
export interface ContractKnowledgeStatus {
  status:
    | "not_enabled"
    | "indexing"
    | "ready"
    | "needs_reindex"
    | "revoked"
    | "failed";
  context_token: string;
  review_id: string;
  review_version: number;
  source_name: string;
  page_count: number;
  allow_external_ai: boolean;
  grant_id: string | null;
  warnings: string[];
}
const root = (caseId: string, reviewId: string) =>
  `/cases/${encodeURIComponent(caseId)}/rag/contracts/${encodeURIComponent(reviewId)}`;
export const getContractKnowledge = (caseId: string, reviewId: string) =>
  api<ContractKnowledgeStatus>(root(caseId, reviewId) + "/status");
export const indexContractKnowledge = (
  caseId: string,
  reviewId: string,
  status: ContractKnowledgeStatus,
  external: boolean,
) =>
  api(
    root(caseId, reviewId) + "/index",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        request_id: newRequestId(),
        context_token: status.context_token,
        expected_version: status.review_version,
        confirmed: true,
        allow_external_ai: external,
      }),
    },
    { timeoutMs: 300_000 },
  );
export const forgetContractKnowledge = (caseId: string, reviewId: string) =>
  api(root(caseId, reviewId) + "/revoke", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
export const askContractKnowledge = (
  caseId: string,
  reviewId: string,
  status: ContractKnowledgeStatus,
  question: string,
  external: boolean,
) =>
  api<KnowledgeAnswer>(
    root(caseId, reviewId) + "/answers",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        context_token: status.context_token,
        question,
        allow_external_ai: external,
        language: "en",
      }),
    },
    { timeoutMs: 90_000 },
  );
