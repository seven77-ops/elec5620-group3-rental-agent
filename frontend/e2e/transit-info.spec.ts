import { test, expect } from "@playwright/test";

test("traffic answers show named stops, safe alert links and concise average commute", async ({ page, request }) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const home = await (await request.get("/api/v1/listings/domain:16095702")).json();
  const route = { listing_id: home.listing_id, status: "ok", duration_minutes: 14, walking_minutes: 6, transfers: 0,
    departure_at: "2026-10-28T08:43:00+11:00", arrival_at: "2026-10-28T08:57:00+11:00",
    transit_modes: ["bus"], legs: [
      { mode: "walk", duration_minutes: 3, from: home.address, to: "Parramatta Rd stop" },
      { mode: "bus", service: "412", duration_minutes: 8, from: "Parramatta Rd stop", to: "University of Sydney" },
    ] };
  const common = { role: "assistant", agent: "agent2", created_at: "2026-10-27T10:00:00Z", actions: [] };
  const info = { topic: "nearby", listing_id: home.listing_id, address: home.address, queried_at: common.created_at,
    source_url: "https://transportnsw.info", stop_name: null, alerts: [],
    stops: [{ id: "10113043", name: "Parramatta Rd before Lyons Rd, Camperdown", distance_m: 49 }] };
  const conversation = { conversation_id: "transit-test", case_id: c.case_id, revision: 3, title: "到校交通", messages: [
    { ...common, message_id: "route", content: "找到符合20分钟要求的房源。", listings: [home], commute_recommendation: {
      status: "ready", destination: home.usyd_commute.destination, criteria: { commute_max_minutes: 20, commute_mode: "public_transport" },
      date: "2026-10-28", arrival_time: "09:00", areas: [], routes: [route], matching_count: 1,
    } },
    { ...common, message_id: "nearby", content: "附近车站参考如下。", listings: [], transit_information: info },
    { ...common, message_id: "alert", content: "当前站点提醒。", listings: [], transit_information: { ...info, topic: "alerts", stop_name: info.stops[0].name,
      alerts: [{ title: "公交服务调整", url: "https://transportnsw.info/alerts" }] } },
  ] };
  await page.route(`**/api/v1/cases/${c.case_id}/assistant/**`, route => route.fulfill({ json:
    new URL(route.request().url()).pathname.endsWith("/conversations")
      ? { items: [{ conversation_id: conversation.conversation_id, title: conversation.title, updated_at: common.created_at, message_count: 3 }] }
      : conversation }));
  await page.goto(`/cases/${c.case_id}/assistant`);
  // Sections use an accessible aria label and remain compact inside the chat.
  await expect(page.locator(".transit-information")).toHaveCount(2);
  await expect(page.getByText("直线约 49 米", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "查看详情 ↗", exact: true })).toHaveAttribute("href", "https://transportnsw.info/alerts");
  await expect(page.getByText("查看行程分段", { exact: true })).toHaveCount(0);
  await expect(page.locator(".commute-homes")).toContainText("平均通勤约");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: "/tmp/mcp-integration-chat-mobile.png" });
});
