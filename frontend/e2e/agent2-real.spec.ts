import { test, expect } from "@playwright/test";
import { fillRentalNeeds, confirmRentalNeeds } from "./fillRentalNeeds";

test("real catalogue has 1000 ads, paginates, filters, and preserves unknowns", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (["error", "warning"].includes(m.type())) errors.push(m.text());
  });
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(
    page.getByRole("heading", { name: "Housing recommendations", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /Filtered results.*1000/ }),
  ).toBeVisible();
  const catalogue = await (
    await request.get("/api/v1/listings?page_size=1")
  ).json();
  expect(catalogue.catalog.suburb_count).toBe(72);
  await expect(
    page.getByTestId("real-catalog").locator("tbody tr.ant-table-row"),
  ).toHaveCount(20);
  const first = await page
    .getByTestId("real-catalog")
    .locator("tbody tr.ant-table-row")
    .first()
    .innerText();
  await page.locator(".ant-pagination-item-2").click();
  await expect(
    page.getByTestId("real-catalog").locator("tbody tr.ant-table-row").first(),
  ).not.toHaveText(first);
  await page
    .getByRole("spinbutton", { name: "Minimum bedrooms", exact: true })
    .fill("2");
  await page
    .getByRole("spinbutton", { name: "Minimum bathrooms", exact: true })
    .fill("2");
  await page
    .getByRole("spinbutton", { name: "Minimum car spaces", exact: true })
    .fill("1");
  await page
    .getByRole("spinbutton", { name: "Maximum weekly rent (AUD)", exact: true })
    .fill("1500");
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(page.locator(".ant-spin-spinning")).toHaveCount(0);
  const rows = page
    .getByTestId("real-catalog")
    .locator("tbody tr.ant-table-row");
  await expect(rows.first()).toBeVisible();
  for (const row of await rows.all()) {
    const cells = row.locator("td");
    expect(Number(await cells.nth(1).innerText())).toBeGreaterThanOrEqual(2);
    expect(Number(await cells.nth(2).innerText())).toBeGreaterThanOrEqual(2);
    expect(Number(await cells.nth(3).innerText())).toBeGreaterThanOrEqual(1);
    expect(
      Number((await cells.nth(4).innerText()).replace(/[^\d.]/g, "")),
    ).toBeLessThanOrEqual(1500);
  }
  await page
    .getByRole("button", { name: "View listing details", exact: true })
    .first()
    .click();
  await expect(page.getByRole("dialog")).not.toContainText("Items to confirm");
  await expect(
    page.getByRole("dialog").getByRole("link", { name: "View Domain listing" }),
  ).toHaveAttribute("href", /^https:\/\/www.domain.com.au\//);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("spinbutton", { name: "Maximum weekly rent (AUD)", exact: true })
    .fill("1");
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(
    page.getByText(
      "No listings match these criteria. Adjust budget or housing needs, or explicitly increase the campus commute limit.",
    ),
  ).toBeVisible();
  expect(errors).toEqual([]);
  await expect(page.locator("vite-error-overlay")).toHaveCount(0);
});

test("confirmed Agent1 profile allows durable selection without manual report actions", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await request.post(`/api/v1/cases/${c.case_id}/profile-confirmations`, {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(
    page.getByRole("heading", { name: "Housing recommendations", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Generate candidate report for current filters",
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", {
      name: "Download live candidate report",
      exact: true,
    }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Select and follow up", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Confirm and start follow-up", exact: true })
    .click();
  await expect(
    page.getByText("Property selected for follow-up", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Property selected for follow-up", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/Current preferences v\d+ · Candidate report saved/),
  ).toHaveCount(0);
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.selection.data_mode).toBe("real_listings");
  expect(saved.selection.contract_ready).toBe(false);
  expect(saved.selection.listing_snapshot.weekly_rent).toBeGreaterThan(0);
  await page.getByRole("menuitem", { name: "Contract assistant" }).click();
  await page
    .getByRole("tab", { name: "Upload contract for review", exact: true })
    .click();
  await expect(
    page.getByText("Review an existing contract directly", { exact: true }),
  ).toBeVisible();
});

test("reload restores the filters bound to the latest real report", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await request.post(`/api/v1/cases/${c.case_id}/profile-confirmations`, {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  await request.post(`/api/v1/cases/${c.case_id}/evaluations`, {
    data: {
      request_id: "filtered",
      confirmation_version: 1,
      filters: { suburb: "Rhodes", min_bedrooms: 2 },
    },
  });
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(
    page.getByTestId("real-catalog").locator("tbody tr.ant-table-row").first(),
  ).toBeVisible();
  await expect(
    page.getByRole("spinbutton", { name: "Minimum bedrooms", exact: true }),
  ).toHaveValue("2");
  const rows = page
    .getByTestId("real-catalog")
    .locator("tbody tr.ant-table-row");
  await expect(rows.first()).toContainText("Rhodes");
  for (const row of await rows.all()) await expect(row).toContainText("Rhodes");
});

test("mobile catalogue and source details stay usable", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/real-data`);
  await expect(
    page.getByRole("heading", { name: /Filtered results.*1000/ }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/agent2-real-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "/tmp/agent2-real-desktop.png",
    fullPage: true,
  });
});

test("a late saved report does not overwrite filters the user is editing", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await request.post(`/api/v1/cases/${c.case_id}/profile-confirmations`, {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  const run = await (
    await request.post(`/api/v1/cases/${c.case_id}/evaluations`, {
      data: {
        request_id: "saved",
        confirmation_version: 1,
        filters: { suburb: "Rhodes", max_weekly_rent: 1500 },
      },
    })
  ).json();
  let release!: () => void, entered!: () => void;
  const hold = new Promise<void>((resolve) => {
    release = resolve;
  });
  const seen = new Promise<void>((resolve) => {
    entered = resolve;
  });
  await page.route(`**/api/v1/evaluations/${run.run_id}`, async (route) => {
    entered();
    await hold;
    await route.continue();
  });
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await seen;
  await page
    .getByRole("spinbutton", { name: "Maximum weekly rent (AUD)", exact: true })
    .fill("1000");
  const response = page.waitForResponse(`**/api/v1/evaluations/${run.run_id}`);
  release();
  await response;
  await expect(
    page.getByRole("spinbutton", {
      name: "Maximum weekly rent (AUD)",
      exact: true,
    }),
  ).toHaveValue("1000");
});

test("preferences generate mapped budget and housing filters in the merged recommendations page", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/preferences`);
  await expect(page).toHaveURL(
    new RegExp(`/cases/${c.case_id}/assistant\\?needs=1$`),
  );
  await fillRentalNeeds(page, {
    suburb: "Rhodes",
    budget: 1500,
    bedrooms: 2,
    bathrooms: 2,
    parking: 1,
  });
  await confirmRentalNeeds(page);
  await page
    .getByRole("menuitem", { name: "Housing recommendations", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Housing recommendations", exact: true }),
  ).toBeVisible();
  for (const [name, value] of [
    ["Maximum weekly rent (AUD)", "1500"],
    ["Minimum bedrooms", "2"],
    ["Minimum bathrooms", "2"],
    ["Minimum car spaces", "1"],
  ]) {
    await expect(
      page.getByRole("spinbutton", { name, exact: true }),
    ).toHaveValue(value);
  }
  expect(
    (
      await (await request.get(`/api/v1/cases/${c.case_id}`)).json()
    ).confirmations.at(-1).version,
  ).toBe(1);
  await expect(
    page.getByRole("menuitem", { name: "Real data", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByTestId("real-catalog").locator("tbody tr.ant-table-row").first(),
  ).toContainText("Rhodes");
  await page.reload();
  await expect(
    page.getByRole("spinbutton", {
      name: "Maximum weekly rent (AUD)",
      exact: true,
    }),
  ).toHaveValue("1500");
  await page.goto(`/cases/${c.case_id}/real-data`);
  await expect(page).toHaveURL(
    new RegExp(`/cases/${c.case_id}/recommendations$`),
  );
  await expect(
    page.getByText("Additional listing tools", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("tab", { name: "Rent reference", exact: true }),
  ).toHaveCount(0);
  expect(errors).toEqual([]);
});
