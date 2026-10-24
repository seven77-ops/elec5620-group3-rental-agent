import { test, expect } from "@playwright/test";

async function openReal(
  page: import("@playwright/test").Page,
  request: import("@playwright/test").APIRequestContext,
) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/real-data`);
  await expect(
    page.getByRole("heading", { name: "真实房源推荐", exact: true }),
  ).toBeVisible();
  await page.getByText("房源补充工具", { exact: true }).click();
  await page.getByRole("tab", { name: "租金参考", exact: true }).click();
  return c;
}

test("real rent benchmark respects periods, scope and editable inputs", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await openReal(page, request);
  await page
    .getByRole("spinbutton", { name: "房源基础周租（AUD，可留空）" })
    .fill("760");
  await page.getByRole("button", { name: "查询租金参考", exact: true }).click();
  await expect(page.getByTestId("market-2026-09")).toContainText("805");
  await expect(page.getByTestId("market-2026-09")).toContainText("45");
  await expect(page.getByTestId("market-2026-Q2")).toContainText("775");
  await page.getByRole("combobox", { name: /租金计价对象/ }).click();
  await page.getByRole("combobox", { name: /租金计价对象/ }).press("ArrowDown");
  await page.getByRole("combobox", { name: /租金计价对象/ }).press("Enter");
  await expect(page.getByTestId("market-2026-09")).toHaveCount(0);
  await page.getByRole("button", { name: "查询租金参考", exact: true }).click();
  await expect(
    page.getByText("单间和按人报价暂不提供市场比较", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  await expect(page.locator("vite-error-overlay")).toHaveCount(0);
});

test("manual real listing persists after refresh, exports and never becomes a recommendation", async ({
  page,
  request,
}) => {
  const c = await openReal(page, request);
  await page.getByRole("tab", { name: "真实房源", exact: true }).click();
  await page
    .getByRole("textbox", { name: /房源地址或位置说明/ })
    .fill("1/20 Pyrmont Bridge Road, Camperdown");
  await page
    .getByRole("textbox", { name: /原始房源链接/ })
    .fill("https://www.domain.com.au/example-18374975");
  await page
    .getByRole("spinbutton", { name: /^\*?\s*周租（AUD）$/ })
    .fill("760");
  await page
    .getByRole("button", { name: "保存真实房源记录", exact: true })
    .click();
  await expect(page.getByTestId("saved-real-listings")).toContainText(
    "1/20 Pyrmont Bridge Road",
  );
  await expect(page.getByTestId("saved-real-listings")).toContainText(
    "尚未评估",
  );
  await page.reload();
  await page.getByText("房源补充工具", { exact: true }).click();
  await page.getByRole("tab", { name: "真实房源", exact: true }).click();
  await expect(page.getByTestId("saved-real-listings")).toContainText(
    "1/20 Pyrmont Bridge Road",
  );
  const output = await (
    await request.get(`/api/v1/cases/${c.case_id}/real-listings/export`)
  ).json();
  expect(output.items).toHaveLength(1);
  expect(output.items[0].bills_included).toBeNull();
  const state = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(state.evaluations).toHaveLength(0);
  expect(state.selection).toBeNull();
});

test("unconfigured providers remain disabled and 360px page fits", async ({
  page,
  request,
}) => {
  await openReal(page, request);
  await page.getByRole("tab", { name: "真实房源", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "查询 Domain 房源", exact: true }),
  ).toBeDisabled();
  await page.getByRole("tab", { name: "通勤查询", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "查询实际通勤", exact: true }),
  ).toBeDisabled();
  await page.setViewportSize({ width: 360, height: 900 });
  await expect(
    page.getByRole("heading", { name: "真实房源推荐", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);
});

test("late initial listing read cannot hide a record saved afterward", async ({
  page,
  request,
}) => {
  let release!: () => void;
  let initialReady!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  const initial = new Promise<void>((resolve) => {
    initialReady = resolve;
  });
  let reads = 0;
  await page.route("**/api/v1/cases/*/real-listings", async (route) => {
    if (route.request().method() !== "GET" || ++reads > 1) {
      await route.continue();
      return;
    }
    const response = await route.fetch();
    initialReady();
    await held;
    await route.fulfill({ response });
  });
  await openReal(page, request);
  await page.getByRole("tab", { name: "真实房源", exact: true }).click();
  await initial;
  await page
    .getByRole("textbox", { name: /房源地址或位置说明/ })
    .fill("Saved while old read pending");
  await page
    .getByRole("textbox", { name: /原始房源链接/ })
    .fill("https://www.domain.com.au/research");
  await page
    .getByRole("spinbutton", { name: /^\*?\s*周租（AUD）$/ })
    .fill("760");
  await page
    .getByRole("button", { name: "保存真实房源记录", exact: true })
    .click();
  await expect(page.getByTestId("saved-real-listings")).toContainText(
    "Saved while old read pending",
  );
  const late = page.waitForResponse(
    (response) =>
      response.url().endsWith("/real-listings") &&
      response.request().method() === "GET",
  );
  release();
  await (await late).json();
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await expect(page.getByTestId("saved-real-listings")).toContainText(
    "Saved while old read pending",
  );
});
