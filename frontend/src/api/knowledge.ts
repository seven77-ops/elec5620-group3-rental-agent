import { api } from "./client";
export interface KnowledgeAnswer {
  answer: string;
  status: "answered" | "sources_only" | "insufficient_evidence";
  knowledge_language: "en" | "original";
  scope?: "contract" | "public" | "product";
  language: "en" | "zh";
  question?: string;
  answer_language?: "en" | "zh" | "original";
  generation_outcome?: string;
  source_preserving?: boolean;
  private_binding?: unknown;
  citations: {
    evidence_id: string;
    document_id: string;
    title: string;
    section: string;
    source_url: string;
    checked_at: string | null;
    source_type?:
      | "official_guidance"
      | "official_template"
      | "student_guidance"
      | "product_guide"
      | "user_contract";
    page?: number;
    review_version?: number;
    line_start?: number;
    line_end?: number;
    document_version: string;
    quote: string;
  }[];
  unknowns: string[];
  warnings: string[];
  retrieval_methods: string[];
}
export const askKnowledge = (
  caseId: string,
  question: string,
  allowExternal: boolean,
  _language: "en" = "en",
) =>
  api<KnowledgeAnswer>(
    `/cases/${encodeURIComponent(caseId)}/rag/answers`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        allow_external_ai: allowExternal,
        language: "en",
      }),
    },
    { timeoutMs: 65_000 },
  );
