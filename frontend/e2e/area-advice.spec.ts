import { test, expect } from "@playwright/test";

test("choosing Rhodes and answering commute minutes advances without repeating area cards", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  const composer = page.getByPlaceholder("描述你的租房需求，或问一个问题…");
  const submit = page.getByRole("button", { name: "发送消息", exact: true });
  await composer.fill("比较 Burwood 和 Rhodes，我看重公园和餐饮");
  await submit.click();
  await expect(
    page.getByRole("region", { name: "区域生活建议", exact: true }),
  ).toHaveCount(1);
  await page
    .getByRole("button", { name: "在 Rhodes 找房", exact: true })
    .click();
  await expect(composer).toHaveValue(
    "保持我的预算和房型要求，按 Rhodes 区域继续推荐房源，并核对到悉大主校区的通勤。",
  );
  await submit.click();
  await expect(
    page.locator(".assistant-message-assistant").last(),
  ).toContainText("单程最多接受多少分钟");
  await expect(
    page.getByRole("region", { name: "区域生活建议", exact: true }),
  ).toHaveCount(1);
  await composer.fill("20分钟");
  await submit.click();
  const last = page.locator(".assistant-message-assistant").last();
  await expect(last).toContainText("通勤选");
  await expect(last).not.toContainText("单程最多接受多少分钟");
  await expect(
    page.getByRole("region", { name: "区域生活建议", exact: true }),
  ).toHaveCount(1);
});

test("area evidence stays in chat while recommendations show filters and results", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByPlaceholder("描述你的租房需求，或问一个问题…")
    .fill("比较 Burwood 和 Rhodes，我看重公园和餐饮");
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
  const advice = page.getByRole("region", {
    name: "区域生活建议",
    exact: true,
  });
  await expect(advice).toBeVisible();
  await expect(advice).toContainText("12 / 72 个区域");
  await expect(advice).toContainText("Burwood");
  await expect(advice).toContainText("Rhodes");
  await advice.getByText("查看来源与适用范围", { exact: true }).first().click();
  await expect(
    advice.getByRole("link", { name: /Burwood Chinatown/ }),
  ).toBeVisible();
  await expect(advice).toContainText("核对：2026-10-24");
  await page.getByRole("menuitem", { name: "房源推荐" }).click();
  await expect(
    page.getByRole("region", { name: "聊天中的区域参考", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".real-catalog-filters")).toBeVisible();
  await expect(page.getByTestId("real-catalog")).toBeVisible();
  await page.getByRole("menuitem", { name: "AI租房助手", exact: true }).click();
  await expect(page).toHaveURL(/assistant/);
  await page
    .getByPlaceholder("描述你的租房需求，或问一个问题…")
    .fill("生活配套没有特别要求，比较 Carlton 的安静和安全");
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
  const gap = page
    .getByRole("region", { name: "区域生活建议", exact: true })
    .last();
  await expect(gap).toContainText("Carlton");
  await expect(gap).toContainText("资料尚未整理");
  await expect(gap).toContainText("安静、安全");
  await page.setViewportSize({ width: 360, height: 800 });
  await expect(gap).toBeVisible();
  await gap.scrollIntoViewIfNeeded();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "/tmp/area-advice-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("recommendations omit duplicate chat panels and do not fetch commute reports", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/assistant`;
  const conversation = await (
    await request.post(root + "/conversations", { data: {} })
  ).json();
  const answer = await (
    await request.post(
      root + `/conversations/${conversation.conversation_id}/messages`,
      {
        data: {
          request_id: "area-context",
          expected_revision: 0,
          message: "比较 Burwood 和 Rhodes，我看重公园和餐饮",
          allow_external_ai: true,
        },
      },
    )
  ).json();
  const context = answer.messages
    .at(-1)
    .area_advice.areas.find((a: { suburb: string }) => a.suburb === "Rhodes");
  const report = {
    status: "unavailable",
    destination: {
      id: "usyd:camperdown-darlington:fisher-library",
      label: "悉尼大学 Camperdown / Darlington 主校区 · Fisher Library",
      latitude: -33.88,
      longitude: 151.18,
      precision: "address_point",
      source_url: "https://www.nsw.gov.au/",
    },
    criteria: { lifestyle_priorities: ["parks"], commute_max_minutes: 40 },
    queried_at: "2026-10-24T00:00:00Z",
    date: "2026-10-26",
    arrival_time: "09:00",
    total_matching: 10,
    evaluated_count: 0,
    query_limit: 12,
    areas: [
      {
        suburb: "Rhodes",
        count: 10,
        min_weekly_rent: 800,
        max_weekly_rent: 1500,
        fastest_minutes: null,
        verified_route_count: 0,
        reasons: [],
        tradeoffs: [],
        area_context: context,
      },
    ],
    routes: [],
    limitations: ["测试用未查询通勤状态"],
    area_knowledge_coverage: { covered_suburbs: 12, catalog_suburbs: 71 },
  };
  let sharedReads = 0;
  await page.route(`**${root}/commute-recommendation`, (route) => {
    sharedReads++;
    return route.fulfill({
      json: {
        conversation_id: conversation.conversation_id,
        stale: false,
        stale_reasons: [],
        message: {
          ...answer.messages.at(-1),
          area_advice: undefined,
          commute_recommendation: report,
        },
      },
    });
  });
  await page.goto(`/cases/${c.case_id}/recommendations`);
  const commute = page.getByRole("region", {
    name: "聊天中的通勤推荐",
    exact: true,
  });
  await expect(commute).toHaveCount(0);
  await expect(page.locator(".real-catalog-filters")).toBeVisible();
  await expect(page.getByTestId("real-catalog")).toBeVisible();
  expect(sharedReads).toBe(0);
  await page.screenshot({
    path: "/tmp/recommendations-filters-only.png",
    fullPage: true,
  });
});

test("a natural Ashfield choice and changed budget advance with distinct answers", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  const composer = page.getByPlaceholder("描述你的租房需求，或问一个问题…");
  const send = async (text: string) => {
    await composer.fill(text);
    await page.getByRole("button", { name: "发送消息", exact: true }).click();
    await expect(composer).toHaveValue("");
  };
  await send("比较 Burwood 和 Ashfield，整套850一卧，想吃饭方便");
  const replies = page.locator(".assistant-message-assistant");
  await expect(replies.last()).toContainText("850");
  await expect(replies.last()).toContainText("餐饮");
  const first = await replies.last().innerText();
  await send("预算降到700，按价格比较这两个区");
  await expect(replies.last()).toContainText("700");
  await expect(replies.last()).toContainText("低标价");
  expect(await replies.last().innerText()).not.toBe(first);
  await send("那先看Ashfield吧，帮我找房，也看看上学方不方便。");
  await expect(replies.last()).toContainText("单程最多接受多少分钟");
  await expect(
    replies.last().getByRole("region", { name: "区域生活建议", exact: true }),
  ).toHaveCount(0);
  await send("20分钟");
  await expect(replies.last()).toContainText("通勤选");
  const list = await (
    await request.get(`/api/v1/cases/${c.case_id}/assistant/conversations`)
  ).json();
  const chat = await (
    await request.get(
      `/api/v1/cases/${c.case_id}/assistant/conversations/${list.items[0].conversation_id}`,
    )
  ).json();
  expect(chat.rental_brief.suburb).toBe("Ashfield");
  expect(chat.rental_brief.budget_amount).toBe(700);
});
