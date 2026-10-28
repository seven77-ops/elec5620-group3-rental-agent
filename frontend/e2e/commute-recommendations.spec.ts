import { test, expect } from "@playwright/test";
import { selectedCommute } from "../src/features/real-data/commuteSummary";

const destination = {
  id: "usyd:camperdown-darlington:fisher-library",
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

test("old destination choices are replaced by the fixed main campus and require explicit send", async ({
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
  await expect(
    page.getByRole("button", {
      name: "选择 " + destination.label,
      exact: true,
    }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "按主校区继续", exact: true }).click();
  await expect(
    page.getByPlaceholder("描述你的租房需求，或问一个问题…"),
  ).toHaveValue("保留我的预算和房型，按悉大主校区继续推荐通勤房源。");
  expect(writes).toBe(0);
  await expect(page.getByRole("checkbox", { name: /位置与交通/ })).toHaveCount(
    0,
  );
});

test("commute results remain in chat and recommendations only show catalogue filters", async ({
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
  const message = {
    ...entry,
    listings: [rows[0]],
    commute_recommendation: { ...report, pending_listings: [rows[1]] },
  };
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
    page.getByRole("heading", { name: "到悉大主校区找房", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      selectedCommute(rows[0].usyd_commute, "public_transport")!.text,
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByText("本次推荐的依据与范围", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("仅查询部分候选，不代表整个悉尼。", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "原始房源 ↗", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "房源详情", exact: true })
    .first()
    .click();
  const detail = page.getByRole("dialog");
  await expect(
    detail.getByRole("link", { name: "查看 Domain 房源", exact: true }),
  ).toHaveAttribute("href", rows[0].source_url);
  const directions = detail.getByRole("link", {
    name: "在 Google 地图查看公共交通",
    exact: true,
  });
  await expect(directions).toHaveAttribute("href", /travelmode=transit/);
  const href = new URL((await directions.getAttribute("href"))!);
  const point = rows[0].usyd_commute?.origin;
  expect(href.searchParams.get("origin")).toBe(
    point
      ? `${point.latitude},${point.longitude}`
      : `${rows[0].address} NSW ${rows[0].postcode}`,
  );
  expect(href.searchParams.get("destination")).toBe(
    "-33.88630396441765,151.190498785334",
  );
  await page.keyboard.press("Escape");
  await expect(page.locator(".commute-pending")).toHaveCount(0);
  await expect(page.getByText("通勤时间参考", { exact: true })).toHaveCount(0);
  await expect(
    page.getByText("本次找到 1 套符合通勤条件的房源", { exact: false }),
  ).toBeVisible();
  await page.setViewportSize({ width: 360, height: 900 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(
    page.getByRole("region", { name: "聊天中的通勤推荐", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "回到对话更新推荐", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".real-catalog-filters")).toBeVisible();
  await expect(page.getByTestId("real-catalog")).toBeVisible();
});

test("all eligible homes have region filtering, pagination and a clear commute constraint", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const rows = (
    await (await request.get("/api/v1/listings?page_size=30")).json()
  ).items;
  const listings = rows.slice(0, 26);
  const suburbs = [
    ...new Set(listings.map((r: { suburb: string }) => r.suburb)),
  ] as string[];
  const report = {
    status: "ready",
    destination,
    criteria: { commute_mode: "public_transport", commute_max_minutes: 30 },
    queried_at: "2026-10-28T00:00:00Z",
    date: "2026-10-28",
    arrival_time: "10:00",
    total_matching: 26,
    evaluated_count: 26,
    query_limit: 26,
    matching_count: 26,
    basis: "scheduled_reference",
    areas: suburbs.map((suburb) => ({
      suburb,
      count: listings.filter((r: { suburb: string }) => r.suburb === suburb)
        .length,
    })),
    routes: [],
    limitations: [],
    estimated_listings: [rows[26]],
    pending_listings: [rows[27]],
  };
  const conversation = {
    conversation_id: "all-commute-homes",
    case_id: c.case_id,
    title: "完整推荐",
    revision: 1,
    messages: [{ ...entry, listings, commute_recommendation: report }],
  };
  await page.route(`**/api/v1/cases/${c.case_id}/assistant/**`, async (route) =>
    route.fulfill({
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
    }),
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  const group = page.getByRole("group", { name: "按区域查看房源" });
  await expect(
    group.getByRole("button", { name: "全部", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(group.getByRole("button")).toHaveCount(suburbs.length + 1);
  await expect(page.getByText("已筛选", { exact: true })).toBeVisible();
  await expect(
    page.getByText("公共交通 ≤30分钟", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/2026-10-28 · 10:00/)).toHaveCount(0);
  await expect(page.getByText("通勤时间参考", { exact: true })).toHaveCount(0);
  await expect(page.locator(".commute-home")).toHaveCount(12);
  await page.getByTitle("2", { exact: true }).click();
  await expect(page.locator(".commute-home h4").first()).toHaveText(
    listings[12].address,
  );
  await group.getByRole("button", { name: suburbs[0], exact: true }).click();
  const matching = listings.filter(
    (r: { suburb: string }) => r.suburb === suburbs[0],
  );
  await expect(page.locator(".commute-home h4")).toHaveText(
    matching.slice(0, 12).map((r: { address: string }) => r.address),
  );
  await group.getByRole("button", { name: "全部", exact: true }).click();
  await expect(page.locator(".commute-home h4").first()).toHaveText(
    listings[0].address,
  );
  await page.getByRole("button", { name: "换一批", exact: true }).click();
  await expect(
    page.getByPlaceholder("描述你的租房需求，或问一个问题…"),
  ).toHaveValue(
    "保持全部已确认的预算、房型和通勤条件，换一批推荐，优先展示之前没看过的房源。",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
