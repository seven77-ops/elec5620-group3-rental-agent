import { api } from "./client";
import type { LivingAttachment } from "./living";
import type { Dict, Review } from "./types";

export interface OperatorReview {
  is_demo?: boolean;
  kind: "aftercare" | "contract" | "issue";
  case_id: string;
  review_id: string;
  address: string;
  version: number;
  status: string;
  reason: string;
  created_at: string;
  decisions: Dict[];
  claims?: Dict[];
  history?: Dict[];
  evidence?: Dict[];
  attachments?: LivingAttachment[];
  report?: Dict;
  updates?: Dict[];
  review?: Review;
}

export function getOperatorReviews() {
  return api<{ items: OperatorReview[]; pending_count: number }>(
    "/operator/reviews",
  );
}
