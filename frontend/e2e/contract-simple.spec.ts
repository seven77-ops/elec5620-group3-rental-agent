import { test, expect, type APIRequestContext } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

async function upload(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  const consent = await (
    await request.post(`${root}/contract-consents`, {
      data: { confirmed: true, scope: "document" },
    })
  ).json();
  const response = await request.post(`${root}/contract-reviews`, {
    headers: {
      "Content-Type": "application/octet-stream",
      "X-Consent-Id": consent.consent_id,
      "X-Request-Id": crypto.randomUUID(),
      "X-Filename": "simulated-contract.pdf",
    },
    data: readFileSync(
      resolve(process.cwd(), "e2e/fixtures/date-conflict.pdf"),
    ),
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return { c, review: (await response.json()).review };
}

test("contract review leads with saved PDF issues and keeps source evidence without diagnostics", async ({
  page,
  request,
}) => {
  const { c, review } = await upload(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=review`);
  await expect(
    page.getByRole("heading", { name: "Items to check", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("End date is not after start date", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Contract details", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("2026-11-01", { exact: true })).toBeVisible();
  await expect(page.getByText("2026-10-31", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "AI contract analysis", exact: true }),
  ).not.toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download review JSON" }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Review references and version history", { exact: true }),
  ).toHaveCount(0);
  const positions = await page
    .getByRole("heading", { name: /^(Items to check|Contract details)$/ })
    .allTextContents();
  expect(positions).toEqual(["Items to check", "Contract details"]);
  await page
    .getByRole("button", { name: "View source 1", exact: true })
    .click();
  const evidence = page.getByRole("dialog", {
    name: "Contract source evidence",
    exact: true,
  });
  await expect(evidence).toContainText("Start date: 2026-11-01");
  await expect(evidence.locator("pre")).toHaveCount(0);
  await page.keyboard.press("Escape");
  const unchanged = await (
    await request.get(`/api/v1/contract-reviews/${review.review_id}`)
  ).json();
  expect(unchanged).toEqual(review);
});

test("failed AI check explains next steps without exposing invalid candidate values or internal errors", async ({
  page,
  request,
}) => {
  const { c, review } = await upload(request);
  await page.route(
    `**/contract-reviews/${review.review_id}/ai-analyses/latest`,
    (route) =>
      route.fulfill({
        json: {
          analysis_id: "synthetic-failed-check",
          kind: "contract",
          status: "failed",
          created_at: "2026-10-30T10:00:00Z",
          binding: { review_version: review.version },
          can_apply: false,
          calls: [],
          error: {
            code: "ai_no_valid_candidates",
            message: "The model returned no verifiable valid candidate values.",
          },
          result: {
            candidates: [
              {
                field: "rent_amount",
                value: 99999,
                valid: false,
                reason: "quote must equal the complete original raw line",
                evidence: null,
              },
            ],
            preview_findings: [],
            explanations: [],
          },
        },
      }),
  );
  await page.goto(`/cases/${c.case_id}/contract?mode=review`);
  await page
    .getByRole("button", { name: "AI-assisted check", exact: true })
    .click();
  const ai = page.getByRole("region", {
    name: "AI contract analysis",
    exact: true,
  });
  await expect(ai).toContainText("AI could not confirm any changes");
  await expect(ai).toContainText("Your saved review is unchanged");
  await expect(ai).not.toContainText("99999");
  for (const technical of [
    "ai_no_valid_candidates",
    "raw line",
    "Model:",
    "Request timeout",
    "AI candidate fields",
    "This AI call",
  ]) {
    await expect(page.locator("body")).not.toContainText(technical);
  }
  await expect(
    ai.getByRole("button", { name: "Analyse contract with AI", exact: true }),
  ).toBeDisabled();
  await ai
    .getByRole("checkbox", {
      name: "I agree to send this contract to the AI service for this check.",
      exact: true,
    })
    .check();
  await expect(
    ai.getByRole("button", { name: "Analyse contract with AI", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByText("End date is not after start date", { exact: true }),
  ).toBeVisible();
});

test("essential review controls fit a 360px screen and history stays readable without raw data", async ({
  page,
  request,
}) => {
  const { c } = await upload(request);
  await page.setViewportSize({ width: 360, height: 844 });
  await page.goto(`/cases/${c.case_id}/contract?mode=review`);
  await page
    .getByRole("button", { name: "Edit contract details", exact: true })
    .click();
  const form = page.getByRole("dialog", {
    name: "Edit contract details",
    exact: true,
  });
  await expect(form.getByLabel("Lease end", { exact: true })).toHaveValue(
    "2026-10-31",
  );
  await form.getByRole("button", { name: "Cancel", exact: true }).click();
  await page
    .getByRole("button", { name: "Manage this contract", exact: true })
    .click();
  await page
    .getByRole("button", { name: "View review history", exact: true })
    .click();
  const history = page.getByRole("dialog", {
    name: "Review history",
    exact: true,
  });
  await expect(history).toContainText("End date is not after start date");
  await expect(history.locator("pre")).toHaveCount(0);
  await page.keyboard.press("Escape");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
