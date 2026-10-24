import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";

async function fixture(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const base = `/api/v1/cases/${c.case_id}`;
  await request.post(base + "/profile-confirmations", {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  const run = await (
    await request.post(base + "/evaluations", {
      data: { request_id: "task-fixture", confirmation_version: 1 },
    })
  ).json();
  await request.post(base + "/selections", {
    data: {
      request_id: "pick",
      run_id: run.run_id,
      listing_id: run.report.pending_confirmation[0].listing_id,
      confirmed: true,
    },
  });
  const context = await (
    await request.get(base + "/lease-drafts/context")
  ).json();
  const catalog = await (
    await request.get("/api/v1/listings?page_size=3")
  ).json();
  return {
    c,
    context,
    listings: catalog.items.slice(0, 2),
    extraListing: catalog.items[2],
  };
}

async function transport(
  page: Page,
  caseId: string,
  messages: object[],
  apply?: (body: object) => void,
) {
  let conversation = {
    conversation_id: "chat-task-fixture",
    case_id: caseId,
    title: "比较与合同",
    revision: 2,
    messages,
  };
  await page.route(`**/api/v1/cases/${caseId}/assistant/**`, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/apply")) {
      apply?.(route.request().postDataJSON());
      conversation = {
        ...conversation,
        revision: 3,
        messages: conversation.messages.map((m: any) =>
          m.lease_proposal
            ? {
                ...m,
                lease_proposal: { ...m.lease_proposal, status: "applied" },
              }
            : m,
        ),
      };
      await route.fulfill({ json: { draft: { version: 1 }, conversation } });
    } else
      await route.fulfill({
        json: path.endsWith("/conversations")
          ? {
              items: [
                {
                  ...conversation,
                  message_count: messages.length,
                  updated_at: "2026-10-24T00:00:00Z",
                },
              ],
            }
          : conversation,
      });
  });
}
const entry = {
  message_id: "task-result",
  role: "assistant",
  agent: "agent2",
  intent: "workflow",
  created_at: "2026-10-24T00:00:00Z",
  content: "已比较两套房源，并准备询问草稿。",
  actions: [],
};

test("completed workflow retains empty search explanations", async ({
  page,
  request,
}) => {
  const { c } = await fixture(request);
  const explanation = "当前区域和预算下没有匹配房源，请调整预算或扩大区域。";
  await transport(page, c.case_id, [
    {
      ...entry,
      listings: [],
      content: explanation,
      task_steps: [
        { label: "筛选房源", status: "completed", detail: explanation },
      ],
    },
  ]);
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(page.getByText(explanation, { exact: true })).toBeVisible();
});

test("workflow retains additional search cards alongside a comparison", async ({
  page,
  request,
}) => {
  const { c, listings, extraListing } = await fixture(request);
  await transport(page, c.case_id, [
    {
      ...entry,
      listings: [...listings, extraListing],
      task_steps: [
        { label: "比较房源", status: "completed", detail: "已比较已选房源。" },
      ],
      comparison: {
        basis: "按本次明确要求",
        summary: "已比较两套房源。",
        recommended_listing_id: null,
        items: listings.map((row: any) => ({
          listing_id: row.listing_id,
          matches: [],
          tradeoffs: [],
          to_verify: [],
        })),
      },
    },
  ]);
  await page.goto(`/cases/${c.case_id}/assistant`);
  const extra = page.locator(`[data-listing-id="${extraListing.listing_id}"]`);
  await expect(
    extra.getByRole("heading", { name: extraListing.address, exact: true }),
  ).toBeVisible();
  await expect(
    extra.getByRole("button", { name: "房源详情", exact: true }),
  ).toBeVisible();
  await expect(
    extra.getByRole("button", { name: "保存为候选", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: listings[0].address, exact: true }),
  ).toHaveCount(1);
});

test("personal comparison shows tradeoffs, verification questions and a copyable enquiry", async ({
  page,
  request,
}) => {
  const { c, listings } = await fixture(request);
  await transport(page, c.case_id, [
    {
      ...entry,
      listings,
      comparison: {
        basis: "按你当前确认的租房需求",
        recommended_listing_id: listings[0].listing_id,
        summary: "你不需要车位，因此优先比较租金与卧卫。",
        items: listings.map((r: any) => ({
          listing_id: r.listing_id,
          matches: ["符合已指定的卧卫要求"],
          tradeoffs: ["你不需要车位，不把车位更多作为推荐优势"],
          to_verify: ["租金计价对象与账单待确认"],
        })),
      },
      task_steps: [
        {
          label: "比较两套房源",
          status: "completed",
          detail: "已按当前需求核对",
        },
        { label: "准备看房询问", status: "completed", detail: "尚未发送" },
      ],
      enquiry: {
        listing_id: listings[0].listing_id,
        address: listings[0].address,
        subject: "Inspection enquiry",
        body: "Hello, could I arrange an inspection?",
        questions: ["请确认可入住日期及是否包含账单。"],
        source_url: listings[0].source_url,
      },
      verification_checklist: {
        title: "看房时重点核实",
        items: ["检查临街情况和窗户隔音。"],
      },
    },
  ]);
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(
    page.getByRole("heading", { name: "按你的需求比较", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("你不需要车位，因此优先比较租金与卧卫。", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "看房询问草稿", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "看房询问内容", exact: true }),
  ).toHaveValue("Hello, could I arrange an inspection?");
  await expect(
    page.getByRole("button", { name: "复制看房询问", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("检查临街情况和窗户隔音。", { exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 360, height: 900 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("chat lease review requires applicability and confirmation, cancel never applies", async ({
  page,
  request,
}) => {
  const { c, context } = await fixture(request);
  const fields = {
    ...context.defaults,
    landlord_name: "Austin",
    tenant_names: "Mike",
    rent_amount: 650,
    rent_period: "week",
    lease_type: "fixed",
    lease_term_months: 12,
    start_date: "2026-11-01",
    end_date: "2027-11-01",
  };
  const applied: any[] = [];
  await transport(
    page,
    c.case_id,
    [
      {
        ...entry,
        agent: "agent3",
        intent: "draft_contract",
        content: "已整理合同信息，请核对后确认。",
        listings: [],
        lease_proposal: {
          proposal_id: "lease-chat-test",
          status: "pending",
          fields,
          patch: {
            landlord_name: "Austin",
            tenant_names: "Mike",
            rent_amount: 650,
            rent_period: "week",
            lease_term_months: 12,
          },
          questions: [
            {
              field: "landlord_contact",
              label: "出租方联系方式",
              question: "出租方联系方式是什么？",
            },
          ],
          base_version: 0,
        },
      },
    ],
    (body) => applied.push(body),
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page.getByRole("button", { name: "核对合同字段", exact: true }).click();
  const modal = page.getByRole("dialog", {
    name: "核对并同步合同草稿",
    exact: true,
  });
  await expect(modal).toContainText("Austin");
  await expect(modal).toContainText("Mike");
  await expect(
    modal.getByRole("button", { name: "确认保存并同步合同", exact: true }),
  ).toBeDisabled();
  await modal.getByRole("button", { name: "继续修改", exact: true }).click();
  expect(applied).toHaveLength(0);
  await page.getByRole("button", { name: "核对合同字段", exact: true }).click();
  await modal.getByRole("checkbox").check();
  await modal
    .getByRole("button", { name: "确认保存并同步合同", exact: true })
    .click();
  await expect.poll(() => applied.length).toBe(1);
  expect(applied[0]).toMatchObject({
    confirmed: true,
    applicability_confirmed: true,
    expected_revision: 2,
  });
  await expect(
    page.getByText("已同步到合同助手", { exact: true }),
  ).toBeVisible();
});
