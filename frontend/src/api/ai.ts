import { api } from "./client";
import { useEffect, useState } from "react";
import type { Evidence, Json } from "./types";
export interface AiConfig {
  enabled: boolean;
  configured: boolean;
  provider: string;
  model: string | null;
  timeout_seconds: number;
}
export interface AiCall {
  task: string;
  provider: string;
  model: string | null;
  status: string;
  attempted: boolean;
  simulated?: boolean;
  started_at: string;
  duration_ms: number;
  provider_request_id?: string;
  provider_response_id?: string;
  usage?: Record<string, number>;
  error_code?: string;
}
export interface Candidate {
  field: string | null;
  value: Json;
  valid: boolean;
  reason: string | null;
  evidence: Evidence | null;
}
export interface AiResult {
  candidates?: Candidate[];
  preview_findings?: {
    id: string;
    title: string;
    reason: string;
    severity: string;
    evidence: Evidence[];
  }[];
  explanations?: { finding_id: string; text: string }[];
  explanation_status?: string;
  items?: { listing_id: string; text: string; evidence_refs: string[] }[];
}
export interface AiAnalysis {
  analysis_id: string;
  kind: string;
  status: string;
  created_at: string;
  binding: Record<string, string | number>;
  result: AiResult | null;
  calls: AiCall[];
  error?: { code: string; message: string };
  can_apply?: boolean;
}
export const aiPost = <T>(path: string, body: unknown) =>
  api<T>(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    { timeoutMs: 45_000 },
  );
export function useAiResource(path: string) {
  const [config, setConfig] = useState<AiConfig | null>(null);
  const [record, setRecord] = useState<AiAnalysis | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    Promise.all([
      api<AiConfig>("/ai/config"),
      api<AiAnalysis | null>(`${path}/latest`, undefined, { allowNull: true }),
    ])
      .then(([c, r]) => {
        if (active) {
          setConfig(c);
          setRecord(r);
          setLoadError(null);
        }
      })
      .catch((e) => {
        if (active) setLoadError(e);
      });
    return () => {
      active = false;
    };
  }, [path, revision]);
  return {
    config,
    record,
    setRecord,
    loadError,
    reload: () => setRevision((v) => v + 1),
  };
}
