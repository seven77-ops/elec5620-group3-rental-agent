import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const permission =
  "I am authorised to upload this contract and agree to send it to the AI service for review.";
const cleanText =
  "Address: 1 Example Street, Sydney NSW 2000\nLandlord: Morgan Example\nTenant: Taylor Example\nRent: AUD 650 per week whole property\nBond: AUD 2600\nStart date: 2026-11-01\nEnd date: 2027-11-01\n";

async function start(page: Page, request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/contract?mode=review`);
  await expect(
    page.getByRole("heading", { name: "Upload your contract", exact: true }),
  ).toBeVisible();
  return c;
}
async function submit(page: Page, buffer: Buffer, name = "test-contract.txt") {
  await page.getByLabel("Select contract", { exact: true }).setInputFiles({
    name,
    mimeType: name.endsWith("pdf") ? "application/pdf" : "text/plain",
    buffer,
  });
  const upload = page.getByRole("button", {
    name: "Upload and analyse",
    exact: true,
  });
  await expect(upload).toBeDisabled();
  await page.getByRole("checkbox", { name: permission, exact: true }).check();
  await upload.click();
  await expect(
    page.getByRole("heading", { name: "Contract check results", exact: true }),
  ).toBeVisible();
}

test("uploading a PDF runs AI once and shows real passed and attention checks without workflow panels", async ({
  page,
  request,
}, info) => {
  const c = await start(page, request);
  const external: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "POST" && req.url().endsWith("/ai-analyses"))
      external.push(req.url());
  });
  await submit(
    page,
    readFileSync(resolve(process.cwd(), "e2e/fixtures/date-conflict.pdf")),
    "date-conflict.pdf",
  );
  expect(external).toHaveLength(1);
  const result = page.getByRole("region", {
    name: "Contract review results",
    exact: true,
  });
  const attention = result.getByRole("region", {
    name: "Checks needing attention",
    exact: true,
  });
  const passed = result.getByRole("region", {
    name: "Passed checks",
    exact: true,
  });
  await expect(attention).toContainText("Agreement date order");
  await expect(attention).toContainText(
    "The end date is not after the start date",
  );
  await expect(passed).toContainText("Property address");
  await expect(passed).toContainText("Whole property");
  await expect(passed).not.toContainText("whole_property");
  await expect(passed).toContainText("2026-11-01");
  const reviewId = await result.getAttribute("data-review-id");
  const report = await (
    await request.get(`/api/v1/contract-reviews/${reviewId}/checklist`)
  ).json();
  expect(report.analysis.status).toBe("success");
  expect(report.total).toBe(report.passed.length + report.attention.length);
  await expect(attention.getByRole("heading", { level: 2 })).toHaveText(
    `Needs attention (${report.attention.length})`,
  );
  await expect(passed.getByRole("heading", { level: 2 })).toHaveText(
    `Passed (${report.passed.length})`,
  );
  const date = attention
    .locator(".contract-check-item")
    .filter({ hasText: "Agreement date order" });
  await date.getByText("View source text", { exact: true }).click();
  await expect(date.locator("blockquote").first()).toContainText(
    "Start date: 2026-11-01",
  );
  for (const old of [
    "Waiting for a reviewer",
    "Awaiting human review",
    "AI-assisted check",
    "Manage this contract",
    "Prepare question list",
    "Edit contract details",
    "Ask more about this contract",
  ]) {
    await expect(result).not.toContainText(old);
  }
  await page.screenshot({
    path: info.outputPath("contract-review-desktop.png"),
    fullPage: true,
    animations: "disabled",
  });
  const saved = await (
    await request.get(`/api/v1/contract-reviews/${reviewId}`)
  ).json();
  expect(saved.version).toBe(1);
  expect(saved.fields.end_date.value).toBe("2026-10-31");
  const current = await (
    await request.get(`/api/v1/cases/${c.case_id}`)
  ).json();
  expect(current.draft).toEqual(c.draft);
  expect(current.confirmations).toEqual(c.confirmations);
  await page.reload();
  await expect(
    page.getByRole("region", { name: "Checks needing attention", exact: true }),
  ).toContainText("Agreement date order");
});

test("a clean contract shows the actual all-passed result without inventing a fixed number of checks", async ({
  page,
  request,
}) => {
  await start(page, request);
  await submit(page, Buffer.from(cleanText));
  const result = page.getByRole("region", {
    name: "Contract review results",
    exact: true,
  });
  await expect(result).toContainText("No issues found in completed checks");
  await expect(
    result.getByRole("heading", { name: "Needs attention (0)", exact: true }),
  ).toBeVisible();
  const reviewId = await result.getAttribute("data-review-id");
  const report = await (
    await request.get(`/api/v1/contract-reviews/${reviewId}/checklist`)
  ).json();
  expect(report.attention).toEqual([]);
  expect(report.passed.length).toBeGreaterThan(0);
  expect(report.total).toBe(report.passed.length);
});

test("missing fields and failed AI remain visible and never become an all-clear result", async ({
  page,
  request,
}) => {
  await start(page, request);
  // Exercise the existing server-side failed-result recording, with no fabricated successful AI response.
  await page.route("**/contract-reviews/*/ai-analyses", (route) =>
    route.fulfill({
      status: 503,
      json: {
        error: { code: "ai_timeout", message: "Synthetic analysis timeout" },
      },
    }),
  );
  await submit(
    page,
    Buffer.from(
      "Address: 1 Example Street, Sydney NSW 2000\nRent: AUD 650 per week whole property\nThis incomplete agreement has no parties, bond or lease dates.\n",
    ),
  );
  const result = page.getByRole("region", {
    name: "Contract review results",
    exact: true,
  });
  await expect(result).toContainText("AI analysis did not complete");
  await expect(
    result.getByRole("region", {
      name: "Checks needing attention",
      exact: true,
    }),
  ).toContainText("Start date");
  await expect(result).not.toContainText(
    "No issues found in completed checks",
  );
  await expect(
    result.getByRole("button", { name: "Try AI again", exact: true }),
  ).toBeDisabled();
});

test("the compact result works on mobile and stopping processing preserves readable results", async ({
  page,
  request,
}, info) => {
  await page.setViewportSize({ width: 360, height: 844 });
  await start(page, request);
  await submit(page, Buffer.from(cleanText));
  await expect(
    page.getByRole("heading", { name: "Passed (12)", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const result = page.getByRole("region", {
    name: "Contract review results",
    exact: true,
  });
  await page.screenshot({
    path: info.outputPath("contract-review-mobile.png"),
    fullPage: true,
    animations: "disabled",
  });
  await result
    .getByRole("button", { name: "Stop processing this contract", exact: true })
    .click();
  await expect(result).toContainText("Processing permission is inactive");
  await expect(
    result.getByRole("region", { name: "Passed checks", exact: true }),
  ).toContainText("Property address");
  await expect(
    result.getByRole("button", { name: "Analyse contract", exact: true }),
  ).toHaveCount(0);
  await result
    .getByRole("button", { name: "Upload another contract", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Upload your contract", exact: true }),
  ).toBeVisible();
});
