import { test, expect } from "@playwright/test";

test("commute cards average five available modes and suburb buttons filter houses without technical copy", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const home = await (await request.get("/api/v1/listings/domain:16095702")).json();
  const other = (await (await request.get("/api/v1/listings?suburb=Newtown&page_size=1")).json()).items[0];
  home.usyd_commute.modes = Object.fromEntries(Object.entries({ public_transport: 13, train: null, metro: null, bus: 12, drive: 4, bike: 7, walk: 15 }).map(([mode, duration_minutes]) => [mode, { status: duration_minutes === null ? "no_observed_option" : "planned", duration_minutes }]));
  delete home.usyd_commute.estimates;
  other.usyd_commute = structuredClone(home.usyd_commute);
  other.usyd_commute.modes.walk.duration_minutes = 180;
  const conversation = { conversation_id: "commute-summary", case_id: c.case_id, title: "通勤找房", revision: 1, messages: [{
    message_id: "summary", role: "assistant", agent: "agent2", created_at: "2026-10-27T10:00:00Z", content: "找到以下房源。", actions: [], listings: [home, other],
    commute_recommendation: { status: "ready", destination: home.usyd_commute.destination, criteria: { commute_mode: "public_transport", commute_max_minutes: 20 }, date: "2026-10-28", arrival_time: "10:00",
      areas: ["Camperdown", "Newtown"].map(suburb => ({ suburb, count: 1, verified_route_count: 1, reasons: ["开发者说明"], tradeoffs: ["区域资料尚未整理"], area_context: null })),
      routes: [{ listing_id: home.listing_id, status: "ok", duration_minutes: 13, walking_minutes: 10, transfers: 0, departure_at: "2026-10-28T09:46:00+11:00", arrival_at: "2026-10-28T09:59:00+11:00", legs: [{ mode: "walk", duration_minutes: 10 }] }],
    },
  }] };
  await page.route(`**/api/v1/cases/${c.case_id}/assistant/**`, route => route.fulfill({ json: new URL(route.request().url()).pathname.endsWith("/conversations")
    ? { items: [{ conversation_id: conversation.conversation_id, title: conversation.title, updated_at: "2026-10-27T10:00:00Z", message_count: 1 }] } : conversation }));
  await page.goto(`/cases/${c.case_id}/assistant`);
  const results = page.getByRole("region", { name: "通勤与区域建议", exact: true });
  await expect(results.locator(".commute-attribution")).toHaveCount(0);
  await expect(results).not.toContainText("TfNSW");
  const card = results.locator(".commute-home").filter({ has: page.getByRole("heading", { name: home.address, exact: true }) });
  await expect(card).toContainText("平均通勤约 10 分钟");
  await expect(card.getByRole("link", { name: "Google 地图 ↗", exact: true })).toHaveAttribute("href", /google.com\/maps\/dir/);
  for (const text of ["依据与取舍", "房屋候选", "已核对路线", "区域资料尚未整理", "查看来源与适用范围", "步行接驳", "换乘 0 次", "09:46", "09:59", "查看行程分段"]) await expect(results).not.toContainText(text);
  const suburbs = results.getByRole("group", { name: "按区域查看房源" });
  await suburbs.getByRole("button", { name: "Newtown", exact: true }).click();
  await expect(results.locator(".commute-homes .commute-home")).toHaveCount(1);
  await expect(results.locator(".commute-homes")).toContainText(other.address);
  await expect(results.locator(".commute-homes")).toContainText("平均通勤约 9 分钟");
  await results.getByRole("button", { name: "房源详情", exact: true }).click();
  const farDetails = page.getByTestId("usyd-commute");
  await expect(farDetails).toContainText("平均通勤约 9 分钟");
  await expect(farDetails.getByText("步行", { exact: true })).toHaveCount(0);
  await expect(farDetails.getByRole("link", { name: "在 Google 地图查看步行", exact: true })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await suburbs.getByRole("button", { name: "Camperdown", exact: true }).click();
  await expect(card).toBeVisible();
  await expect(results.locator(".commute-homes .commute-home")).toHaveCount(1);
  await suburbs.getByRole("button", { name: "Camperdown", exact: true }).click();
  await expect(results.locator(".commute-homes .commute-home")).toHaveCount(2);
  await page.screenshot({ path: "/tmp/commute-summary-desktop.png" });
  await card.getByRole("button", { name: "房源详情", exact: true }).click();
  const details = page.getByTestId("usyd-commute");
  await expect(details).toContainText("平均通勤约 10 分钟");
  for (const text of ["房屋资料", "房屋类型", "待确认事项"]) await expect(page.getByRole("dialog")).not.toContainText(text);
  await expect(details.locator(".usyd-mode-grid > div")).toHaveCount(5);
  for (const mode of ["火车", "地铁"]) await expect(details.getByText(mode, { exact: true })).toHaveCount(0);
  for (const text of ["待核实", "本次未取得", "行程分段", "公共交通基准", "计划时刻", "接驳", "换乘"]) await expect(details).not.toContainText(text);
  await expect(details.getByRole("link", { name: /在 Google 地图查看/ })).toHaveCount(5);
  await details.scrollIntoViewIfNeeded();
  await page.screenshot({ path: "/tmp/commute-summary-detail.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await details.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "/tmp/commute-summary-mobile.png" });
  expect(errors).toEqual([]);
});
