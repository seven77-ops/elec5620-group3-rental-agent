import { api } from "./client";
import type { Dict, Review } from "./types";

export interface OperatorReview {
  kind: "aftercare" | "contract";
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
  review?: Review;
}

export function getOperatorReviews(key: string) {
  return api<{ items: OperatorReview[]; pending_count: number }>(
    "/operator/reviews",
    {
      headers: { "X-Operator-Key": key },
    },
  );
}
