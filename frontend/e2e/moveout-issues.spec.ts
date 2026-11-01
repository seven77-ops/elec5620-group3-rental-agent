import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

async function seed(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const result = await request.post("/api/v1/aftercare/commands", {
    data: {
      case_id: c.case_id,
      request_id: crypto.randomUUID(),
      expected_version: 0,
      operation: "create",
      payload: {
        tenancy: {
          address: "5 Fictional Review Street, Sydney NSW 2000",
          jurisdiction: "NSW",
          tenancy_type: "standard_residential",
          confirmed: true,
          source_ref: "user-entered:issue-test",
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
  expect(result.ok(), await result.text()).toBeTruthy();
  return c.case_id as string;
}
async function openReport(page: Page) {
  await page
    .getByRole("button", { name: "Report a move-out issue", exact: true })
    .click();
  return page.getByRole("dialog", {
    name: "Report a move-out issue",
    exact: true,
  });
}
async function fillReport(page: Page) {
  const dialog = await openReport(page);
  await dialog.getByLabel("Issue type", { exact: true }).click();
  await page.getByRole("option", { name: "Cleaning", exact: true }).click();
  await dialog
    .getByLabel("Issue title", { exact: true })
    .fill("Fictional cleaning deduction");
  await dialog
    .getByLabel("What happened?", { exact: true })
    .fill(
      "The agent proposed a fictional AUD 180 cleaning deduction. 中介提出清洁扣款。",
    );
  await dialog
    .getByLabel("What help do you need?", { exact: true })
    .fill("Please review the cleaning records and advise on next steps.");
  await dialog
    .getByLabel("Amount involved (AUD, optional)", { exact: true })
    .fill("180");
  await dialog
    .getByRole("checkbox", {
      name: "I confirm this report is accurate to the best of my knowledge.",
      exact: true,
    })
    .check();
  return dialog;
}

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGOUDNjCwMDAxAAGAAzrASEtu9dZAAAAAElFTkSuQmCC",
  "base64",
);
const PDF = Buffer.from(
  "%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n",
);

// Historical UI coverage retained for reference; live replacement: issue-report.spec.ts.
test.beforeEach(() => {
  test.skip(
    true,
    "Historical planner/modal UI replaced by inline Issue report and History; backend Agent4 coverage retained.",
  );
});

test("report images and documents reach Human review and saved advice returns to the tenant", async ({
  page,
  request,
}) => {
  const cid = await seed(request);
  await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
  const dialog = await fillReport(page);
  await dialog.getByLabel("Add evidence files", { exact: true }).setInputFiles([
    { name: "争议截图.png", mimeType: "image/png", buffer: PNG },
    { name: "cleaning-receipt.pdf", mimeType: "application/pdf", buffer: PDF },
  ]);
  await expect(
    dialog.getByRole("button", { name: "Submit to Human review", exact: true }),
  ).toBeEnabled();
  await dialog
    .getByRole("button", { name: "Submit to Human review", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  const reports = page.getByRole("region", {
    name: "Move-out issues and human review",
    exact: true,
  });
  await expect(
    reports.getByRole("link", { name: "cleaning-receipt.pdf", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("menuitem", { name: "Human review", exact: true })
    .click();
  const item = page.locator(
    `[data-testid="operator-review"][data-case-id="${cid}"]`,
  );
  await expect(item).toContainText("中介提出清洁扣款。");
  const image = item.getByRole("img", { name: "争议截图.png", exact: true });
  await expect(image).toBeVisible();
  await expect
    .poll(() => image.evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBeGreaterThan(0);
  const pdf = item.getByRole("link", {
    name: "cleaning-receipt.pdf",
    exact: true,
  });
  const url = await pdf.getAttribute("href");
  expect(await (await request.get(url!)).body()).toEqual(PDF);
  await item
    .getByLabel("Review advice", { exact: true })
    .fill(
      "Compare the invoice with the exit inspection and request an itemised explanation.",
    );
  await page.screenshot({
    path: "/tmp/simple-human-review-evidence.png",
    fullPage: true,
  });
  await item
    .getByRole("button", {
      name: "Save advice and complete review",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("region", { name: "Review history", exact: true }),
  ).toContainText("Compare the invoice with the exit inspection");
  await page.reload();
  await page.getByRole("tab", { name: /History/ }).click();
  const saved = page.locator(
    `[data-testid="operator-review"][data-case-id="${cid}"]`,
  );
  await saved
    .getByRole("button", { name: "View aftercare record", exact: true })
    .click();
  await expect(reports).toContainText("Review complete");
  await expect(reports).toContainText(
    "Compare the invoice with the exit inspection",
  );
  await expect(
    reports.getByRole("link", { name: "cleaning-receipt.pdf", exact: true }),
  ).toBeVisible();
});

test("mobile upload and report retries preserve one file and one report", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const cid = await seed(request);
  await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
  const dialog = await fillReport(page);
  let lostUpload = false;
  let lostReport = false;
  await page.route("**/living-services/attachments?*", async (route) => {
    if (route.request().method() === "POST" && !lostUpload) {
      lostUpload = true;
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  await dialog.getByLabel("Add evidence files", { exact: true }).setInputFiles({
    name: "receipt.pdf",
    mimeType: "application/pdf",
    buffer: PDF,
  });
  await expect(
    dialog.getByRole("button", { name: "Submit to Human review", exact: true }),
  ).toBeDisabled();
  await dialog
    .getByRole("button", { name: "Retry upload", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "Submit to Human review", exact: true }),
  ).toBeEnabled();
  await page.route("**/api/v1/aftercare/commands", async (route) => {
    if (
      route.request().postDataJSON().operation === "report_issue" &&
      !lostReport
    ) {
      lostReport = true;
      await route.fetch();
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  await dialog
    .getByRole("button", { name: "Submit to Human review", exact: true })
    .click();
  await expect(dialog.getByLabel("Issue title", { exact: true })).toHaveValue(
    "Fictional cleaning deduction",
  );
  await dialog
    .getByRole("button", { name: "Retry original action", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  const c = await (await request.get(`/api/v1/cases/${cid}`)).json();
  const record = await (
    await request.get(`/api/v1/aftercare/cases/${c.aftercare_case_id}`)
  ).json();
  expect(record.reviews).toHaveLength(1);
  expect(record.reviews[0].attachments).toHaveLength(1);
  const files = await (
    await request.get(`/api/v1/cases/${cid}/living-services/attachments`)
  ).json();
  expect(files.items).toHaveLength(1);
  await page.screenshot({
    path: "/tmp/simple-human-review-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("reviewer keeps advice and can reload a report after a version conflict", async ({
  page,
  request,
}) => {
  const cid = await seed(request);
  await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
  const dialog = await fillReport(page);
  await dialog
    .getByRole("button", { name: "Submit to Human review", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  await page
    .getByRole("menuitem", { name: "Human review", exact: true })
    .click();
  const item = page.locator(
    `[data-testid="operator-review"][data-case-id="${cid}"]`,
  );
  await item
    .getByLabel("Review advice", { exact: true })
    .fill("Advice retained while a new tenant update arrives.");
  const c = await (await request.get(`/api/v1/cases/${cid}`)).json();
  const record = await (
    await request.get(`/api/v1/aftercare/cases/${c.aftercare_case_id}`)
  ).json();
  const updated = await request.post("/api/v1/aftercare/commands", {
    data: {
      case_id: cid,
      request_id: crypto.randomUUID(),
      expected_version: record.version,
      operation: "reply_review",
      payload: {
        review_id: record.reviews[0].review_id,
        text: "New fictional tenant information",
        evidence_refs: [],
        tenant_confirmed: true,
      },
    },
  });
  expect(updated.ok()).toBeTruthy();
  await item
    .getByRole("button", {
      name: "Save advice and complete review",
      exact: true,
    })
    .click();
  await expect(item.getByRole("alert")).toBeVisible();
  await item
    .getByRole("button", { name: "Load latest report", exact: true })
    .click();
  await expect(item).toContainText("New fictional tenant information");
  await expect(item.getByLabel("Review advice", { exact: true })).toHaveValue(
    "Advice retained while a new tenant update arrives.",
  );
  await item
    .getByRole("button", {
      name: "Save advice and complete review",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("region", { name: "Review history", exact: true }),
  ).toContainText("Advice retained while a new tenant update arrives.");
});
