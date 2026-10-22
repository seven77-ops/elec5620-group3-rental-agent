import { test, expect, type Page } from "@playwright/test";

test("empty-result suggestions require an explicit new message and consent", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const suggestion =
    "只预览房源：Rhodes，至少2卧，至少2卫，车位不限，周租上限890澳元。不要修改已保存的偏好。";
  const conversation = {
    conversation_id: "chat-alternatives",
    case_id: c.case_id,
    title: "Rhodes两卧",
    revision: 1,
    messages: [
      {
        message_id: "empty",
        role: "assistant",
        agent: "agent2",
        created_at: "2026-10-22T00:00:00Z",
        content: "Rhodes的2卧2卫最低周租890，比预算高90。扩大区域有30条。",
        listings: [],
        actions: [
          {
            type: "suggestion",
            label: "看看每周 890 的选择",
            message: suggestion,
          },
        ],
      },
    ],
  };
  const sent: Record<string, unknown>[] = [];
  await page.route(
    `**/api/v1/cases/${c.case_id}/assistant/**`,
    async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith("/messages")) sent.push(route.request().postDataJSON());
      await route.fulfill({
        json: path.endsWith("/conversations")
          ? {
              items: [
                {
                  conversation_id: conversation.conversation_id,
                  title: conversation.title,
                  updated_at: "2026-10-22T00:00:00Z",
                  message_count: 1,
                },
              ],
            }
          : conversation,
      });
    },
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByRole("button", { name: "看看每周 890 的选择", exact: true })
    .click();
  const composer = page.getByRole("textbox", { name: "给租房助手的消息" });
  await expect(composer).toHaveValue(suggestion);
  await expect(
    page.getByRole("checkbox", { name: /同意本次/ }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("button", { name: "发送消息", exact: true }),
  ).toBeDisabled();
  expect(sent).toEqual([]);
  await page.getByRole("checkbox", { name: /同意本次/ }).check();
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
  await expect.poll(() => sent.length).toBe(1);
  expect(sent[0].message).toBe(suggestion);
});

async function assistantTransport(page: Page, caseId: string) {
  let conversation = {
    conversation_id: "chat-test",
    case_id: caseId,
    title: "租房新计划",
    revision: 0,
    messages: [] as object[],
  };
  const requests: Record<string, unknown>[] = [];
  await page.route(`**/api/v1/cases/${caseId}/assistant/**`, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/messages")) {
      const body = route.request().postDataJSON();
      requests.push(body);
      conversation = {
        ...conversation,
        revision: conversation.revision + 1,
        messages: [
          ...conversation.messages,
          {
            message_id: "user-1",
            role: "user",
            content: body.message,
            agent: "assistant",
            created_at: "2026-10-22T00:00:00Z",
            listings: [],
            actions: [],
          },
          {
            message_id: "reply-1",
            role: "assistant",
            content: "请告诉我每周预算和偏好区域。",
            agent: "agent1",
            created_at: "2026-10-22T00:00:01Z",
            listings: [],
            actions: [],
          },
        ],
      };
      await route.fulfill({ json: conversation });
    } else if (
      url.pathname.endsWith("/conversations") &&
      route.request().method() === "GET"
    ) {
      await route.fulfill({
        json: {
          items: [
            {
              conversation_id: conversation.conversation_id,
              title: conversation.title,
              updated_at: "2026-10-22T00:00:00Z",
              message_count: conversation.messages.length,
            },
          ],
        },
      });
    } else await route.fulfill({ json: conversation });
  });
  return requests;
}

test("shared assistant requires consent, sends a turn and restores server history", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const requests = await assistantTransport(page, c.case_id);
  await page.goto(`/cases/${c.case_id}/preferences`);
  await page.getByRole("menuitem", { name: "AI租房助手", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "今天，想住在哪里？" }),
  ).toBeVisible();
  const input = page.getByRole("textbox", { name: "给租房助手的消息" });
  await input.fill("帮我找租房");
  await expect(
    page.getByRole("button", { name: "发送消息", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", {
      name: /同意本次将消息与相关租房、租后资料发送至外部 AI/,
    })
    .check();
  await input.press("Enter");
  await expect(
    page.getByText("请告诉我每周预算和偏好区域。", { exact: true }),
  ).toBeVisible();
  expect(requests).toHaveLength(1);
  expect(requests[0]).toMatchObject({
    message: "帮我找租房",
    expected_revision: 0,
    allow_external_ai: true,
  });
  await expect(
    page.getByRole("checkbox", { name: /同意本次/ }),
  ).not.toBeChecked();
  await page.reload();
  await expect(
    page.getByText("请告诉我每周预算和偏好区域。", { exact: true }),
  ).toBeVisible();
  await page.getByRole("menuitem", { name: "房源推荐", exact: true }).click();
  await expect(
    page.getByRole("menuitem", { name: "AI租房助手", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("mobile assistant fits the viewport and IME Enter does not submit", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const requests = await assistantTransport(page, c.case_id);
  await page.goto(`/cases/${c.case_id}/assistant`);
  const input = page.getByRole("textbox", { name: "给租房助手的消息" });
  await input.fill("悉尼");
  await page.getByRole("checkbox", { name: /同意本次/ }).check();
  await input.dispatchEvent("compositionstart");
  await input.press("Enter");
  await input.dispatchEvent("compositionend");
  expect(requests).toHaveLength(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "历史会话" }).click();
  await expect(page.getByRole("button", { name: "租房新计划" })).toBeVisible();
});

test("retry preserves the original request and prevents a second turn", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await assistantTransport(page, c.case_id);
  const bodies: Record<string, unknown>[] = [];
  await page.route(
    `**/api/v1/cases/${c.case_id}/assistant/conversations/*/messages`,
    async (route) => {
      bodies.push(route.request().postDataJSON());
      if (bodies.length === 1) {
        await route.fulfill({
          status: 503,
          json: {
            error: {
              code: "provider_unavailable",
              message: "模型服务暂时不可用，请重试。",
            },
          },
        });
      } else {
        await route.fulfill({
          json: {
            conversation_id: "chat-test",
            case_id: c.case_id,
            title: "租房新计划",
            revision: 1,
            messages: [
              {
                message_id: "retry-answer",
                role: "assistant",
                content: "现在可以继续整理需求。",
                agent: "agent1",
                created_at: "2026-10-22T00:00:01Z",
                listings: [],
                actions: [],
              },
            ],
          },
        });
      }
    },
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  const input = page.getByRole("textbox", { name: "给租房助手的消息" });
  await input.fill("预算每周800澳元");
  await page.getByRole("checkbox", { name: /同意本次/ }).check();
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
  await expect(
    page.getByText("模型服务暂时不可用，请重试。", { exact: true }),
  ).toBeVisible();
  await expect(input).toBeDisabled();
  await page.getByRole("button", { name: "重试原操作", exact: true }).click();
  await expect(
    page.getByText("现在可以继续整理需求。", { exact: true }),
  ).toBeVisible();
  expect(bodies).toHaveLength(2);
  expect(bodies[1]).toEqual(bodies[0]);
  await expect(input).toBeEnabled();
});

test("proposal displays consequential conditions and applies only after confirmation", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await assistantTransport(page, c.case_id);
  const summary = [
    "每周预算 AUD 800 · 整套 · 不含账单 · 硬上限",
    "入住人数：1 · 租住方式：整租",
    "至少1卧、1卫、0车位",
    "按广告金额粗筛；计价对象和账单待核实",
  ];
  const conversation = {
    conversation_id: "chat-test",
    case_id: c.case_id,
    title: "租房新计划",
    revision: 1,
    messages: [
      {
        message_id: "proposal",
        role: "assistant",
        content: "请确认这些租房条件。",
        agent: "agent1",
        created_at: "2026-10-22T00:00:01Z",
        listings: [],
        actions: [
          {
            type: "apply_preferences",
            label: "应用这些偏好",
            proposal_id: "proposal-test",
            summary,
          },
        ],
      },
    ],
  };
  await page.route(
    `**/api/v1/cases/${c.case_id}/assistant/conversations/chat-test`,
    (route) => route.fulfill({ json: conversation }),
  );
  let applies = 0;
  await page.route(
    `**/api/v1/cases/${c.case_id}/assistant/proposals/proposal-test/apply`,
    async (route) => {
      applies++;
      expect(route.request().postDataJSON()).toMatchObject({ confirmed: true });
      await route.fulfill({
        json: {
          case: c,
          conversation: {
            ...conversation,
            revision: 2,
            messages: [
              ...conversation.messages,
              {
                message_id: "applied",
                role: "assistant",
                content: "新偏好与房源报告已保存。",
                agent: "agent2",
                created_at: "2026-10-22T00:00:02Z",
                listings: [],
                actions: [],
              },
            ],
          },
        },
      });
    },
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(page.getByText(summary[0], { exact: true })).toBeVisible();
  await expect(page.locator(".assistant-proposal-summary")).not.toContainText(
    "广告",
  );
  await page
    .getByRole("button", { name: "确认并同步需求", exact: true })
    .click();
  expect(applies).toBe(0);
  await expect(page.getByRole("dialog")).toContainText(summary[0]);
  await expect(page.getByRole("dialog")).not.toContainText("广告");
  await page.getByRole("button", { name: "继续聊聊", exact: true }).click();
  expect(applies).toBe(0);
  await page
    .getByRole("button", { name: "确认并同步需求", exact: true })
    .click();
  await page
    .getByRole("button", { name: "确认同步并生成推荐", exact: true })
    .click();
  await expect(
    page.getByText("新偏好与房源报告已保存。", { exact: true }),
  ).toBeVisible();
  expect(applies).toBe(1);
});

test("real catalogue cards retain source facts and send explicit comparison IDs", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const catalog = await (
    await request.get("/api/v1/listings?page=1&page_size=2")
  ).json();
  const listings = catalog.items;
  expect(listings).toHaveLength(2);
  const turns = await assistantTransport(page, c.case_id);
  await page.route(
    `**/api/v1/cases/${c.case_id}/assistant/conversations/chat-test`,
    (route) =>
      route.fulfill({
        json: {
          conversation_id: "chat-test",
          case_id: c.case_id,
          title: "租房新计划",
          revision: 1,
          messages: [
            {
              message_id: "cards",
              role: "assistant",
              content: "可以先比较这两套真实房源。",
              agent: "agent2",
              created_at: "2026-10-22T00:00:01Z",
              listings,
              actions: [],
            },
          ],
        },
      }),
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  const first = page.locator(`[data-listing-id="${listings[0].listing_id}"]`);
  await expect(first.getByRole("heading")).toHaveText(listings[0].address);
  await expect(first.getByRole("link", { name: "原始房源 ↗" })).toHaveAttribute(
    "href",
    listings[0].source_url,
  );
  await first.getByRole("button", { name: "房源详情", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("待确认事项");
  await page.keyboard.press("Escape");
  for (const listing of listings)
    await page
      .getByRole("checkbox", { name: `选择比较 ${listing.address}` })
      .check();
  await page.getByRole("button", { name: "比较所选房源", exact: true }).click();
  await page.getByRole("checkbox", { name: /同意本次/ }).check();
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
  await expect(
    page.getByText("请告诉我每周预算和偏好区域。", { exact: true }),
  ).toBeVisible();
  expect(turns[0].listing_ids).toEqual(
    listings.map((listing: { listing_id: string }) => listing.listing_id),
  );
  expect(turns[0].expected_revision).toBe(1);
});

test("composer limits selections and restores editable input after validation errors", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const listings = (
    await (await request.get("/api/v1/listings?page=1&page_size=6")).json()
  ).items;
  expect(listings).toHaveLength(6);
  await assistantTransport(page, c.case_id);
  await page.route(
    `**/api/v1/cases/${c.case_id}/assistant/conversations/chat-test`,
    (route) =>
      route.fulfill({
        json: {
          conversation_id: "chat-test",
          case_id: c.case_id,
          title: "租房新计划",
          revision: 1,
          messages: [
            {
              message_id: "six-cards",
              role: "assistant",
              content: "请选择最多五套比较。",
              agent: "agent2",
              created_at: "2026-10-22T00:00:01Z",
              listings,
              actions: [],
            },
          ],
        },
      }),
  );
  const turns: Record<string, unknown>[] = [];
  await page.route(
    `**/api/v1/cases/${c.case_id}/assistant/conversations/*/messages`,
    async (route) => {
      turns.push(route.request().postDataJSON());
      if (turns.length === 1)
        await route.fulfill({
          status: 422,
          json: {
            error: {
              code: "field_not_supported",
              message: "请调整这次比较条件。",
            },
          },
        });
      else
        await route.fulfill({
          json: {
            conversation_id: "chat-test",
            case_id: c.case_id,
            title: "租房新计划",
            revision: 2,
            messages: [
              {
                message_id: "corrected",
                role: "assistant",
                content: "已按调整后的条件比较。",
                agent: "agent2",
                created_at: "2026-10-22T00:00:02Z",
                listings: [],
                actions: [],
              },
            ],
          },
        });
    },
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  const input = page.getByRole("textbox", { name: "给租房助手的消息" });
  await expect(input).toHaveAttribute("maxlength", "3000");
  await input.fill("房".repeat(3001));
  await expect(input).toHaveValue("房".repeat(3000));
  const boxes = listings.map((listing: { address: string }) =>
    page.getByRole("checkbox", { name: `选择比较 ${listing.address}` }),
  );
  for (const box of boxes.slice(0, 5)) await box.check();
  await expect(boxes[5]).toBeDisabled();
  await expect(boxes[0]).toBeEnabled();
  await boxes[0].uncheck();
  await expect(boxes[5]).toBeEnabled();
  await boxes[5].check();
  await expect(
    page.getByText("已选 5/5 套房源", { exact: true }),
  ).toBeVisible();
  const original = "请比较所选房源";
  await input.fill(original);
  await page.getByRole("checkbox", { name: /同意本次/ }).check();
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
  await expect(
    page.getByText("请调整这次比较条件。", { exact: true }),
  ).toBeVisible();
  await expect(input).toBeEnabled();
  await expect(input).toHaveValue(original);
  await expect(
    page.getByRole("button", { name: "重试原操作", exact: true }),
  ).toHaveCount(0);
  for (const box of boxes.slice(1)) await expect(box).toBeChecked();
  await expect(
    page.getByRole("checkbox", { name: /同意本次/ }),
  ).not.toBeChecked();
  await input.fill("请只比较所选房源的周租");
  await page.getByRole("checkbox", { name: /同意本次/ }).check();
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
  await expect(
    page.getByText("已按调整后的条件比较。", { exact: true }),
  ).toBeVisible();
  expect(turns).toHaveLength(2);
  expect(turns[1].request_id).not.toBe(turns[0].request_id);
  expect(turns[1].listing_ids).toEqual(turns[0].listing_ids);
  expect(turns[1].expected_revision).toBe(1);
});
