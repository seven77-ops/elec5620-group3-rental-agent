import { test, expect } from "@playwright/test";

test("both agent roles and conditional contract details save separately and generate a PDF", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
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
  expect(
    (
      await request.post(root + "/selections", {
        data: {
          request_id: "choose",
          run_id: run.run_id,
          listing_id: run.report.pending_confirmation[0].listing_id,
          confirmed: true,
        },
      })
    ).status(),
  ).toBe(200);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await page.getByLabel("Lease scope", { exact: true }).click();
  await page
    .getByRole("option", {
      name: "Standard NSW whole-property residential tenancy",
      exact: true,
    })
    .click();
  await page
    .getByText("Landlord agent (if applicable)", { exact: true })
    .click();
  await page
    .getByLabel("Landlord agent name / company", { exact: true })
    .fill("Owner Agency");
  await page
    .getByLabel("Landlord agent contact details (must include phone)", {
      exact: true,
    })
    .fill("0400000001");
  await page
    .getByLabel("Landlord agent notice address", { exact: true })
    .fill("1 Owner Agency Road");
  await page
    .getByLabel("Landlord agent suburb", { exact: true })
    .fill("Rhodes");
  await page.getByLabel("Landlord agent State", { exact: true }).fill("NSW");
  await page
    .getByLabel("Landlord agent postcode", { exact: true })
    .fill("2138");
  await page.getByText("Tenant agent (if applicable)", { exact: true }).click();
  await page
    .getByLabel("Tenant agent name / company", { exact: true })
    .fill("Tenant Representative");
  await page
    .getByLabel("Tenant agent contact details", { exact: true })
    .fill("0400000002");
  await page
    .getByLabel("Tenant agent notice address", { exact: true })
    .fill("2 Representative Road");
  await page.getByLabel("Tenant agent suburb", { exact: true }).fill("Glebe");
  await page.getByLabel("Tenant agent State", { exact: true }).fill("NSW");
  await page.getByLabel("Tenant agent postcode", { exact: true }).fill("2037");
  const pick = async (label: string, option: string) => {
    const control = page.getByLabel(label, { exact: true });
    await control.click();
    const list = await control.getAttribute("aria-controls");
    await page
      .locator(`[id="${list}"]`)
      .getByRole("option", { name: option, exact: true })
      .click();
  };
  await pick("Separate water usage charge", "No");
  await pick("Smoke alarm type", "Battery powered");
  await pick("Tenant-replaceable alarm battery", "Yes");
  await page.getByLabel("Alarm battery type", { exact: true }).fill("AA");
  await pick("Landlord agrees to electronic service", "Yes");
  await page
    .getByLabel("Landlord email for electronic service", { exact: true })
    .fill("owner@example.com");
  await pick("Tenant agrees to electronic service", "No");
  await expect(
    page.getByLabel("Tenant email for electronic service", { exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Check and fill contract", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "Confirm lease draft save",
    exact: true,
  });
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
  const index = await (await request.get(root + "/lease-drafts")).json();
  const draft = await (
    await request.get(root + "/lease-drafts/" + index.items[0].draft_id)
  ).json();
  expect(draft.fields.agent_name).toBe("Owner Agency");
  expect(draft.fields.tenant_agent_name).toBe("Tenant Representative");
  expect(draft.fields.water_usage).toBe("no");
  expect(draft.fields.electricity_embedded).toBeNull();
  expect(draft.fields.smoke_battery_type).toBe("AA");
  expect(draft.fields.tenant_email_consent).toBe("no");
  expect(draft.fields.tenant_notice_email).toBe("");
  const pdf = await request.get(
    root + "/lease-drafts/" + draft.draft_id + "/pdf?version=1",
  );
  expect(pdf.status()).toBe(200);
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  await preview
    .getByRole("button", { name: "Return to form", exact: true })
    .click();
  await page.reload();
  await page.getByText("Tenant agent (if applicable)", { exact: true }).click();
  await expect(
    page.getByLabel("Tenant agent name / company", { exact: true }),
  ).toHaveValue("Tenant Representative");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/lease-form-mobile.png",
    animations: "disabled",
  });
});
