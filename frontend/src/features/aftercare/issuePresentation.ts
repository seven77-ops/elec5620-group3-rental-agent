import type { Dict } from "../../api/types";

export const reportCategories = {
  rent: "Rent / bond",
  furniture: "Furniture",
  repairs: "Repairs",
  tenancy: "During the tenancy",
  moveout: "Moving out",
  post_tenancy: "After moving out",
  other: "Other",
};
export const issueCategories = {
  ...reportCategories,
  bond: "Bond / refund",
  cleaning: "Cleaning",
};
export const reviewDecisionNames: Record<string, string> = {
  annotate: "Reviewer note",
  return: "More information requested",
  hold: "Review on hold",
  refer: "Referral recommended",
  release: "Review complete",
};

export function reviewState(review: Dict): { label: string; color: string } {
  if (review.status === "released")
    return { label: "Review complete", color: "green" };
  if (review.status !== "open") return { label: "Closed", color: "default" };
  const decision = ((review.decisions ?? []) as Dict[]).at(-1);
  const update = ((review.updates ?? []) as Dict[]).at(-1);
  if (
    !decision ||
    (update && new Date(String(update.at)) > new Date(String(decision.at)))
  )
    return { label: "Awaiting human review", color: "blue" };
  if (decision.decision === "return")
    return { label: "More information needed", color: "orange" };
  if (decision.decision === "refer")
    return { label: "Referral recommended", color: "purple" };
  return { label: "In review", color: "gold" };
}
