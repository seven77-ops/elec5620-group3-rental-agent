import { test, expect } from "@playwright/test";

test("area chat retrieves real evidence and shares it with recommendations", async ({
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
  await page.getByRole("checkbox", { name: /同意本次使用外部/ }).check();
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
  const advice = page.getByRole("region", {
    name: "区域生活建议",
    exact: true,
  });
  await expect(advice).toBeVisible();
  await expect(advice).toContainText("12 / 71 个区域");
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
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "区域生活建议", exact: true }),
  ).toContainText("Burwood");
  await page
    .getByRole("button", { name: "回到对话调整生活偏好", exact: true })
    .click();
  await expect(page).toHaveURL(/assistant\?conversation=/);
  await page
    .getByPlaceholder("描述你的租房需求，或问一个问题…")
    .fill("生活配套没有特别要求，比较 Carlton 的安静和安全");
  await page.getByRole("checkbox", { name: /同意本次使用外部/ }).check();
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

test("commute result renders the same source-backed area context", async ({
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
      id: "test-destination",
      label: "测试目的地",
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
  await page.route(`**${root}/commute-recommendation`, (route) =>
    route.fulfill({
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
    }),
  );
  await page.goto(`/cases/${c.case_id}/recommendations`);
  const commute = page.getByRole("region", {
    name: "聊天中的通勤推荐",
    exact: true,
  });
  await expect(commute).toContainText("The Connection");
  await expect(commute).toContainText("通勤待查询");
  await commute.getByText("查看来源与适用范围", { exact: true }).click();
  await expect(
    commute.getByRole("link", { name: /City of Canada Bay Council/ }).first(),
  ).toBeVisible();
  await expect(commute).toContainText("核对：2026-10-24");
});
