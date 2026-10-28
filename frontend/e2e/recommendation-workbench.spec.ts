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
    name: "本次找房条件",
    exact: true,
  });
  await expect(controls).toContainText("已筛选 0 套");
  await controls
    .getByRole("button", {
      name: `${option.label} · 可找到 ${option.count} 套`,
      exact: true,
    })
    .click();
  const result = page.locator(".commute-results").last();
  await expect(result.locator(".commute-home").first()).toBeVisible();
  await expect(controls).toContainText(`已筛选 ${option.count} 套`);
  let current = await (await request.get(root)).json();
  expect(current.messages.at(-1).listings).toHaveLength(option.count);
  expect(current.rental_brief).toMatchObject({
    ...brief,
    budget_amount: brief.budget_amount + 50,
  });
  await expect(result).not.toContainText("平均通勤");
  await expect(
    result.getByRole("list", { name: "推荐理由" }).first(),
  ).toContainText("公共交通");
  await expect(
    page.getByRole("status", { name: "本次筛选变化" }).last(),
  ).toContainText(`房源 0 → ${option.count} 套`);
  await controls
    .getByRole("button", { name: "修改通勤条件", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "调整通勤", exact: true });
  await dialog
    .getByRole("spinbutton", { name: "本次通勤上限", exact: true })
    .fill("40");
  await dialog
    .getByRole("button", { name: "应用修改并重新筛选", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    controls.getByRole("button", { name: "修改通勤条件", exact: true }),
  ).toContainText("≤40分钟");
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
    .getByRole("button", { name: "修改预算条件", exact: true })
    .click();
  const budgetDialog = page.getByRole("dialog", {
    name: "调整预算",
    exact: true,
  });
  const editedAmount = String(brief.budget_amount + 55);
  await budgetDialog
    .getByRole("spinbutton", { name: "本次预算上限", exact: true })
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
    .getByRole("button", { name: "应用修改并重新筛选", exact: true })
    .click();
  await expect(budgetDialog).toContainText("测试服务暂不可用");
  await expect(
    budgetDialog.getByRole("spinbutton", { name: "本次预算上限", exact: true }),
  ).toHaveAttribute("aria-valuenow", editedAmount);
  await budgetDialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(budgetDialog).toHaveCount(0);
  await page.unroute("**/recommendation-adjustments");
  await page.reload();
  await expect(controls).toContainText("≤40分钟");
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
    .getByRole("spinbutton", { name: "至少卧室数", exact: true })
    .fill("2");
  await page
    .getByRole("spinbutton", { name: "至少浴室数", exact: true })
    .fill("1");
  await page
    .getByRole("spinbutton", { name: "最高周租（AUD）", exact: true })
    .fill(String(cap));
  await page
    .getByRole("combobox", { name: "到校通勤方式", exact: true })
    .click();
  await page
    .locator(".ant-select-dropdown:visible .ant-select-item-option-content")
    .getByText("公共交通", { exact: true })
    .click();
  await page
    .getByRole("spinbutton", { name: "到悉大最多（分钟）", exact: true })
    .fill("30");
  await page.getByRole("button", { name: "应用筛选", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "筛选结果 · 0 条", exact: true }),
  ).toBeVisible();
  const budget = page.getByRole("button", {
    name: /周租上限增加 AUD 50.*可找到/,
  });
  await expect(budget).toBeVisible();
  await budget.click();
  await expect(
    page.getByTestId("real-catalog").locator("tbody tr.ant-table-row").first(),
  ).toBeVisible();
  await expect(
    page.getByRole("spinbutton", { name: "到悉大最多（分钟）", exact: true }),
  ).toHaveValue("30");
  await expect(
    page.getByRole("spinbutton", { name: "至少卧室数", exact: true }),
  ).toHaveValue("2");
  await expect(page.getByTestId("real-catalog")).toContainText("公共交通");
  await expect(
    page
      .getByTestId("real-catalog")
      .getByRole("list", { name: "推荐理由" })
      .first(),
  ).toBeVisible();
});
