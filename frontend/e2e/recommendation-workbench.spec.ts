import { expect, test } from "@playwright/test";

test("zero-result alternatives apply one real change, expose reasons and keep working criteria across reload", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const reference = await (
    await request.get(
      `/api/v1/listings?case_id=${c.case_id}&min_bedrooms=2&min_bathrooms=1&usyd_mode=public_transport&usyd_max_minutes=30&sort=rent_asc`,
    )
  ).json();
  const cheapest = reference.items[0];
  expect(cheapest).toBeTruthy();
  const conversation = await (
    await request.post(`/api/v1/cases/${c.case_id}/assistant/conversations`, {
      data: {},
    })
  ).json();
  const root = `/api/v1/cases/${c.case_id}/assistant/conversations/${conversation.conversation_id}`;
  const brief = {
    recommend_areas: true,
    suburb: cheapest.suburb,
    budget_amount: cheapest.weekly_rent - 25,
    budget_period: "week",
    budget_scope: "whole_property",
    min_bedrooms: 2,
    min_bathrooms: 1,
    min_car_spaces: 0,
    rental_mode: "whole_property",
    occupants: 1,
    commute_mode: "public_transport",
    commute_max_minutes: 30,
  };
  const prepared = await request.post(`${root}/proposals`, {
    data: {
      request_id: `seed-${crypto.randomUUID()}`,
      expected_revision: 0,
      expected_profile_fingerprint: c.draft.fingerprint,
      brief,
    },
  });
  expect(prepared.ok()).toBe(true);
  const context = await (
    await request.get(`${root}/recommendation-context`)
  ).json();
  expect(context.total).toBe(0);
  const option = context.alternatives.find(
    (item: { id: string }) => item.id === "budget",
  );
  expect(option.count).toBeGreaterThan(0);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`/cases/${c.case_id}/assistant`);
  const controls = page.getByRole("region", {
    name: "Current housing criteria",
    exact: true,
  });
  await expect(controls).toContainText("Filtered 0 properties");
  await controls
    .getByRole("button", {
      name: `${option.label} · Matches available: ${option.count} properties`,
      exact: true,
    })
    .click();
  const result = page.locator(".commute-results").last();
  await expect(result.locator(".commute-home").first()).toBeVisible();
  await expect(controls).toContainText(`Filtered ${option.count} properties`);
  let current = await (await request.get(root)).json();
  expect(current.messages.at(-1).listings).toHaveLength(option.count);
  expect(current.rental_brief).toMatchObject({
    ...brief,
    budget_amount: brief.budget_amount + 50,
  });
  await expect(result).not.toContainText("Average commute");
  await expect(
    result.getByRole("list", { name: "Recommendation reasons" }).first(),
  ).toContainText(/Public transport|Transit/);
  await expect(
    page.getByRole("status", { name: "Filter changes" }).last(),
  ).toContainText(`Listings 0 → ${option.count} properties`);
  await controls
    .getByRole("button", { name: "Edit commute criteria", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Adjust commute",
    exact: true,
  });
  await dialog
    .getByRole("spinbutton", { name: "Current commute limit", exact: true })
    .fill("40");
  await dialog
    .getByRole("button", {
      name: "Apply changes and filter again",
      exact: true,
    })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    controls.getByRole("button", {
      name: "Edit commute criteria",
      exact: true,
    }),
  ).toContainText("≤40 minutes");
  current = await (await request.get(root)).json();
  expect(current.rental_brief).toMatchObject({
    ...brief,
    budget_amount: brief.budget_amount + 50,
    commute_max_minutes: 40,
  });
  await page.screenshot({
    path: "/tmp/recommendation-workbench-desktop.png",
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await controls
    .getByRole("button", { name: "Edit budget criteria", exact: true })
    .click();
  const budgetDialog = page.getByRole("dialog", {
    name: "Adjust budget",
    exact: true,
  });
  const editedAmount = String(brief.budget_amount + 55);
  await budgetDialog
    .getByRole("spinbutton", { name: "Current budget limit", exact: true })
    .fill(editedAmount);
  await page.route("**/recommendation-adjustments", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "temporary_unavailable", message: "测试服务暂不可用" },
      }),
    }),
  );
  await budgetDialog
    .getByRole("button", {
      name: "Apply changes and filter again",
      exact: true,
    })
    .click();
  await expect(budgetDialog).toContainText("测试服务暂不可用");
  await expect(
    budgetDialog.getByRole("spinbutton", {
      name: "Current budget limit",
      exact: true,
    }),
  ).toHaveAttribute("aria-valuenow", editedAmount);
  await budgetDialog
    .getByRole("button", { name: "Cancel", exact: true })
    .click();
  await expect(budgetDialog).toHaveCount(0);
  await page.unroute("**/recommendation-adjustments");
  await page.reload();
  await expect(controls).toContainText("≤40 minutes");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/recommendation-workbench-mobile.png",
    animations: "disabled",
  });
  const unchanged = await (
    await request.get(`/api/v1/cases/${c.case_id}`)
  ).json();
  expect(unchanged.draft.fingerprint).toBe(c.draft.fingerprint);
  expect(unchanged.confirmations).toEqual(c.confirmations);
  expect(errors).toEqual([]);
});

test("catalogue zero results offer computed single-filter alternatives and keep the selected transport", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const reference = await (
    await request.get(
      `/api/v1/listings?case_id=${c.case_id}&min_bedrooms=2&min_bathrooms=1&usyd_mode=public_transport&usyd_max_minutes=30&sort=rent_asc`,
    )
  ).json();
  const cap = reference.items[0].weekly_rent - 25;
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await page
    .getByRole("spinbutton", { name: "Minimum bedrooms", exact: true })
    .fill("2");
  await page
    .getByRole("spinbutton", { name: "Minimum bathrooms", exact: true })
    .fill("1");
  await page
    .getByRole("spinbutton", { name: "Maximum weekly rent (AUD)", exact: true })
    .fill(String(cap));
  await page
    .getByRole("combobox", { name: "Commute mode to campus", exact: true })
    .click();
  await page
    .locator(".ant-select-dropdown:visible .ant-select-item-option-content")
    .getByText("Public transport (any combination)", { exact: true })
    .click();
  await page
    .getByRole("spinbutton", {
      name: "Maximum commute to USYD (minutes)",
      exact: true,
    })
    .fill("30");
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Filtered results · 0 records",
      exact: true,
    }),
  ).toBeVisible();
  const budget = page.getByRole("button", {
    name: /Increase weekly rent limit by AUD 50.*Matches available:/,
  });
  await expect(budget).toBeVisible();
  await budget.click();
  await expect(
    page.getByTestId("real-catalog").locator("tbody tr.ant-table-row").first(),
  ).toBeVisible();
  await expect(
    page.getByRole("spinbutton", {
      name: "Maximum commute to USYD (minutes)",
      exact: true,
    }),
  ).toHaveValue("30");
  await expect(
    page.getByRole("spinbutton", { name: "Minimum bedrooms", exact: true }),
  ).toHaveValue("2");
  await expect(page.getByTestId("real-catalog")).toContainText(
    "Commute to USYD",
  );
  await expect(
    page
      .getByTestId("real-catalog")
      .getByRole("cell", { name: /Commute to USYD/ })
      .first(),
  ).toBeVisible();
});
