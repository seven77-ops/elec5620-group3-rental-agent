import { test, expect, type APIRequestContext } from "@playwright/test";
import { readFile } from "node:fs/promises";
async function seed(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json(),
    root = `/api/v1/cases/${c.case_id}`;
  await request.post(root + "/profile-confirmations", {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  const run = await (
    await request.post(root + "/evaluations", {
      data: { request_id: "run", confirmation_version: 1 },
    })
  ).json();
  const row = run.report.pending_confirmation[0];
  expect(
    (
      await request.post(root + "/selections", {
        data: {
          request_id: "select",
          run_id: run.run_id,
          listing_id: row.listing_id,
          confirmed: true,
        },
      })
    ).ok(),
  ).toBe(true);
  return { c, root, row };
}
test("official lease draft requires confirmation, saves versions, reloads and downloads an unsigned PDF", async ({
  page,
  request,
}, info) => {
  const { c, root, row } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await expect(
    page.getByRole("heading", { name: "Contract assistant", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Property address", { exact: true }),
  ).toHaveValue(row.address);
  await expect(
    page.getByLabel("Proposed rent (AUD)", { exact: true }),
  ).toHaveValue("");
  await expect(
    page.getByRole("heading", {
      name: "Enter contract details directly",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Parties", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", {
      name: "Contract details description",
      exact: true,
    }),
  ).not.toBeVisible();
  await page.getByLabel("Lease scope", { exact: true }).click();
  await page
    .getByRole("option", {
      name: "Standard NSW whole-property residential tenancy",
      exact: true,
    })
    .click();
  for (const [label, value] of [
    ["Landlord name", "Example Owner"],
    ["Landlord contact details", "owner@example.com"],
    ["Landlord notice address", "1 Example Road, Sydney NSW 2000"],
    ["Tenant names (one per line)", "张三"],
    ["Tenant contact details", "tenant@example.com"],
    ["Lease start date", "2026-11-01"],
    ["End date", "2027-11-01"],
    ["Proposed rent (AUD)", "600"],
    ["Proposed bond (AUD)", "2400"],
    ["Maximum agreed occupants", "2"],
    ["First rent payment date", "2026-11-01"],
    ["Rent due day", "每周一"],
  ])
    await page.getByLabel(label, { exact: true }).fill(value);
  await page.getByLabel("Lease type", { exact: true }).click();
  await page.getByRole("option", { name: "Fixed term", exact: true }).click();
  await page.getByLabel("Rent period", { exact: true }).click();
  await page.getByRole("option", { name: "Weekly", exact: true }).click();
  await page
    .getByRole("button", { name: "Check and fill contract", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "Confirm lease draft save",
    exact: true,
  });
  await expect(modal).toContainText("张三");
  expect(
    (await (await request.get(root + "/lease-drafts")).json()).items,
  ).toHaveLength(0);
  await expect(
    modal.getByRole("button", {
      name: "Confirm and save unsigned draft",
      exact: true,
    }),
  ).toBeDisabled();
  await modal.getByRole("checkbox").check();
  await modal
    .getByRole("button", {
      name: "Confirm and save unsigned draft",
      exact: true,
    })
    .click();
  const preview = page.getByRole("dialog", {
    name: "Contract preview · v1",
    exact: true,
  });
  await expect(preview).toBeVisible();
  await expect(
    preview.locator('iframe[title="Completed contract draft v1"]'),
  ).toHaveAttribute("src", /^blob:/);
  await expect(
    preview.getByRole("link", {
      name: "Download this PDF version",
      exact: true,
    }),
  ).toHaveAttribute("href", /\/pdf\?version=1$/);
  await preview
    .getByRole("button", { name: "Return to form", exact: true })
    .click();
  const link = page.getByRole("link", {
    name: "Download saved v1 PDF",
    exact: true,
  });
  await expect(link).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await link.click();
  const download = await downloadPromise;
  const file = info.outputPath("lease-v1.pdf");
  await download.saveAs(file);
  expect((await readFile(file)).subarray(0, 4).toString()).toBe("%PDF");
  const state = await (await request.get(root)).json();
  expect(state.selection.contract_ready).toBe(false);
  expect(state.reviews).toHaveLength(0);
  await page.reload();
  await expect(
    page.getByLabel("Proposed rent (AUD)", { exact: true }),
  ).toHaveValue(/^600(?:\.00)?$/);
  await page.getByLabel("Proposed rent (AUD)", { exact: true }).fill("610");
  await expect(
    page.getByText(
      "The form has unsaved changes. Preview and download still use saved v1.",
      {
        exact: true,
      },
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Preview saved v1 contract", exact: true })
    .click();
  await expect(
    preview.locator('iframe[title="Completed contract draft v1"]'),
  ).toHaveAttribute("src", /^blob:/);
  expect(
    (await (await request.get(root + "/lease-drafts")).json()).items[0].version,
  ).toBe(1);
  await preview
    .getByRole("button", { name: "Return to form", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Check and fill contract", exact: true })
    .click();
  await modal.getByRole("checkbox").check();
  await modal
    .getByRole("button", {
      name: "Confirm and save unsigned draft",
      exact: true,
    })
    .click();
  const v2Preview = page.getByRole("dialog", {
    name: "Contract preview · v2",
    exact: true,
  });
  await expect(
    v2Preview.locator('iframe[title="Completed contract draft v2"]'),
  ).toHaveAttribute("src", /^blob:/);
  await v2Preview
    .getByRole("button", { name: "Return to form", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "Download saved v2 PDF", exact: true }),
  ).toBeVisible();
  let releaseVersion!: () => void;
  const versionGate = new Promise<void>((resolve) => {
    releaseVersion = resolve;
  });
  let markRequested!: () => void;
  const requested = new Promise<void>((resolve) => {
    markRequested = resolve;
  });
  await page.route(
    /\/lease-drafts\/lease-draft-.*\?version=1$/,
    async (route) => {
      markRequested();
      await versionGate;
      await route.continue();
    },
  );
  await page
    .getByRole("combobox", { name: "Draft version", exact: true })
    .click();
  await page.getByRole("option", { name: "Draft 1 · v1", exact: true }).click();
  await requested;
  try {
    await expect(
      page.getByRole("button", {
        name: "New draft for current candidate",
        exact: true,
      }),
    ).toBeDisabled();
    await expect(
      page.getByLabel("Proposed rent (AUD)", { exact: true }),
    ).toBeDisabled();
  } finally {
    releaseVersion();
  }
  await expect(
    page.getByText("Viewing a historical version", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Proposed rent (AUD)", { exact: true }),
  ).toHaveValue(/^600(?:\.00)?$/);
  await page
    .getByRole("button", {
      name: "New draft for current candidate",
      exact: true,
    })
    .click();
  await expect(
    page.getByLabel("Property address", { exact: true }),
  ).toHaveValue(row.address);
  await expect(
    page.getByLabel("Proposed rent (AUD)", { exact: true }),
  ).toHaveValue("");
  await page
    .getByRole("tab", { name: "Upload contract for review", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Upload your contract", exact: true }),
  ).toBeVisible();
});

test("AI only fills the form after review and never creates a draft automatically", async ({
  page,
  request,
}) => {
  const { c, root } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await page
    .getByRole("button", { name: "AI-assisted entry (optional)", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Contract details description", exact: true })
    .fill("整租，每周600，押金2400，租客 Zhang San");
  await expect(
    page.getByRole("button", {
      name: "Extract contract details with AI",
      exact: true,
    }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", {
      name: "I agree to send this text to the configured external AI for this field extraction.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", {
      name: "Extract contract details with AI",
      exact: true,
    })
    .click();
  const modal = page.getByRole("dialog", {
    name: "Check AI-extracted fields",
    exact: true,
  });
  await expect(modal).toContainText("Zhang San");
  await expect(
    page.getByLabel("Proposed rent (AUD)", { exact: true }),
  ).toHaveValue("");
  await modal
    .getByRole("button", {
      name: "Fill these fields into the form",
      exact: true,
    })
    .click();
  await expect(
    page.getByLabel("Proposed rent (AUD)", { exact: true }),
  ).toHaveValue(/^600(?:\.00)?$/);
  await expect(
    page.getByLabel("Tenant names (one per line)", { exact: true }),
  ).toHaveValue("Zhang San");
  expect(
    (await (await request.get(root + "/lease-drafts")).json()).items,
  ).toHaveLength(0);
});

test("saved PDF preview can retry a failed load on mobile without saving another version", async ({
  page,
  request,
}) => {
  const { c, root } = await seed(request);
  const context = await (
    await request.get(root + "/lease-drafts/context")
  ).json();
  const saved = await (
    await request.post(root + "/lease-drafts", {
      data: {
        request_id: "preview-retry",
        context_token: context.context_token,
        expected_version: 0,
        confirmed: true,
        applicability_confirmed: true,
        fields: {
          ...context.defaults,
          rental_mode: "whole_property",
          tenant_names: "Preview Tenant",
          rent_amount: 700,
          rent_period: "week",
        },
      },
    })
  ).json();
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  let allowPdf = false;
  await page.route("**/lease-drafts/*/pdf?version=1", async (route) => {
    if (!allowPdf) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: { message: "PDF 暂时无法读取" } }),
      });
    } else await route.continue();
  });
  await page
    .getByRole("button", { name: "Preview saved v1 contract", exact: true })
    .click();
  const preview = page.getByRole("dialog", {
    name: "Contract preview · v1",
    exact: true,
  });
  await expect(preview).toContainText("Unable to complete this action");
  await expect(preview).not.toContainText("PDF 暂时无法读取");
  allowPdf = true;
  await preview
    .getByRole("button", { name: "Reload preview", exact: true })
    .click();
  await expect(
    preview.locator('iframe[title="Completed contract draft v1"]'),
  ).toHaveAttribute("src", /^blob:/);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    (
      await (
        await request.get(root + `/lease-drafts/${saved.draft_id}?version=1`)
      ).json()
    ).version,
  ).toBe(1);
  await preview
    .getByRole("button", { name: "Return to form", exact: true })
    .click();
  await expect(
    page.getByLabel("Tenant names (one per line)", { exact: true }),
  ).toHaveValue("Preview Tenant");
});

test("mobile contract assistant fits and missing candidate has a useful next step", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await expect(
    page.getByRole("button", { name: "My rental needs", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const seeded = await seed(request);
  await page.goto(`/cases/${seeded.c.case_id}/contract?mode=draft`);
  await expect(
    page.getByLabel("Property address", { exact: true }),
  ).toBeEnabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await expect(
    page.getByRole("menuitem", { name: "Contract assistant", exact: true }),
  ).toBeVisible();
});

test("AI extraction timeout preserves text and manual fields, retries once and never saves automatically", async ({
  page,
  request,
}) => {
  const { c, root } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await page.getByLabel("Landlord name", { exact: true }).fill("Manual Owner");
  await page
    .getByRole("button", { name: "AI-assisted entry (optional)", exact: true })
    .click();
  const text = "整租，每周600，押金2400，租客 Zhang San";
  await page
    .getByRole("textbox", { name: "Contract details description", exact: true })
    .fill(text);
  await page
    .getByRole("checkbox", {
      name: "I agree to send this text to the configured external AI for this field extraction.",
      exact: true,
    })
    .check();
  const ids: string[] = [];
  await page.route("**/lease-drafts/proposals", async (route) => {
    ids.push(route.request().postDataJSON().request_id);
    if (ids.length === 1)
      await route.fulfill({
        status: 504,
        json: {
          error: {
            code: "lease_ai_timeout",
            message:
              "Lease extraction timed out. Your original text and completed fields are retained. Retry or process smaller sections.",
          },
        },
      });
    else {
      const response = await route.fetch();
      const result = await response.json();
      await route.fulfill({
        response,
        json: {
          ...result,
          warnings: [
            {
              field: "rent_due_day",
              label: "Rent due day",
              message:
                "Source or field-role checks failed. Complete this field manually.",
            },
          ],
        },
      });
    }
  });
  await page
    .getByRole("button", {
      name: "Extract contract details with AI",
      exact: true,
    })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Contract extraction timed out",
  );
  await expect(
    page.getByRole("textbox", {
      name: "Contract details description",
      exact: true,
    }),
  ).toHaveValue(text);
  await expect(page.getByLabel("Landlord name", { exact: true })).toHaveValue(
    "Manual Owner",
  );
  await page
    .getByRole("button", { name: "Retry original action", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "Check AI-extracted fields",
    exact: true,
  });
  await expect(modal).toContainText("Zhang San");
  await expect(modal.getByRole("alert")).toContainText(
    "These fields were not filled automatically: Rent due day",
  );
  expect(ids).toHaveLength(2);
  expect(ids[0]).toBe(ids[1]);
  expect(
    (await (await request.get(root + "/lease-drafts")).json()).items,
  ).toHaveLength(0);
  await modal
    .getByRole("button", {
      name: "Fill these fields into the form",
      exact: true,
    })
    .click();
  await expect(page.getByLabel("Landlord name", { exact: true })).toHaveValue(
    "Manual Owner",
  );
  await expect(
    page.getByLabel("Proposed rent (AUD)", { exact: true }),
  ).toHaveValue(/^600(?:\.00)?$/);
});
