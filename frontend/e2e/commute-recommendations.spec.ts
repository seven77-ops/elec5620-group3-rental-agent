import { test, expect } from "@playwright/test";

const destination = {
  id: "nsw-campus-1",
  label: "University of Sydney, Camperdown NSW",
  latitude: -33.888,
  longitude: 151.187,
  precision: "address_point",
  source_url: "https://www.nsw.gov.au/",
};
const entry = {
  message_id: "commute-message",
  role: "assistant",
  agent: "agent2",
  intent: "recommend_areas",
  created_at: "2026-10-24T00:00:00Z",
  content: "已按本次预算与通勤条件整理候选。",
  actions: [],
  listings: [],
};

test("destination choices populate composer and require explicit send", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const conversation = {
    conversation_id: "commute-choice",
    case_id: c.case_id,
    title: "按通勤选区域",
    revision: 1,
    messages: [{ ...entry, destination_options: [destination] }],
  };
  let writes = 0;
  await page.route(
    `**/api/v1/cases/${c.case_id}/assistant/**`,
    async (route) => {
      if (route.request().method() === "POST") writes++;
      await route.fulfill({
        json: route.request().url().endsWith("/conversations")
          ? {
              items: [
                {
                  ...conversation,
                  message_count: 1,
                  updated_at: entry.created_at,
                },
              ],
            }
          : conversation,
      });
    },
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByRole("button", { name: "选择 " + destination.label, exact: true })
    .click();
  await expect(
    page.getByPlaceholder("描述你的租房需求，或问一个问题…"),
  ).toHaveValue(
    "我的通勤目的地选择：" +
      destination.label +
      "（地点编号 " +
      destination.id +
      "）",
  );
  expect(writes).toBe(0);
  await expect(
    page.getByRole("checkbox", { name: /位置与交通/ }),
  ).not.toBeChecked();
});

test("shared commute result discloses unavailable routes, coverage and stale state", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const rows = (
    await (await request.get("/api/v1/listings?page_size=2")).json()
  ).items;
  const report = {
    status: "partial",
    destination,
    criteria: { budget_amount: 850, commute_max_minutes: 40 },
    queried_at: "2026-10-24T00:00:00Z",
    date: "2026-10-26",
    arrival_time: "09:00",
    total_matching: 90,
    evaluated_count: 2,
    query_limit: 12,
    areas: [
      {
        suburb: rows[0].suburb,
        count: 2,
        min_weekly_rent: 470,
        max_weekly_rent: 485,
        fastest_minutes: 34,
        verified_route_count: 1,
        reasons: ["有已查询的40分钟内路线"],
        tradeoffs: ["部分房源通勤待查询"],
      },
    ],
    routes: [
      {
        listing_id: rows[0].listing_id,
        status: "ok",
        duration_minutes: 34,
        walking_minutes: 8,
        transfers: 1,
        departure_at: null,
        arrival_at: null,
        source_url: "https://transportnsw.info/",
        origin_precision: "address_point",
        reason: "",
      },
      {
        listing_id: rows[1].listing_id,
        status: "unavailable",
        duration_minutes: null,
        walking_minutes: null,
        transfers: null,
        departure_at: null,
        arrival_at: null,
        source_url: "https://transportnsw.info/",
        origin_precision: "unknown",
        reason: "位置尚未确认",
      },
    ],
    limitations: ["仅查询部分候选，不代表整个悉尼。"],
  };
  const message = { ...entry, listings: rows, commute_recommendation: report };
  const conversation = {
    conversation_id: "commute-result",
    case_id: c.case_id,
    title: "按通勤选区域",
    revision: 1,
    messages: [message],
  };
  await page.route(
    `**/api/v1/cases/${c.case_id}/assistant/**`,
    async (route) => {
      const url = route.request().url();
      await route.fulfill({
        json: url.endsWith("/commute-recommendation")
          ? {
              conversation_id: conversation.conversation_id,
              message,
              stale: true,
              stale_reasons: ["聊天需求已更新，请重新生成推荐。"],
            }
          : url.endsWith("/conversations")
            ? {
                items: [
                  {
                    ...conversation,
                    message_count: 1,
                    updated_at: entry.created_at,
                  },
                ],
              }
            : conversation,
      });
    },
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(
    page.getByRole("heading", { name: "按通勤选区域", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("34 分钟", { exact: true })).toBeVisible();
  await expect(page.getByText("通勤待查询", { exact: true })).toBeVisible();
  await expect(
    page.getByText("90 条符合房屋筛选，已查询 2 条", { exact: false }),
  ).toBeVisible();
  await page.setViewportSize({ width: 360, height: 900 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(
    page.getByText("聊天需求已更新，请重新生成推荐。", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "回到对话更新推荐", exact: true }),
  ).toBeVisible();
});
