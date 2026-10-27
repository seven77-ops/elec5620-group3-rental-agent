import { test, expect } from "@playwright/test";
import { commuteSummary } from "../src/features/real-data/commuteSummary";

test("all houses have seven mode records and the webpage enforces walk twenty minutes", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const data = await (
    await request.get(
      "/api/v1/listings?usyd_mode=walk&usyd_max_minutes=20&max_weekly_rent=1200&page_size=100",
    )
  ).json();
  expect(data.total).toBeGreaterThan(0);
  for (const row of data.items) {
    const minutes = row.usyd_commute.modes.walk.duration_minutes;
    expect(minutes ?? row.usyd_commute.estimates.walk.upper_minutes).toBeLessThanOrEqual(20);
    expect(Object.keys(row.usyd_commute.modes)).toHaveLength(7);
  }
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await page
    .getByRole("combobox", { name: "到校通勤方式", exact: true })
    .click();
  await page.getByRole("option", { name: "步行", exact: true }).click();
  await page
    .getByRole("spinbutton", { name: "到悉大最多（分钟）", exact: true })
    .fill("20");
  await page
    .getByRole("spinbutton", { name: "最高周租（AUD）", exact: true })
    .fill("1200");
  await page.getByRole("button", { name: "应用筛选", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: `筛选结果 · ${data.total} 条`,
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "查看房源详情", exact: true })
    .first()
    .click();
  const details = page.getByTestId("usyd-commute");
  await expect(details).toContainText("Fisher Library");
  const summary = commuteSummary(data.items[0].usyd_commute);
  for (const mode of summary.items) await expect(details.getByText(mode.label, { exact: true })).toBeVisible();
  await expect(details.locator(".usyd-mode-grid > div")).toHaveCount(summary.items.length);
  await expect(details).toContainText(`平均通勤约 ${summary.average} 分钟`);
  await details.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "/tmp/usyd-listing-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await details.scrollIntoViewIfNeeded();
  const grid = await page.locator(".usyd-mode-grid").boundingBox();
  expect(grid?.x).toBeGreaterThanOrEqual(0);
  expect((grid?.x ?? 0) + (grid?.width ?? 0)).toBeLessThanOrEqual(390);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/usyd-listing-mobile.png",
    fullPage: false,
  });
});

test("chat uses the main campus without school questions and syncs the actual commute limit", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByPlaceholder("描述你的租房需求，或问一个问题…")
    .fill(
      "我是悉大学生，步行20分钟，整租每周1200，一卧一卫，车位不限，一个人住",
    );
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "到悉大主校区找房", exact: true }),
  ).toBeVisible();
  const times = await page
    .locator(".commute-homes .commute-time")
    .allTextContents();
  expect(times.length).toBeGreaterThan(0);
  for (const time of times) expect(time).toMatch(/^平均通勤约 \d+ 分钟$/);
  const estimates = page.getByRole("region", { name: "街道与区域通勤估算" });
  await expect(estimates).toBeVisible();
  await expect(estimates).toContainText("通勤时间参考");
  await expect(estimates.getByRole("button", { name: "保存为候选" })).toHaveCount(0);
  await expect(page.getByText("选择这个地点", { exact: true })).toHaveCount(0);
  await page.screenshot({
    path: "/tmp/usyd-chat-twenty-minutes.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "我的租房需求", exact: true }).click();
  const drawer = page.getByRole("dialog", {
    name: "我的租房需求",
    exact: true,
  });
  await expect(
    drawer.getByRole("spinbutton", { name: "单程最多（分钟）", exact: true }),
  ).toHaveValue("20");
  await drawer
    .getByRole("button", { name: "确认并同步需求", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "确认同步租房需求？",
    exact: true,
  });
  await expect(modal).toContainText("步行");
  await expect(modal).toContainText("20");
  await modal
    .getByRole("button", { name: "确认同步并生成推荐", exact: true })
    .click();
  await expect(drawer).not.toBeVisible();
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.confirmations.at(-1).profile.student_commute).toEqual({
    mode: "walk",
    maximum_minutes: 20,
  });
  await page.getByRole("menuitem", { name: "房源推荐", exact: true }).click();
  await expect(
    page.getByRole("spinbutton", { name: "到悉大最多（分钟）", exact: true }),
  ).toHaveValue("20");
  await expect(page.locator(".usyd-commute-mini").first()).toContainText(
    "平均通勤约",
  );
});

test("unlocated houses show a labelled range and cannot use its midpoint to pass twenty minutes", async ({ page, request }) => {
  const redfern = await (await request.get("/api/v1/listings?suburb=Redfern&page_size=100&sort=rent_asc")).json();
  const listing = redfern.items.find((r: { usyd_commute: { origin: unknown; estimates?: { walk?: { upper_minutes: number } } } }) => !r.usyd_commute.origin && (r.usyd_commute.estimates?.walk?.upper_minutes ?? 0) > 20);
  expect(listing).toBeTruthy();
  expect(listing.usyd_commute.origin).toBeNull();
  const estimate = listing.usyd_commute.estimates.walk;
  expect(estimate.level).toBe("street");
  expect(estimate.upper_minutes).toBeGreaterThan(20);
  const filtered = await (await request.get("/api/v1/listings?suburb=Redfern&usyd_mode=walk&usyd_max_minutes=20&page_size=100")).json();
  expect(filtered.items.some((r: { listing_id: string }) => r.listing_id === listing.listing_id)).toBe(false);
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await page.getByRole("combobox", { name: "房源区域", exact: true }).fill("Redfern");
  await page.getByRole("combobox", { name: "房源区域", exact: true }).press("Enter");
  await page.getByRole("button", { name: "应用筛选", exact: true }).click();
  // New lower-rent houses can move the historical unlocated fixture beyond page one.
  const index = redfern.items.findIndex((r: { listing_id: string }) => r.listing_id === listing.listing_id);
  const resultPage = Math.floor(index / 20) + 1;
  if (resultPage > 1) await page.getByTitle(String(resultPage), { exact: true }).click();
  const row = page.getByTestId("real-catalog").locator("tbody tr.ant-table-row").filter({ hasText: listing.address });
  await expect(row).toContainText("平均通勤约");
  await row.getByRole("button", { name: "查看房源详情", exact: true }).click();
  const detail = page.getByTestId("usyd-commute");
  await expect(detail).toContainText(`约 ${Math.round((estimate.lower_minutes + estimate.upper_minutes) / 2)}`);
  await expect(detail).toContainText("平均通勤约");
  await expect(detail).not.toContainText("直线");
  await detail.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "/tmp/usyd-expanded-estimated-home.png", fullPage: false });
});

test("historical unlocated cards open the newly refined house routes inside details", async ({ page, request }) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const catalog = await (await request.get("/api/v1/listings?page_size=1")).json();
  const current = await (await request.get("/api/v1/listings/domain:16095702")).json();
  expect(current.usyd_commute.origin.provider).toBe("tfnsw_stop_finder");
  const old = structuredClone(current);
  old.usyd_commute.origin = null;
  old.usyd_commute.straight_line_distance_m = null;
  for (const mode of Object.keys(old.usyd_commute.modes)) old.usyd_commute.modes[mode] = { status: "unavailable", duration_minutes: null };
  old.usyd_commute.estimates = { public_transport: { status: "coarse_estimate", label: "街道估算", lower_minutes: 4, upper_minutes: 20 } };
  await page.route("**/api/v1/listings?*", (route) => route.fulfill({ json: { ...catalog, total: 1, items: [old] } }));
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(page.getByTestId("real-catalog")).toContainText("平均通勤约 12 分钟");
  await expect(page.getByRole("link", { name: "原始房源 ↗" })).toHaveCount(0);
  await page.getByRole("button", { name: "查看房源详情", exact: true }).click();
  const details = page.getByTestId("usyd-commute");
  await expect(details).toContainText("平均通勤约");
  await expect(details).not.toContainText("4–20");
  const walk = details.locator(".usyd-mode-grid > div").filter({ has: page.getByText("步行", { exact: true }) });
  await expect(walk.locator("strong")).toContainText(String(Math.ceil(current.usyd_commute.modes.walk.duration_minutes)));
  await expect(details.getByRole("link", { name: /在 Google 地图查看/ })).toHaveCount(commuteSummary(current.usyd_commute).items.length);
  await details.scrollIntoViewIfNeeded();
  await expect.poll(async () => {
    const box = await page.getByRole("dialog").boundingBox();
    return !!box && box.x >= 0 && box.x + box.width <= 1441;
  }).toBe(true);
  await page.screenshot({ path: "/tmp/commute-refined-home-desktop.png", fullPage: false });
  await page.setViewportSize({ width: 390, height: 844 });
  await details.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "/tmp/commute-refined-home-mobile.png", fullPage: false });
});
