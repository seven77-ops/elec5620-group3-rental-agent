import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGOUDNjCwMDAxAAGAAzrASEtu9dZAAAAAElFTkSuQmCC",
  "base64",
);
const PDF = Buffer.from("%PDF-1.4\n%%EOF\n");
async function start(page: Page, request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=moveout`);
  await expect(
    page.getByRole("heading", { name: "Issue report", exact: true }),
  ).toBeVisible();
  return c.case_id as string;
}
async function fill(page: Page, description: string) {
  const form = page.getByRole("region", { name: "Report issue", exact: true });
  await form.getByLabel("Issue type", { exact: true }).click();
  await page.getByRole("option", { name: "Furniture", exact: true }).click();
  await form.getByLabel("Issue description", { exact: true }).fill(description);
  return form;
}

test("flat report needs only type description and files, records date and reaches Human review", async ({
  page,
  request,
}) => {
  const cid = await start(page, request);
  const description = "Fictional broken chair. 家具问题原文保留。";
  const form = await fill(page, description);
  for (const label of [
    "Move-out plan and tasks",
    "Bond follow-up",
    "Local reminders",
  ]) {
    await expect(
      page.getByRole("tab", { name: label, exact: true }),
    ).toHaveCount(0);
  }
  await expect(
    page.getByText("Confirmed lease details", { exact: true }),
  ).toHaveCount(0);
  await expect(form.locator('input[type="date"]')).toHaveCount(0);
  await expect(form.locator('input[type="file"]')).toBeHidden();
  await expect(
    form.getByRole("button", { name: "Upload files", exact: true }),
  ).toBeVisible();
  await form.getByLabel("Add evidence files", { exact: true }).setInputFiles([
    { name: "chair.png", mimeType: "image/png", buffer: PNG },
    { name: "receipt.pdf", mimeType: "application/pdf", buffer: PDF },
  ]);
  await expect(
    form.getByRole("button", { name: "Submit report", exact: true }),
  ).toBeEnabled();
  await form
    .getByRole("button", { name: "Submit report", exact: true })
    .click();
  const history = page.getByRole("region", {
    name: "Issue report history",
    exact: true,
  });
  await expect(history).toContainText(description);
  await expect(history).toContainText(/\d{4}-\d{2}-\d{2}/);
  await expect(
    history.getByRole("link", { name: "receipt.pdf", exact: true }),
  ).toBeVisible();
  const c = await (await request.get(`/api/v1/cases/${cid}`)).json();
  expect(c.aftercare_case_id).toBeNull();
  await page
    .getByRole("menuitem", { name: "Human review", exact: true })
    .click();
  const item = page.locator(
    `[data-testid="operator-review"][data-case-id="${cid}"]`,
  );
  await expect(item).toContainText(description);
  await expect(item).not.toContainText("undefined");
  await expect(
    item.getByRole("img", { name: "chair.png", exact: true }),
  ).toBeVisible();
  await item
    .getByLabel("Review advice", { exact: true })
    .fill("Ask the agent to inspect the chair using the attached photo.");
  await item
    .getByRole("button", {
      name: "Save advice and complete review",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("region", { name: "Review history", exact: true }),
  ).toContainText("Ask the agent to inspect the chair");
  await page
    .locator(`[data-testid="operator-review"][data-case-id="${cid}"]`)
    .getByRole("button", { name: "View report", exact: true })
    .click();
  await expect(history).toContainText("Ask the agent to inspect the chair");
  await page.screenshot({
    path: "/tmp/flat-issue-history.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("tab", { name: "Report issue", exact: true }).click();
  await page.screenshot({ path: "/tmp/flat-issue-report.png", fullPage: true });
});

test("mobile upload and report retry keep one file and one submission without a tenancy", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const cid = await start(page, request);
  const description = "Fictional mobile furniture issue";
  const form = await fill(page, description);
  let lostFile = false,
    lostReport = false;
  await page.route("**/living-services/attachments?*", async (route) => {
    if (route.request().method() === "POST" && !lostFile) {
      lostFile = true;
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  await form.getByLabel("Add evidence files", { exact: true }).setInputFiles({
    name: "mobile-receipt.pdf",
    mimeType: "application/pdf",
    buffer: PDF,
  });
  await form.getByRole("button", { name: "Retry upload", exact: true }).click();
  await expect(
    form.getByRole("button", { name: "Submit report", exact: true }),
  ).toBeEnabled();
  await page.route(`**/api/v1/cases/${cid}/issue-reports`, async (route) => {
    if (route.request().method() === "POST" && !lostReport) {
      lostReport = true;
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  await form
    .getByRole("button", { name: "Submit report", exact: true })
    .click();
  await expect(
    form.getByLabel("Issue description", { exact: true }),
  ).toHaveValue(description);
  await form
    .getByRole("button", { name: "Retry original action", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Issue report history", exact: true }),
  ).toContainText(description);
  const history = await (await request.get("/api/v1/issue-reports")).json();
  expect(
    history.items.filter((row: { case_id: string }) => row.case_id === cid),
  ).toHaveLength(1);
  const files = await (
    await request.get(`/api/v1/cases/${cid}/living-services/attachments`)
  ).json();
  expect(files.items).toHaveLength(1);
  await page.screenshot({ path: "/tmp/flat-issue-mobile.png", fullPage: true });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("history retains earlier submitted move-out reports while the new form hides old setup", async ({
  page,
  request,
}) => {
  const cid = await start(page, request);
  const response = await request.post("/api/v1/aftercare/commands", {
    data: {
      case_id: cid,
      request_id: crypto.randomUUID(),
      expected_version: 0,
      operation: "create",
      payload: {
        tenancy: {
          address: "Fictional older home",
          jurisdiction: "NSW",
          tenancy_type: "standard_residential",
          confirmed: true,
          source_ref: "user-entered:test",
          source_version: 1,
          rooms: null,
          carpeted: null,
          outdoor: null,
          furnished: null,
          inventory: null,
          inventory_confirmed: false,
          baseline_evidence_refs: [],
        },
        evidence: [],
      },
    },
  });
  expect(response.ok()).toBeTruthy();
  const created = await response.json();
  const saved = await request.post("/api/v1/aftercare/commands", {
    data: {
      case_id: cid,
      request_id: crypto.randomUUID(),
      expected_version: created.version,
      operation: "report_issue",
      payload: {
        category: "cleaning",
        title: "Earlier cleaning issue",
        description: "Original report from the earlier screen.",
        requested_outcome: "Check the records.",
        amount_cents: null,
        evidence_refs: [],
        tenant_confirmed: true,
      },
    },
  });
  expect(saved.ok()).toBeTruthy();
  await page.reload();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Issue report history", exact: true }),
  ).toContainText("Original report from the earlier screen.");
  const original = page
    .getByRole("article")
    .filter({ hasText: "Original report from the earlier screen." });
  await original
    .getByRole("button", { name: "Original report details", exact: true })
    .click();
  await expect(original).toContainText("Check the records.");
  await expect(
    page.getByText("Confirmed lease details", { exact: true }),
  ).toHaveCount(0);
});
