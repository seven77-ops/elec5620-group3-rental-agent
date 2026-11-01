import { api, post } from "./client";
import type { OperatorReview } from "./operator";
export const getIssueReports = () =>
  api<{ items: OperatorReview[] }>("/issue-reports");
export const submitIssueReport = (
  caseId: string,
  body: {
    request_id: string;
    category: string;
    description: string;
    attachment_ids: string[];
  },
) =>
  post<OperatorReview>(
    `/cases/${encodeURIComponent(caseId)}/issue-reports`,
    body,
  );
