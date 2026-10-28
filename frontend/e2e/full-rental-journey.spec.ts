import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { confirmRentalNeeds, fillRentalNeeds } from "./fillRentalNeeds";

async function choose(
  page: Page,
  scope: Page | Locator,
  label: string,
  option: string,
) {
  const control = scope.getByLabel(label, { exact: true });
  await control.click();
  const listId = await control.getAttribute("aria-controls");
  expect(listId).toBeTruthy();
  await page
    .locator(".ant-select-dropdown")
    .filter({ has: page.locator(`[id="${listId}"]`) })
    .locator(".ant-select-item-option-content")
    .getByText(option, { exact: true })
    .click();
}

test("完整主流程：找房 → 收藏跟进 → 合同生成复核 → 租后服务 → 报修 → 退租押金", async ({
  page,
  request,
}, info) => {
  test.skip(
    process.env.FULL_JOURNEY_ISOLATED !== "1",
    "请通过 scripts/test_full_journey.py 启动隔离环境。",
  );
  test.setTimeout(240_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let root = "",
    caseId = "",
    address = "",
    agreedRent = 0;
  const today = new Date();
  const start = `${today.getFullYear() + 1}-01-01`;
  const end = `${today.getFullYear() + 2}-01-01`;
  const state = async () => (await request.get(root)).json();
  const living = async () =>
    (await request.get(`${root}/living-services`)).json();
  const screenshot = async (name: string) => {
    const path = info.outputPath(`${name}.png`);
    await page.screenshot({ path, animations: "disabled" });
    await info.attach(name, { path, contentType: "image/png" });
  };

  await test.step("01 从首页新建案例，并通过聊天收集找房条件", async () => {
    await page.goto("/");
    await page
      .getByRole("button", { name: "新建演示案例", exact: true })
      .click();
    await expect(page).toHaveURL(/\/cases\/[^/]+\/assistant$/);
    caseId = new URL(page.url()).pathname.split("/")[2];
    root = `/api/v1/cases/${caseId}`;
    const input = page.getByRole("textbox", {
      name: "给租房助手的消息",
      exact: true,
    });
    await input.fill(
      "想找悉大步行20分钟以内的整租，每周1200澳元，至少1卧1卫，1人入住，不限区域。",
    );
    await input.press("Enter");
    await expect(
      page.locator(".commute-results .commute-home").first(),
    ).toBeVisible();
    const controls = page.getByRole("region", {
      name: "本次找房条件",
      exact: true,
    });
    await expect(controls).toContainText("步行");
    await expect(controls).toContainText("≤20分钟");
    expect((await state()).selection).toBeNull();
    expect((await state()).confirmations).toHaveLength(0);
  });

  await test.step("02 零结果调整方案使用真实计数；用户选择后才改变预算", async () => {
    const reference = await (
      await request.get(
        "/api/v1/listings?min_bedrooms=1&min_bathrooms=1&usyd_mode=walk&usyd_max_minutes=20&sort=rent_asc",
      )
    ).json();
    expect(reference.items.length).toBeGreaterThan(1);
    const cap = reference.items[0].weekly_rent - 25;
    const controls = page.getByRole("region", {
      name: "本次找房条件",
      exact: true,
    });
    async function budget(value: number) {
      await controls
        .getByRole("button", { name: "修改预算条件", exact: true })
        .click();
      const dialog = page.getByRole("dialog", {
        name: "调整预算",
        exact: true,
      });
      await dialog
        .getByRole("spinbutton", { name: "本次预算上限", exact: true })
        .fill(String(value));
      await dialog
        .getByRole("button", { name: "应用修改并重新筛选", exact: true })
        .click();
      await expect(dialog).toHaveCount(0);
    }
    await budget(cap);
    await expect(controls).toContainText("已筛选 0 套");
    const conversations = await (
      await request.get(`${root}/assistant/conversations`)
    ).json();
    const contextUrl = `${root}/assistant/conversations/${conversations.items[0].conversation_id}/recommendation-context`;
    const context = await (await request.get(contextUrl)).json();
    const option = context.alternatives.find(
      (item: { id: string }) => item.id === "budget",
    );
    expect(option.count).toBeGreaterThan(0);
    expect(context.criteria.budget_amount).toBe(cap);
    await controls
      .getByRole("button", {
        name: `${option.label} · 可找到 ${option.count} 套`,
        exact: true,
      })
      .click();
    await expect(controls).toContainText(`已筛选 ${option.count} 套`);
    const updated = await (await request.get(contextUrl)).json();
    expect(updated.criteria).toMatchObject({
      budget_amount: cap + 50,
      commute_mode: "walk",
      commute_max_minutes: 20,
    });
    await budget(1200);
    const results = page.locator(".commute-results").last();
    await expect(
      results.getByRole("list", { name: "推荐理由" }).first(),
    ).toContainText("步行");
    await expect(results).not.toContainText("平均通勤");
    await controls
      .getByRole("button", { name: "修改通勤条件", exact: true })
      .click();
    const commute = page.getByRole("dialog", { name: "调整通勤", exact: true });
    await choose(page, commute, "本次交通方式", "公共交通");
    await commute.getByLabel("本次通勤上限", { exact: true }).fill("30");
    await commute
      .getByRole("button", { name: "应用修改并重新筛选", exact: true })
      .click();
    await expect(commute).toHaveCount(0);
    await expect(controls).toContainText("公共交通 ≤30分钟");
    await expect(
      results.getByRole("list", { name: "推荐理由" }).first(),
    ).toContainText("公共交通");
    await expect(results).not.toContainText("平均通勤");
    const publicContext = await (await request.get(contextUrl)).json();
    const currentConversation = await (
      await request.get(contextUrl.replace(/\/recommendation-context$/, ""))
    ).json();
    expect(currentConversation.messages.at(-1).listings).toHaveLength(
      publicContext.total,
    );
    await results.getByRole("button", { name: "全部", exact: true }).click();
    await expect(results.locator(".commute-home")).toHaveCount(
      Math.min(12, publicContext.total),
    );
    await screenshot("01-recommendations");
  });

  await test.step("03 确认需求，收藏两套并比较；收藏本身不选定房源", async () => {
    await page
      .getByRole("button", { name: "我的租房需求", exact: true })
      .click();
    await fillRentalNeeds(page, { budget: 1200, bedrooms: 1, bathrooms: 1 });
    await confirmRentalNeeds(page);
    expect((await state()).confirmations).toHaveLength(1);
    await page.getByRole("menuitem", { name: "房源推荐", exact: true }).click();
    const table = page.getByTestId("real-catalog");
    for (let n = 1; n <= 2; n++) {
      await table
        .getByRole("button", { name: "收藏房源", exact: true })
        .first()
        .click();
      await expect(
        table.getByRole("button", { name: "取消收藏", exact: true }),
      ).toHaveCount(n);
    }
    expect((await state()).selection).toBeNull();
    await page.reload();
    await page
      .getByRole("button", { name: "我的收藏（2）", exact: true })
      .click();
    const drawer = page.getByRole("dialog", { name: "我的收藏", exact: true });
    await expect(drawer.getByTestId("favorite-home")).toHaveCount(2);
    await drawer.getByRole("checkbox").nth(0).check();
    await drawer.getByRole("checkbox").nth(1).check();
    await expect(
      drawer.getByRole("table", { name: "收藏房源比较" }),
    ).toBeVisible();
    await screenshot("02-favorites-comparison");
    await drawer
      .getByRole("button", { name: "选定并跟进", exact: true })
      .first()
      .click();
    expect((await state()).selection).toBeNull();
    await page
      .getByRole("button", { name: "确认并开始跟进", exact: true })
      .click();
    await expect(drawer).not.toBeVisible();
    const selected = (await state()).selection;
    address = selected.listing_snapshot.address;
    agreedRent = selected.listing_snapshot.weekly_rent + 20;
    expect(selected.contract_ready).toBe(false);
    await expect(page.getByTestId("candidate-next")).toContainText(address);
  });

  await test.step("04 记录中介回复，跨页面保留约定租金及来源", async () => {
    await page
      .getByTestId("candidate-next")
      .getByRole("button", { name: "准备看房与询问", exact: true })
      .click();
    const drawer = page.getByRole("dialog", { name: "房源跟进", exact: true });
    await drawer
      .getByLabel("回复中的租金（AUD）", { exact: true })
      .fill(String(agreedRent));
    await choose(page, drawer, "租金周期", "每周");
    await choose(page, drawer, "租金计价对象", "整套");
    await drawer
      .getByLabel("信息来源", { exact: true })
      .fill("E2E synthetic agent reply");
    await drawer
      .getByLabel("看房安排", { exact: true })
      .fill("仅测试记录：周六看房，尚未向中介发送预约。");
    await drawer
      .getByRole("button", { name: "确认保存跟进信息", exact: true })
      .click();
    await expect(
      drawer.getByText("已保存 v1 · 用户记录", { exact: true }),
    ).toBeVisible();
    expect((await state()).selection.contract_ready).toBe(false);
    await drawer.getByRole("button", { name: "关闭", exact: true }).click();
    await page
      .getByTestId("candidate-next")
      .getByRole("button", { name: "生成租约草稿", exact: true })
      .click();
    await expect(page.getByLabel("房屋地址", { exact: true })).toHaveValue(
      address,
    );
    await expect(
      page.getByLabel("拟定租金（AUD）", { exact: true }),
    ).toHaveAttribute("aria-valuenow", String(agreedRent));
  });

  await test.step("05 录入双方及中介资料，明确确认后生成并检查真实 PDF", async () => {
    await choose(page, page, "租约适用范围", "新州普通整租住宅");
    for (const [label, value] of [
      ["出租方姓名", "E2E Example Owner"],
      ["出租方联系方式", "owner@example.com"],
      ["出租方送达地址", "1 Example Road, Sydney NSW 2000"],
      ["租客姓名（每行一名）", "E2E Example Tenant"],
      ["租客联系方式", "tenant@example.com"],
      ["起租日期", start],
      ["结束日期", end],
      ["拟定押金（AUD）", String(agreedRent * 4)],
      ["约定最多居住人数", "1"],
      ["首期租金付款日期", start],
      ["租金付款日", "每周一"],
    ])
      await page.getByLabel(label, { exact: true }).fill(value);
    await choose(page, page, "租期类型", "固定租期");
    await page.getByText("出租方中介（如适用）", { exact: true }).click();
    for (const [label, value] of [
      ["出租方中介姓名 / 公司", "E2E Agency"],
      [
        "出租方中介联系方式（须含电话）",
        "agent@example.com; Phone: 0400000001",
      ],
      ["出租方中介送达地址", "2 Example Road"],
      ["出租方中介区域（Suburb）", "Rhodes"],
      ["出租方中介 State", "NSW"],
      ["出租方中介邮编", "2138"],
    ])
      await page.getByLabel(label, { exact: true }).fill(value);
    await page
      .getByRole("button", { name: "核对并填入合同", exact: true })
      .click();
    const confirm = page.getByRole("dialog", {
      name: "确认保存租约草稿",
      exact: true,
    });
    expect(
      (await (await request.get(`${root}/lease-drafts`)).json()).items,
    ).toHaveLength(0);
    await expect(
      confirm.getByRole("button", { name: "确认保存未签署草稿", exact: true }),
    ).toBeDisabled();
    await confirm.getByRole("checkbox").check();
    await confirm
      .getByRole("button", { name: "确认保存未签署草稿", exact: true })
      .click();
    const preview = page.getByRole("dialog", {
      name: "合同预览 · v1",
      exact: true,
    });
    await expect(preview.locator("iframe")).toHaveAttribute("src", /^blob:/);
    await preview
      .getByRole("button", { name: "返回填写", exact: true })
      .click();
    const pending = page.waitForEvent("download");
    await page
      .getByRole("link", { name: "下载已保存 v1 PDF", exact: true })
      .click();
    const file = info.outputPath("unsigned-lease-v1.pdf");
    await (await pending).saveAs(file);
    expect((await readFile(file)).subarray(0, 4).toString()).toBe("%PDF");
    const pdf = JSON.parse(
      execFileSync(
        process.env.FULL_JOURNEY_PYTHON!,
        [
          "-c",
          "import json,sys; from pypdf import PdfReader; r=PdfReader(sys.argv[1]); f=r.get_fields(); print(json.dumps({'values':{k:str(v.get('/V','')) for k,v in f.items()}, 'signed':any(v.get('/V') for v in f.values() if v.get('/FT')=='/Sig')}))",
          file,
        ],
        { encoding: "utf8" },
      ),
    );
    // Assert the pinned official template's actual field identities, including
    // the separate landlord-agent and tenant-representative sections.
    expect(pdf.values).toMatchObject({
      "Text field 1.4": "E2E Example Owner",
      "Text field 2.6": "E2E Example Tenant",
      "Text field 2.15": "E2E Agency",
      "Text field 2.16": "2 Example Road",
      "Text field 2.17": "Rhodes",
      "Text field 2.18": "NSW",
      "Text field 2.19": "2138",
      "Text field 2.20": "agent@example.com; Phone: 0400000001",
      "Text field 2.21": "",
      "Text field 3.13": String(agreedRent),
    });
    expect(pdf.signed).toBe(false);
    await info.attach("未签署合同 PDF", {
      path: file,
      contentType: "application/pdf",
    });
    expect((await state()).selection.contract_ready).toBe(false);
  });

  await test.step("05B 上传测试合同复核，比较合同租金与跟进记录的差异", async () => {
    await page.getByRole("tab", { name: "上传合同复核", exact: true }).click();
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
    const contractRent = agreedRent + 10;
    await page.locator("input[type=file]").setInputFiles({
      name: "e2e-example-lease.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        `Address: ${address}\nLandlord: E2E Example Owner\nTenant: E2E Example Tenant\nRent: AUD ${contractRent} per week whole property\nBond: AUD ${contractRent * 4}\nStart date: ${start}\nEnd date: ${end}\n`,
      ),
    });
    await page
      .getByRole("checkbox", {
        name: "我确认有权提交此合同用于本次复核。",
        exact: true,
      })
      .check();
    await page.getByRole("button", { name: "上传并复核", exact: true }).click();
    await expect(page.getByTestId("real-contract-comparison")).toContainText(
      "E2E synthetic agent reply",
    );
    const comparison = page.getByTestId("comparison-recorded_rent");
    await expect(comparison).toContainText("需要核对差异");
    await expect(comparison).toContainText(String(agreedRent));
    await expect(comparison).toContainText(String(contractRent));
    expect((await state()).reviews).toHaveLength(1);
    await page.reload();
    await expect(comparison).toContainText("需要核对差异");
  });

  await test.step("06 租约资料先预览，人工确认实际资料后接入租后页面", async () => {
    await page.getByRole("menuitem", { name: "租后服务", exact: true }).click();
    expect((await living()).profile.address).toBe("");
    await page
      .getByRole("button", { name: "查看租约来源", exact: true })
      .click();
    const modal = page.getByRole("dialog", {
      name: "核对租约来源",
      exact: true,
    });
    await expect(modal).toContainText(address);
    expect((await living()).profile.address).toBe("");
    await modal
      .getByRole("checkbox", {
        name: "我确认这些资料对应我的实际租约。",
        exact: true,
      })
      .check();
    await modal
      .getByRole("button", { name: "接入所选资料", exact: true })
      .click();
    await page
      .getByRole("button", { name: "确认接入租约资料", exact: true })
      .click();
    await expect(modal).toHaveCount(0);
    expect((await living()).profile).toMatchObject({
      address,
      agent_name: "E2E Agency",
      agent_email: "agent@example.com",
      lease_start_date: start,
      lease_end_date: end,
    });
  });

  await test.step("07 查看供应商详情并保存水电选择；搬运与清洁分组展示", async () => {
    await page.getByRole("tab", { name: "水电气网", exact: true }).click();
    const directory = await (
      await request.get("/api/v1/living-providers")
    ).json();
    const power = directory.providers.find(
      (p: { name: string }) => p.name === "AGL",
    );
    await page.locator(`[data-provider-id="${power.id}"]`).click();
    const details = page.getByRole("dialog", {
      name: "AGL · 供应商详情",
      exact: true,
    });
    await expect(details).toBeVisible();
    await screenshot("03-utility-details");
    await details
      .getByRole("button", { name: "关闭详情", exact: true })
      .click();
    await choose(page, page, "电力供应商", "AGL");
    await page
      .getByRole("button", { name: "保存供应商选择", exact: true })
      .click();
    expect((await living()).profile.utilities.electricity).toBeNull();
    await page
      .getByRole("button", { name: "确认保存选择", exact: true })
      .click();
    await expect
      .poll(async () => (await living()).profile.utilities.electricity)
      .toBe(power.id);
    await page.getByRole("tab", { name: "搬运与清洁", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "搬运公司", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "清洁公司", exact: true }),
    ).toBeVisible();
    const mover = directory.providers.find((p: { categories: string[] }) =>
      p.categories.includes("removalist"),
    );
    await page.locator(`[data-provider-id="${mover.id}"]`).click();
    const modal = page.getByRole("dialog", {
      name: `${mover.name} · 服务商详情`,
      exact: true,
    });
    await expect(
      modal.getByRole("link", { name: "公司网站", exact: true }),
    ).toHaveAttribute("href", mover.website);
    await expect(modal).not.toContainText("路线");
    await modal
      .getByRole("button", { name: "记录报价或预约", exact: true })
      .click();
    const form = page.getByRole("dialog");
    await form.getByLabel("收到的报价（AUD）", { exact: true }).fill("250");
    await form.getByLabel("服务日期", { exact: true }).fill(start);
    await form
      .getByLabel("服务备注", { exact: true })
      .fill("测试电话报价，尚未向商家预约。");
    await form
      .getByRole("checkbox", {
        name: "我确认仅保存记录，不会向服务商提交预约。",
        exact: true,
      })
      .check();
    await form
      .getByRole("button", { name: "确认保存服务记录", exact: true })
      .click();
    await expect(form).toHaveCount(0);
    expect((await living()).bookings[0]).toMatchObject({
      provider_id: mover.id,
      quote_amount: 250,
      status: "considering",
    });
  });

  await test.step("08 AI 润色报修邮件，用户编辑确认保存，记录后续并在手机恢复", async () => {
    await page.getByRole("tab", { name: "日常报修", exact: true }).click();
    await page
      .getByLabel("报修邮件收件人姓名", { exact: true })
      .fill("E2E Agency");
    await page
      .getByLabel("问题描述", { exact: true })
      .fill("厨房水龙头关闭后仍滴水，请安排维修。");
    await page
      .getByRole("button", { name: "AI 润色邮件", exact: true })
      .click();
    await expect(
      page.getByLabel("润色邮件正文", { exact: true }),
    ).toContainText("Dear E2E Agency");
    expect((await living()).repairs).toHaveLength(0);
    await page
      .getByLabel("润色邮件主题", { exact: true })
      .fill("E2E kitchen tap repair");
    await page
      .getByLabel("润色邮件正文", { exact: true })
      .fill(
        "Dear E2E Agency,\n\nThe kitchen tap is leaking. Please arrange a repair.\n\nThank you.",
      );
    await page
      .getByRole("button", { name: "保存润色报修草稿", exact: true })
      .click();
    await page
      .getByRole("button", { name: "确认保存报修草稿", exact: true })
      .click();
    const card = page.locator(".living-repair-card");
    await expect(card).toContainText("E2E kitchen tap repair");
    await card.getByRole("button", { name: "记录后续", exact: true }).click();
    const modal = page.getByRole("dialog", {
      name: "记录报修后续",
      exact: true,
    });
    await modal
      .getByLabel("对方回复或我的记录", { exact: true })
      .fill("测试记录：已联系中介，等待安排维修。");
    await modal
      .getByRole("button", { name: "核对并保存后续", exact: true })
      .click();
    await page
      .getByRole("button", { name: "确认保存报修后续", exact: true })
      .click();
    await expect(modal).toHaveCount(0);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await expect(card).toContainText("测试记录：已联系中介，等待安排维修。");
    await expect(card).toContainText("草稿已准备 · 尚未发送");
    const saved = await living();
    expect(saved.repairs).toHaveLength(1);
    expect(saved.repairs[0].email).toMatchObject({
      to: "agent@example.com",
      subject: "E2E kitchen tap repair",
      delivery_status: "prepared_not_sent",
    });
    expect(saved.bookings).toHaveLength(1);
    expect(saved.profile.address).toBe(address);
    expect((await state()).selection.listing_snapshot.address).toBe(address);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await screenshot("04-aftercare-mobile");
    await info.attach("final-state", {
      body: JSON.stringify({ case: await state(), living: saved }, null, 2),
      contentType: "application/json",
    });
  });

  await test.step("09 从已复核地址创建退租案件，生成计划并保存任务进度", async () => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole("tab", { name: "退租与押金", exact: true }).click();
    // The unsigned draft and review must not silently create a confirmed tenancy.
    expect((await state()).aftercare_case_id).toBeNull();
    await page
      .getByRole("button", {
        name: "从最近合同复核预填地址与来源",
        exact: true,
      })
      .click();
    await expect(page.getByLabel("租约地址", { exact: true })).toHaveValue(
      address,
    );
    for (const field of ["有地毯", "有室外区域", "带家具"])
      await choose(page, page, field, "否");
    await page.getByRole("button", { name: "添加房间", exact: true }).click();
    await page.getByLabel("房间名称", { exact: true }).fill("E2E Bedroom");
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
    await expect(
      page.getByText("已确认租约资料", { exact: true }),
    ).toBeVisible();
    await page.getByLabel("计划退租日期", { exact: true }).fill(end);
    await page
      .getByRole("button", { name: "生成并确认计划", exact: true })
      .click();
    await page.getByRole("button", { name: "确认计划", exact: true }).click();
    await page
      .getByRole("button", { name: "编辑任务", exact: true })
      .first()
      .click();
    const modal = page.getByRole("dialog", {
      name: "编辑任务与证据",
      exact: true,
    });
    await choose(page, modal, "任务状态", "已完成");
    await modal.getByRole("button", { name: "保存任务", exact: true }).click();
    await expect(modal).toHaveCount(0);
    const m4 = (await state()).aftercare_case_id;
    const saved = await (
      await request.get(`/api/v1/aftercare/cases/${m4}`)
    ).json();
    expect(saved.tenancy.address).toBe(address);
    expect(saved.plan.move_out_date).toBe(end);
    expect(
      saved.plan.tasks.some(
        (task: { status: string }) => task.status === "done",
      ),
    ).toBe(true);
    await screenshot("05-moveout-plan");
  });

  await test.step("10 建立押金跟进、生成未发送草稿，明确确认结果后关闭", async () => {
    await page.getByRole("tab", { name: "押金跟进", exact: true }).click();
    await page
      .getByLabel("押金记录编号（可暂不填写）", { exact: true })
      .fill("E2E-BOND-001");
    await page
      .getByRole("button", { name: "建立押金跟进", exact: true })
      .click();
    await page
      .getByRole("button", { name: "确认事实并激活跟进", exact: true })
      .click();
    await page
      .getByLabel("租客报告的事实", { exact: true })
      .fill("E2E 测试记录：钥匙已交还，等待押金结果。");
    await page.getByRole("button", { name: "确认并记录", exact: true }).click();
    await page
      .getByRole("button", { name: "准备跟进草稿", exact: true })
      .click();
    await expect(
      page.getByText("跟进草稿 · 尚未发送", { exact: true }),
    ).toBeVisible();
    await page
      .getByLabel("你确认的结果或撤回原因", { exact: true })
      .fill("E2E 测试结果：用户确认押金已退回，关闭本次跟进。");
    await page
      .getByRole("button", { name: "确认结果并关闭跟进", exact: true })
      .click();
    await page
      .getByRole("button", { name: "确认结果并关闭", exact: true })
      .click();
    await expect(page.getByText("已确认结果", { exact: true })).toBeVisible();
    await page.reload();
    await page.getByRole("tab", { name: "押金跟进", exact: true }).click();
    await expect(page.getByText("已确认结果", { exact: true })).toBeVisible();
    const finalCase = await state();
    const aftercare = await (
      await request.get(
        `/api/v1/aftercare/cases/${finalCase.aftercare_case_id}`,
      )
    ).json();
    expect(aftercare.bond.state).toBe("Resolved");
    expect(aftercare.bond.history).toHaveLength(1);
    expect(aftercare.bond.drafts).toHaveLength(1);
    const finalLiving = await living();
    expect(finalLiving.profile.address).toBe(address);
    expect(finalLiving.repairs).toHaveLength(1);
    expect(finalLiving.bookings).toHaveLength(1);
    await info.attach("completed-journey-state", {
      body: JSON.stringify(
        { case: finalCase, living: finalLiving, aftercare },
        null,
        2,
      ),
      contentType: "application/json",
    });
    await screenshot("06-bond-completed");
    expect(errors).toEqual([]);
  });
});
