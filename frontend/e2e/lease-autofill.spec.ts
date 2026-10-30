import { test, expect, type APIRequestContext } from "@playwright/test";
import { writeFile } from "node:fs/promises";
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
  const r = await (
    await request.post(root + "/evaluations", {
      data: { request_id: "run", confirmation_version: 1 },
    })
  ).json();
  await request.post(root + "/selections", {
    data: {
      request_id: "choose",
      run_id: r.run_id,
      listing_id: r.report.pending_confirmation[0].listing_id,
      confirmed: true,
    },
  });
  return { c, root };
}
test("calendar lease lengths calculate end dates, preserve explicit custom dates and clear periodic terms", async ({
  page,
  request,
}) => {
  const { c } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await page.getByLabel("Lease type", { exact: true }).click();
  await page.getByRole("option", { name: "Fixed term", exact: true }).click();
  await expect(
    page
      .locator(".ant-form-item")
      .filter({ has: page.getByLabel("Lease duration", { exact: true }) }),
  ).toContainText("1 year");
  await page.getByLabel("Lease duration", { exact: true }).click();
  await page.getByRole("option", { name: "6 months", exact: true }).click();
  await page.getByLabel("Lease start date", { exact: true }).fill("2026-08-31");
  await expect(page.getByLabel("End date", { exact: true })).toHaveValue(
    "2027-02-28",
  );
  await expect(page.getByLabel("End date", { exact: true })).toBeDisabled();
  await page.getByLabel("Lease duration", { exact: true }).click();
  await page.getByRole("option", { name: "1 year", exact: true }).click();
  await expect(page.getByLabel("End date", { exact: true })).toHaveValue(
    "2027-08-31",
  );
  await page.getByLabel("Lease duration", { exact: true }).click();
  await page.getByRole("option", { name: "Custom dates", exact: true }).click();
  await expect(page.getByLabel("End date", { exact: true })).toBeEnabled();
  await page.getByLabel("End date", { exact: true }).fill("2026-08-01");
  await page
    .getByRole("button", { name: "Check and fill contract", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Confirm lease draft save", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("The end date must be after the start date.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByLabel("Lease type", { exact: true }).click();
  await page
    .getByRole("option", {
      name: "Periodic tenancy (no end date)",
      exact: true,
    })
    .click();
  await expect(page.getByLabel("End date", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("End date", { exact: true })).toBeDisabled();
});
test("chosen addresses populate structured PDF boxes, additional fields and a standard calendar term", async ({
  page,
  request,
}) => {
  const { c, root } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  for (const [prefix, street, suburb, postcode] of [
    ["Landlord", "1 Example Street", "Redfern", "2016"],
    ["Tenant", "Unit 2001, 10 Example Street", "Redfern", "2016"],
    ["Landlord agent", "2 Example Road", "Burwood", "2134"],
  ]) {
    if (prefix === "Landlord agent")
      await page
        .getByText("Landlord agent (if applicable)", { exact: true })
        .click();
    await page
      .getByLabel(`${prefix} notice address`, { exact: true })
      .fill(street);
    await page.getByLabel(`${prefix} State`, { exact: true }).fill("NSW");
    await page.getByLabel(`${prefix} suburb`, { exact: true }).fill(suburb);
    const field =
      prefix === "Landlord"
        ? "landlord"
        : prefix === "Tenant"
          ? "tenant"
          : "agent";
    await page
      .locator(`#${field}_notice_suburb_list`)
      .getByRole("option", { name: `${suburb} · NSW ${postcode}`, exact: true })
      .click();
    await expect(
      page.getByLabel(`${prefix} notice address`, { exact: true }),
    ).toHaveValue(street);
    await expect(
      page.getByLabel(`${prefix} suburb`, { exact: true }),
    ).toHaveValue(suburb);
    await expect(
      page.getByLabel(`${prefix} State`, { exact: true }),
    ).toHaveValue("NSW");
    await expect(
      page.getByLabel(`${prefix} postcode`, { exact: true }),
    ).toHaveValue(postcode);
  }
  await page.getByLabel("Lease scope", { exact: true }).click();
  await page
    .getByRole("option", {
      name: "Standard NSW whole-property residential tenancy",
      exact: true,
    })
    .click();
  await page.getByLabel("Lease type", { exact: true }).click();
  await page.getByRole("option", { name: "Fixed term", exact: true }).click();
  await page.getByLabel("Lease duration", { exact: true }).click();
  await page.getByRole("option", { name: "6 months", exact: true }).click();
  await page.getByLabel("Lease start date", { exact: true }).fill("2026-08-31");
  await page.getByText("Signing details (optional)", { exact: true }).click();
  await page
    .getByLabel("Proposed signing date", { exact: true })
    .fill("2026-08-20");
  await page
    .getByLabel("Proposed signing location", { exact: true })
    .fill("Sydney");
  await page
    .getByRole("button", { name: "Check and fill contract", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "Confirm lease draft save",
    exact: true,
  });
  await expect(modal).toContainText("2016");
  await expect(modal).toContainText("6 months");
  await modal.getByRole("checkbox").check();
  await modal
    .getByRole("button", {
      name: "Confirm and save unsigned draft",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Contract preview · v1", exact: true }),
  ).toBeVisible();
  const list = await (await request.get(root + "/lease-drafts")).json();
  const draft = await (
    await request.get(root + `/lease-drafts/${list.items[0].draft_id}`)
  ).json();
  expect(draft.fields.landlord_notice_postcode).toBe("2016");
  expect(draft.fields.tenant_notice_suburb).toBe("Redfern");
  expect(draft.fields.agent_notice_postcode).toBe("2134");
  expect(draft.fields.end_date).toBe("2027-02-28");
  expect(draft.fields.lease_term_months).toBe(6);
  const pdf = await request.get(
    root + `/lease-drafts/${list.items[0].draft_id}/pdf?version=1`,
  );
  expect(pdf.ok()).toBe(true);
  await writeFile("/tmp/lease-autofill-browser.pdf", await pdf.body());
  await page.reload();
  await expect(
    page.getByLabel("Landlord postcode", { exact: true }),
  ).toHaveValue("2016");
  await expect(page.getByLabel("End date", { exact: true })).toHaveValue(
    "2027-02-28",
  );
});

test("mobile property search ignores late results and permits explicit manual addresses", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 900 });
  const { c } = await seed(request);
  const redfern = await (
    await request.get("/api/v1/lease-addresses?q=Redfern")
  ).json();
  const burwood = await (
    await request.get("/api/v1/lease-addresses?q=Burwood")
  ).json();
  let releaseOld!: () => void;
  const oldGate = new Promise<void>((resolve) => {
    releaseOld = resolve;
  });
  let oldStarted = false;
  await page.route("**/api/v1/lease-addresses?*", async (route) => {
    const q = new URL(route.request().url()).searchParams.get("q");
    if (q === "Redfern") {
      oldStarted = true;
      await oldGate;
      await route.fulfill({ json: redfern });
    } else if (q === "Burwood") await route.fulfill({ json: burwood });
    else await route.fulfill({ json: { items: [], source: "local_catalog" } });
  });
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  const input = page.getByLabel("Property address", { exact: true });
  await input.fill("Redfern");
  await expect.poll(() => oldStarted).toBe(true);
  await input.fill("Burwood");
  const list = page.locator("#address_list");
  await expect(list).toContainText("Burwood");
  const oldResponse = page.waitForResponse((r) =>
    r.url().includes("/lease-addresses?q=Redfern"),
  );
  releaseOld();
  await oldResponse;
  await expect(list).not.toContainText("Redfern");
  await list
    .getByRole("option")
    .filter({ has: page.locator('[data-address-kind="address"]') })
    .first()
    .click();
  await expect(
    page.getByLabel("Property postcode", { exact: true }),
  ).toHaveValue("2134");
  await input.fill("Unit 20, Unlisted Example Road");
  await expect(
    page.getByLabel("Property postcode", { exact: true }),
  ).toHaveValue("");
  await page.getByLabel("Property suburb", { exact: true }).fill("Sydney");
  await page.getByLabel("Property State", { exact: true }).fill("NSW");
  await page.getByLabel("Property postcode", { exact: true }).fill("2000");
  await expect(input).toHaveValue("Unit 20, Unlisted Example Road");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
