import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
const root = resolve(process.cwd(), "..");
const artifactDir = resolve(root, ".runtime/qa");
mkdirSync(artifactDir, { recursive: true });
async function seed(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await request.post(`/api/v1/cases/${c.case_id}/profile-confirmations`, {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  const e = await (
    await request.post(`/api/v1/cases/${c.case_id}/evaluations`, {
      data: {
        request_id: `test-${crypto.randomUUID()}`,
        confirmation_version: 1,
      },
    })
  ).json();
  return { c, e };
}
async function navigate(page: Page, name: string) {
  await page.getByRole("menuitem", { name: new RegExp(name) }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}

test("tenant completes confirmed profile, true recommendation, selection, contract review and restoration", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto("/");
  await expect(page).toHaveTitle("租房助手 · ELEC5620");
  await page.getByRole("button", { name: "新建演示案例", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "生成推荐", exact: true }),
  ).toBeDisabled();
  await expect(page.getByText("Agent1 本地偏好服务已接入", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "确认当前偏好", exact: true }).click();
  await expect(page.getByText("房源为固定时点的合成数据。居住人数会被记录，但当前不检查房源可容纳人数。", { exact: true })).toHaveCount(2);
  await page.getByRole("button", { name: "确认这些条件", exact: true }).click();
  await expect(
    page.getByText("当前草稿已确认 · v1", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "生成推荐", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "房源推荐", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "全部合格 15", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "待确认 9", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "已排除 5", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "重复记录 1", exact: true }),
  ).toBeVisible();
  const first = page.locator("article.listing-row").first();
  await expect(first).toContainText("DEMO-006");
  await expect(first).toContainText("92.75");
  await page.screenshot({
    path: resolve(artifactDir, "recommendations-desktop.png"),
  });
  await first.getByRole("button", { name: "查看推荐依据" }).click();
  await expect(
    page.getByText("fixture:DEMO-006#rent_amount", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("tab", { name: "待确认 9", exact: true }).click();
  await expect(page.getByText("未评分", { exact: true })).toHaveCount(9);
  await expect(
    page.getByRole("button", { name: "选择此房源", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("tab", { name: "推荐房源 5", exact: true }).click();
  await first.getByRole("button", { name: "选择此房源", exact: true }).click();
  await page
    .getByRole("button", { name: "确认选择此房源", exact: true })
    .click();
  await page.getByRole("button", { name: "继续合同复核", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "合同复核", exact: true }),
  ).toBeVisible();
  await expect(page.locator("input[type=file]")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "同意处理此合同", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", {
      name: "我同意为本次复核处理此合同，理解此同意独立于选房确认。",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "同意处理此合同", exact: true })
    .click();
  await page
    .locator("input[type=file]")
    .setInputFiles(
      resolve(root, "agent3/data/demo/agreements/selection-demo.txt"),
    );
  await page
    .getByRole("checkbox", {
      name: "我确认上传的是合成演示合同。",
      exact: true,
    })
    .check();
  await page.getByRole("button", { name: "上传并复核", exact: true }).click();
  await expect(page.getByText("复核完成", { exact: true })).toBeVisible();
  await expect(
    page.getByText("当前复核没有发现项，不生成额外问题。", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "准备问题清单", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "查看原文", exact: true })
    .first()
    .click();
  await expect(page.locator("blockquote")).toContainText("Address:");
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  const caseId = page.url().split("/")[4];
  const c = await (await request.get(`/api/v1/cases/${caseId}`)).json();
  const selection = await (
    await request.get(`/api/v1/cases/${caseId}/exports/selection`)
  ).json();
  expect(selection.listing_id).toBe("DEMO-006");
  expect(c.agent1.state).toBe("Confirmed");
  expect(c.confirmations[0].source).toBe("agent1");
  expect(c.evaluations[0].agent1_task_id).toMatch(/^task-/);
  expect(c.aftercare_case_id).toBeNull();
  await page.reload();
  await expect(page.getByText("复核完成", { exact: true })).toBeVisible();
  await page.screenshot({ path: resolve(artifactDir, "contract-desktop.png") });
  await expect(page.locator("vite-error-overlay")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("edited preferences require reconfirmation and zero-match remains a valid report with history", async ({
  page,
  request,
}) => {
  const { c } = await seed(request);
  await page.goto(`/cases/${c.case_id}/preferences`);
  await page.getByRole("spinbutton", { name: "期望周预算（AUD）" }).fill("1");
  await page.getByRole("spinbutton", { name: "最高周预算（AUD）" }).fill("1");
  await expect(
    page.getByRole("button", { name: "生成推荐", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "保存草稿", exact: true }).click();
  await expect(
    page.getByText("当前草稿尚未确认", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "确认当前偏好", exact: true }).click();
  await page.getByRole("button", { name: "确认这些条件", exact: true }).click();
  await expect(
    page.getByText("当前草稿已确认 · v2", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "生成推荐", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "房源推荐", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "推荐房源 0", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("当前分类没有房源。可查看其他分类或返回偏好调整条件。", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "查看偏好版本比较", exact: true })
    .click();
  await expect(page.getByText("偏好变化", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.confirmations).toHaveLength(2);
  expect(saved.evaluations).toHaveLength(2);
});

test("independent aftercare requires confirmation and supports tasks, dispute gate, operator and reminders", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "新建演示案例", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "租房偏好", exact: true }),
  ).toBeVisible();
  await navigate(page, "租后服务");
  await expect(
    page.getByRole("button", { name: "确认资料并创建租后案件", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", {
      name: "我已核对并确认上述租约、房间、家具及资料来源。",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "确认资料并创建租后案件", exact: true })
    .click();
  await expect(page.getByText("已确认租约资料", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "生成并确认计划", exact: true })
    .click();
  await page.getByRole("button", { name: "确认计划", exact: true }).click();
  await expect(
    page.getByText("Clean Bedroom and record its condition", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "编辑任务", exact: true })
    .first()
    .click();
  await page.getByRole("combobox", { name: "任务状态", exact: true }).click();
  await page.getByText("已完成", { exact: true }).last().click();
  await page.getByRole("button", { name: "保存任务", exact: true }).click();
  await expect(page.getByText("已完成", { exact: true }).first()).toBeVisible();
  await page.getByLabel("提议新的退租日期", { exact: true }).fill("2026-11-02");
  await page.getByRole("button", { name: "提交改期提案", exact: true }).click();
  await page.getByRole("button", { name: "提交提案", exact: true }).click();
  await expect(
    page.getByText("有待确认的日期变更", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "编辑任务", exact: true })
    .first()
    .click();
  await page
    .getByRole("dialog")
    .getByRole("textbox", { name: "任务内容" })
    .fill("Synthetic completed task during pending proposal");
  await page.getByRole("button", { name: "保存任务", exact: true }).click();
  await expect(
    page.getByText("Synthetic completed task during pending proposal", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("有待确认的日期变更", { exact: true }),
  ).toBeVisible();

  await page.getByRole("button", { name: "确认改期", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "确认改期", exact: true })
    .click();
  await expect(
    page.getByText("有待确认的日期变更", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("tab", { name: "押金跟进", exact: true }).click();
  await page.getByRole("button", { name: "建立押金跟进", exact: true }).click();
  await page
    .getByRole("button", { name: "确认事实并激活跟进", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "租客报告的事实" })
    .fill("Synthetic report: keys return arranged; no outcome yet.");
  await page.getByRole("button", { name: "确认并记录", exact: true }).click();
  await expect(page.getByText("等待结果", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "记录新事实或扣款主张", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "租客报告的事实" })
    .fill("Synthetic tenant disputes a reported deduction.");
  await page
    .getByRole("checkbox", { name: "包含一项报告的扣款主张", exact: true })
    .check();
  await page
    .getByRole("textbox", { name: "报告的扣款原因" })
    .fill("Synthetic wall mark");
  await page.getByRole("button", { name: "确认并记录", exact: true }).click();
  await expect(
    page.getByText("存在争议或审核门禁", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "准备跟进草稿", exact: true }),
  ).toBeDisabled();
  await page.getByRole("link", { name: "本地演示操作员", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "本地演示操作员", exact: true }),
  ).toBeVisible();
  await page.getByLabel("本地操作员密钥", { exact: true }).fill("qa-local-key");
  await page
    .getByLabel("人工核对记录")
    .fill("Synthetic test evidence reviewed; no liability determination.");
  await page
    .getByRole("combobox", { name: "押金审核决定", exact: true })
    .click();
  await page.getByText("已核对并解除门禁", { exact: true }).click();
  await page
    .getByRole("button", { name: "记录选定的审核决定", exact: true })
    .click();
  await page.getByRole("button", { name: "确认记录", exact: true }).click();
  await expect(
    page.getByText("当前案例没有未决押金审核事项。", { exact: true }),
  ).toBeVisible();
  await navigate(page, "租后服务");
  await page.getByRole("tab", { name: "押金跟进", exact: true }).click();
  await page.getByRole("button", { name: "准备跟进草稿", exact: true }).click();
  await expect(
    page.getByText("跟进草稿 · 尚未发送", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "本地提醒", exact: true }).click();
  await page.getByRole("switch", { name: "开启本地提醒", exact: true }).click();
  await expect(page.getByText("提醒已开启", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "查询到期提醒", exact: true }).click();
  await expect(
    page.getByText("当前没有已投递提醒。", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("tab", { name: "押金跟进", exact: true }).click();
  await page
    .getByLabel("你确认的结果或撤回原因", { exact: true })
    .fill("Synthetic outcome explicitly confirmed by tenant.");
  await page
    .getByRole("button", { name: "确认结果并关闭跟进", exact: true })
    .click();
  await page
    .getByRole("button", { name: "确认结果并关闭", exact: true })
    .click();
  await expect(page.getByText("已确认结果", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("已确认租约资料", { exact: true })).toBeVisible();
  await page.screenshot({
    path: resolve(artifactDir, "aftercare-desktop.png"),
  });
});

for (const width of [360, 768, 1440])
  test(`responsive recommendation and keyboard evidence drawer at ${width}px`, async ({
    page,
    request,
  }) => {
    const { c } = await seed(request);
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(`/cases/${c.case_id}/recommendations`);
    await expect(
      page.getByRole("heading", { name: "房源推荐", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    await page
      .locator("article.listing-row")
      .first()
      .getByRole("button", { name: "查看推荐依据", exact: true })
      .focus();
    await page.keyboard.press("Enter");
    await expect(
      page.getByText("四维匹配分与有效权重", { exact: true }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await page.screenshot({
      path: resolve(artifactDir, `recommendations-${width}.png`),
    });
  });

test("contract conflict requires operator, prepares unsent questions and retains history after correction and revoke", async ({
  page,
  request,
}) => {
  const { c, e } = await seed(request);
  await request.post(`/api/v1/cases/${c.case_id}/selections`, {
    data: {
      request_id: `select-${crypto.randomUUID()}`,
      run_id: e.run_id,
      listing_id: "DEMO-006",
      confirmed: true,
    },
  });
  await page.goto(`/cases/${c.case_id}/contract`);
  await page
    .getByRole("checkbox", {
      name: "我同意为本次复核处理此合同，理解此同意独立于选房确认。",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "同意处理此合同", exact: true })
    .click();
  const buffer = Buffer.from(
    readFileSync(
      resolve(root, "agent3/data/demo/agreements/selection-demo.txt"),
      "utf8",
    ).replace("$500", "$650"),
  );
  await page.locator("input[type=file]").setInputFiles({
    name: "rent-conflict.txt",
    mimeType: "text/plain",
    buffer,
  });
  await page
    .getByRole("checkbox", {
      name: "我确认上传的是合成演示合同。",
      exact: true,
    })
    .check();
  await page.getByRole("button", { name: "上传并复核", exact: true }).click();
  await expect(
    page.getByText("等待本地演示操作员处理", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "准备问题清单", exact: true }),
  ).toBeDisabled();
  await page.getByRole("link", { name: "本地演示操作员", exact: true }).click();
  await page.getByLabel("本地操作员密钥", { exact: true }).fill("qa-local-key");
  await page
    .getByLabel("人工核对记录")
    .fill("Synthetic rent difference reviewed; demonstration decision only.");
  await page
    .getByRole("button", { name: "完成本次人工复核", exact: true })
    .click();
  await page.getByRole("button", { name: "记录人工决定", exact: true }).click();
  await expect(
    page.getByText("当前案例没有待人工复核的合同。", { exact: true }),
  ).toBeVisible();
  await navigate(page, "合同复核");
  await page.getByRole("button", { name: "准备问题清单", exact: true }).click();
  await expect(
    page.getByText("问题清单 · 尚未发送", { exact: true }),
  ).toBeVisible();
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  const reviewId = saved.reviews.at(-1).review_id;
  const packet = await (
    await request.get(`/api/v1/contract-reviews/${reviewId}/questions/export`)
  ).json();
  expect(packet.handoff_status).toBe("prepared_not_sent");
  expect(packet.questions.length).toBeGreaterThan(0);
  await page.getByRole("button", { name: "修正提取字段", exact: true }).click();
  await page.getByRole("spinbutton", { name: "合同租金（AUD）" }).fill("500");
  await page
    .getByRole("button", { name: "保存为新复核版本", exact: true })
    .click();
  await expect(page.getByText("复核版本 v2", { exact: true })).toBeVisible();
  await expect(
    page.getByText("当前复核没有发现项，不生成额外问题。", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "查看历史复核版本", exact: true })
    .click();
  await expect(page.getByText("历史快照只读", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page
    .getByRole("button", { name: "撤销本次复核处理同意", exact: true })
    .click();
  await expect(
    page.getByText("本次复核处理同意未生效或上下文已变化", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "修正提取字段", exact: true }),
  ).toBeDisabled();
  await expect(page.locator("input[type=file]")).toHaveCount(0);
});

test("failed case navigation never exposes writes to the previous case", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "新建演示案例", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "租房偏好", exact: true }),
  ).toBeVisible();
  const caseA = page.url().split("/")[4];
  await page.getByRole("button", { name: "新建案例", exact: true }).click();
  await expect(page).not.toHaveURL(new RegExp(caseA));
  await expect(
    page.getByRole("heading", { name: "租房偏好", exact: true }),
  ).toBeVisible();
  await page.route(`**/api/v1/cases/${caseA}`, (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "test_unavailable",
          message: "Temporary case read failure",
          request_id: "case-read-test",
        },
      }),
    }),
  );
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(caseA));
  await expect(
    page.getByText("Temporary case read failure", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "保存草稿", exact: true }),
  ).toHaveCount(0);
});

test("failed report selection preserves clearly labeled prior data and disables mixed report actions", async ({
  page,
  request,
}) => {
  const { c, e } = await seed(request);
  let current = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  const profile = structuredClone(current.draft.profile);
  profile.weights.cost = 0.9;
  current = await (
    await request.post(`/api/v1/cases/${c.case_id}/profile-drafts`, {
      data: { expected_revision: current.draft.revision, profile },
    })
  ).json();
  await request.post(`/api/v1/cases/${c.case_id}/profile-confirmations`, {
    data: {
      draft_revision: current.draft.revision,
      fingerprint: current.draft.fingerprint,
      review_token: current.agent1.review_token,
    },
  });
  await request.post(`/api/v1/cases/${c.case_id}/evaluations`, {
    data: {
      request_id: `evaluate-${crypto.randomUUID()}`,
      confirmation_version: 2,
    },
  });
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(page.locator("article.listing-row").first()).toBeVisible();
  await page.route(`**/api/v1/evaluations/${e.run_id}`, (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "test_unavailable",
          message: "Temporary report read failure",
          request_id: "report-read-test",
        },
      }),
    }),
  );
  await page
    .getByRole("combobox", { name: "选择推荐版本", exact: true })
    .click();
  await page.getByText("偏好 v1 · 报告 1", { exact: true }).click();
  await expect(
    page.getByText("所选报告尚未成功读取", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "选择此房源", exact: true }).first(),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "查看推荐依据", exact: true }).first(),
  ).toBeDisabled();
});

test("lost aftercare response preserves modal input and retry identity while reminder polling stays paused", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const config = await (await request.get("/api/v1/demo-config")).json();
  let version = 0;
  for (const [operation, payload] of [
    [
      "create",
      {
        tenancy: { ...config.tenancy_template, confirmed: true },
        evidence: config.capabilities.aftercare_evidence_template,
      },
    ],
    ["create_plan", { move_out_date: "2026-10-31", schedule_confirmed: true }],
    ["reminder_preferences", { enabled: true, follow_up_at: null }],
  ] as const) {
    const response = await request.post("/api/v1/aftercare/commands", {
      data: {
        case_id: c.case_id,
        request_id: `seed-${crypto.randomUUID()}`,
        expected_version: version,
        operation,
        payload,
      },
    });
    expect(response.ok()).toBeTruthy();
    version = (await response.json()).version;
  }
  const commands: Record<string, unknown>[] = [];
  let loseResponse = true;
  await page.route("**/api/v1/aftercare/commands", async (route) => {
    const body = route.request().postDataJSON();
    commands.push(body);
    if (body.operation === "edit_task" && loseResponse) {
      loseResponse = false;
      const result = await route.fetch();
      expect(result.ok()).toBeTruthy();
      await route.abort("failed");
    } else await route.continue();
  });
  await page.clock.install();
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await page
    .getByRole("button", { name: "编辑任务", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("textbox", { name: "任务内容" })
    .fill("Synthetic task edited before response loss");
  await dialog.getByRole("button", { name: "保存任务", exact: true }).click();
  await expect(dialog.getByText("操作未完成", { exact: true })).toBeVisible();
  await expect(dialog.getByRole("textbox", { name: "任务内容" })).toHaveValue(
    "Synthetic task edited before response loss",
  );
  await page.clock.fastForward(31_000);
  expect(commands.some((c) => c.operation === "poll_reminders")).toBeFalsy();
  await dialog.getByRole("button", { name: "重试原操作", exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(
    page.getByText("Synthetic task edited before response loss", {
      exact: true,
    }),
  ).toBeVisible();
  const retries = commands.filter((c) => c.operation === "edit_task");
  expect(retries).toHaveLength(2);
  expect(retries[1]).toEqual(retries[0]);
});

async function seedAftercare(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const config = await (await request.get("/api/v1/demo-config")).json();
  let version = 0,
    m4id = "";
  for (const [operation, payload] of [
    [
      "create",
      {
        tenancy: { ...config.tenancy_template, confirmed: true },
        evidence: config.capabilities.aftercare_evidence_template,
      },
    ],
    ["create_plan", { move_out_date: "2026-10-31", schedule_confirmed: true }],
  ] as const) {
    const response = await request.post("/api/v1/aftercare/commands", {
      data: {
        case_id: c.case_id,
        request_id: `seed-${crypto.randomUUID()}`,
        expected_version: version,
        operation,
        payload,
      },
    });
    expect(response.ok()).toBeTruthy();
    const result = await response.json();
    version = result.version;
    m4id = result.case_id;
  }
  return { c, m4id };
}

test("cancelling a failed task edit cannot retry the previous task from a new edit session", async ({
  page,
  request,
}) => {
  const { c, m4id } = await seedAftercare(request);
  let fail = true;
  await page.route("**/api/v1/aftercare/commands", async (route) => {
    const body = route.request().postDataJSON();
    if (body.operation === "edit_task" && fail)
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "version_conflict",
            message: "Synthetic task conflict",
            request_id: body.request_id,
          },
        }),
      });
    else await route.continue();
  });
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await page
    .getByRole("button", { name: "编辑任务", exact: true })
    .first()
    .click();
  let dialog = page.getByRole("dialog");
  await dialog
    .getByRole("textbox", { name: "任务内容" })
    .fill("Unsubmitted first task edit");
  await dialog.getByRole("button", { name: "保存任务", exact: true }).click();
  await expect(
    dialog.getByText("Synthetic task conflict", { exact: true }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "取消本次编辑", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  await page
    .getByRole("button", { name: "编辑任务", exact: true })
    .nth(1)
    .click();
  dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("button", { name: "重试原操作", exact: true }),
  ).toHaveCount(0);
  await expect(
    dialog.getByRole("textbox", { name: "任务内容" }),
  ).not.toHaveValue("Unsubmitted first task edit");
  fail = false;
  await dialog
    .getByRole("textbox", { name: "任务内容" })
    .fill("Second task intentional edit");
  await dialog.getByRole("button", { name: "保存任务", exact: true }).click();
  await expect(dialog).toBeHidden();
  const record = await (
    await request.get(`/api/v1/aftercare/cases/${m4id}`)
  ).json();
  expect(record.plan.tasks[0].title).not.toBe("Unsubmitted first task edit");
  expect(record.plan.tasks[1].title).toBe("Second task intentional edit");
});

test("an existing aftercare read failure offers recovery instead of creating a second tenancy", async ({
  page,
  request,
}) => {
  const { c, m4id } = await seedAftercare(request);
  const pattern = `**/api/v1/aftercare/cases/${m4id}`;
  await page.route(pattern, (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "service_failure",
          message: "Synthetic aftercare read unavailable",
          request_id: "read-existing",
        },
      }),
    }),
  );
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await expect(
    page.getByText("Synthetic aftercare read unavailable", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "确认资料并创建租后案件", exact: true }),
  ).toHaveCount(0);
  await page.unroute(pattern);
  await page.getByRole("button", { name: "读取最新状态", exact: true }).click();
  await expect(page.getByText("已确认租约资料", { exact: true })).toBeVisible();
});
