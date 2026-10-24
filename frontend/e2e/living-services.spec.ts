import { expect, test } from "@playwright/test";

test("living profile and utility choices require confirmation and restore after reload", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const directory = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const energy = directory.providers.find((p: { categories: string[] }) =>
    p.categories.includes("electricity"),
  );
  expect(energy).toBeTruthy();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=utilities`);
  await expect(
    page.getByRole("heading", { name: "租后生活服务", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "编辑住处与联系人", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("textbox", { name: "居住地址", exact: true }),
  ).toBeEmpty();
  await dialog
    .getByRole("textbox", { name: "居住地址", exact: true })
    .fill("Test unit, Sydney NSW");
  await dialog
    .getByRole("textbox", { name: "中介或房东姓名", exact: true })
    .fill("Test contact");
  await dialog
    .getByRole("textbox", { name: "联系邮箱", exact: true })
    .fill("agent@example.com");
  await expect(
    dialog.getByRole("button", { name: "确认保存资料", exact: true }),
  ).toBeDisabled();
  await dialog
    .getByRole("checkbox", {
      name: "我确认保存这些住处与联系人资料。",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("button", { name: "确认保存资料", exact: true })
    .click();
  await expect(
    page.getByText("agent@example.com", { exact: true }),
  ).toBeVisible();
  await page.getByRole("combobox", { name: "电力供应商", exact: true }).click();
  await page
    .locator(".ant-select-dropdown .ant-select-item-option-content")
    .getByText(energy.name, { exact: true })
    .click();
  await page
    .getByRole("button", { name: "保存供应商选择", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(energy.name);
  const before = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(before.profile.utilities.electricity).toBeNull();
  await page.getByRole("button", { name: "确认保存选择", exact: true }).click();
  await page.reload();
  await expect(
    page.getByText(energy.name, { exact: true }).first(),
  ).toBeVisible();
  const saved = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(saved.profile.utilities.electricity).toBe(energy.id);
  expect(saved.profile.agent_email).toBe("agent@example.com");
  await page.screenshot({
    path: "/tmp/living-services-utilities-desktop.png",
    fullPage: true,
  });
});

test("repairs preserve an unsent email draft and status without sending", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=repairs`);
  await expect(
    page.getByText(
      "未填写邮箱，可先保存报修草稿或拨打已记录电话；补充邮箱后可在邮件客户端打开。",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "报修标题", exact: true })
    .fill("厨房水龙头漏水");
  await page
    .getByRole("textbox", { name: "问题描述", exact: true })
    .fill("今天发现关闭后仍持续滴水，尚未联系维修人员。");
  await page.getByRole("textbox", { name: "位置", exact: true }).fill("厨房");
  await page.getByRole("button", { name: "准备报修邮件", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("只保存邮件草稿");
  await page
    .getByRole("button", { name: "确认保存报修草稿", exact: true })
    .click();
  await expect(
    page.getByText("草稿已准备 · 尚未发送", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "在邮箱中打开", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "编辑住处与联系人", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("textbox", { name: "联系邮箱", exact: true })
    .fill("agent@example.com");
  await dialog
    .getByRole("textbox", { name: "联系电话", exact: true })
    .fill("0400000000");
  await dialog
    .getByRole("checkbox", {
      name: "我确认保存这些住处与联系人资料。",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("button", { name: "确认保存资料", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "拨打联系人电话", exact: true }),
  ).toHaveAttribute("href", "tel:0400000000");
  await expect(
    page.getByRole("link", { name: "在邮箱中打开", exact: true }),
  ).toHaveAttribute("href", /^mailto:agent%40example\.com\?subject=/);
  const saved = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(saved.repairs).toHaveLength(1);
  expect(saved.repairs[0].email.delivery_status).toBe("prepared_not_sent");
  expect(saved.repairs[0].email.to).toBe("");
  await page.reload();
  await expect(
    page.getByText("厨房水龙头漏水", { exact: true }).first(),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("provider cards use directory sources and save quote records on mobile", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const directory = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const provider = directory.providers.find(
    (p: { categories: string[] }) =>
      p.categories.includes("removalist") || p.categories.includes("cleaner"),
  );
  expect(provider).toBeTruthy();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=services`);
  const card = page.locator(`[data-provider-id="${provider.id}"]`);
  await expect(
    card.getByRole("link", { name: "公司网站", exact: true }),
  ).toHaveAttribute("href", provider.website);
  await expect(
    card.getByRole("link", { name: "来源", exact: true }),
  ).toHaveAttribute("href", provider.source_url);
  await card
    .getByRole("button", { name: "记录报价或预约", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("spinbutton", { name: "收到的报价（AUD）", exact: true })
    .fill("250");
  await dialog
    .getByRole("textbox", { name: "服务日期", exact: true })
    .fill("2026-12-15");
  await dialog
    .getByRole("textbox", { name: "服务备注", exact: true })
    .fill("仅记录电话报价，尚未确认预约。");
  await dialog
    .getByRole("checkbox", {
      name: "我确认仅保存记录，不会向服务商提交预约。",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("button", { name: "确认保存服务记录", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("AUD 250", { exact: true })).toBeVisible();
  const saved = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(saved.bookings[0].provider_id).toBe(provider.id);
  expect(saved.bookings[0].quote_amount).toBe(250);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/living-services-mobile.png",
    fullPage: true,
  });
  await page.getByRole("tab", { name: "退租与押金", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "租约地址", exact: true }),
  ).toBeEmpty();
  await expect(page.getByText("synthetic://", { exact: false })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "添加房间", exact: true }),
  ).toBeVisible();
});

test("real tenancy confirmation sends no sample rooms, inventory or evidence", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const payloads: Record<string, unknown>[] = [];
  await page.route("**/api/v1/aftercare/commands", async (route) => {
    payloads.push(route.request().postDataJSON());
    await route.continue();
  });
  await page.goto(`/cases/${c.case_id}/aftercare?tab=moveout`);
  const address = page.getByRole("textbox", { name: "租约地址", exact: true });
  await expect(address).toBeEmpty();
  await expect(
    page.getByRole("textbox", { name: "房间名称", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("textbox", { name: "家具名称", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("textbox", { name: "资料来源引用", exact: true }),
  ).toHaveCount(0);
  await address.fill("User-confirmed test tenancy, Sydney NSW");
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
  expect(payloads).toHaveLength(1);
  expect(payloads[0]).toMatchObject({
    operation: "create",
    payload: {
      tenancy: {
        address: "User-confirmed test tenancy, Sydney NSW",
        source_ref: "user-entered:tenant-confirmation",
        confirmed: true,
        rooms: null,
        inventory: null,
        carpeted: null,
        outdoor: null,
        furnished: null,
        inventory_confirmed: false,
        baseline_evidence_refs: [],
      },
      evidence: [],
    },
  });
  expect(JSON.stringify(payloads[0])).not.toContain("synthetic://");
  await page.getByRole("tab", { name: "押金跟进", exact: true }).click();
  await expect(
    page.getByLabel("押金记录编号（可暂不填写）", { exact: true }),
  ).toBeEmpty();
});

test("utility edits retain their base version across refresh and cannot erase a concurrent gas choice", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const directory = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const provider = directory.providers.find(
    (p: { categories: string[] }) =>
      p.categories.includes("electricity") && p.categories.includes("gas"),
  );
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  await page.goto(`/cases/${c.case_id}/aftercare?tab=utilities`);
  const chooseElectricity = async () => {
    await page
      .getByRole("combobox", { name: "电力供应商", exact: true })
      .click();
    await page
      .locator(".ant-select-dropdown .ant-select-item-option-content")
      .getByText(provider.name, { exact: true })
      .click();
  };
  await chooseElectricity();
  const initial = await (await request.get(root)).json();
  const changed = await request.post(`${root}/profile`, {
    data: {
      request_id: `test-${crypto.randomUUID()}`,
      expected_version: initial.version,
      confirmed: true,
      values: {
        ...initial.profile,
        utilities: { ...initial.profile.utilities, gas: provider.id },
      },
    },
  });
  expect(changed.ok()).toBe(true);
  await page.getByRole("button", { name: "读取最新资料", exact: true }).click();
  await expect(
    page.getByText(
      "资料已有新版本，你未保存的选择仍保留。恢复最新选择后再修改并保存。",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "保存供应商选择", exact: true })
    .click();
  await page.getByRole("button", { name: "确认保存选择", exact: true }).click();
  await expect(
    page.getByText("资料已变化，请重新读取后确认。", { exact: true }),
  ).toBeVisible();
  const protectedRecord = await (await request.get(root)).json();
  expect(protectedRecord.profile.utilities).toMatchObject({
    electricity: null,
    gas: provider.id,
  });
  await page.getByRole("button", { name: "恢复最新选择", exact: true }).click();
  await chooseElectricity();
  await page
    .getByRole("button", { name: "保存供应商选择", exact: true })
    .click();
  await page.getByRole("button", { name: "确认保存选择", exact: true }).click();
  await expect(
    page.getByText("资料已变化，请重新读取后确认。", { exact: true }),
  ).toHaveCount(0);
  const saved = await (await request.get(root)).json();
  expect(saved.profile.utilities).toMatchObject({
    electricity: provider.id,
    gas: provider.id,
  });
});

test("a real uploaded PNG remains downloadable after reload and is marked unverified", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  await page.goto(`/cases/${c.case_id}/aftercare?tab=repairs`);
  const png = Buffer.from(
    await page.evaluate(() => {
      const canvas = document.createElement("canvas");
      canvas.width = 1;
      canvas.height = 1;
      const context = canvas.getContext("2d")!;
      context.fillStyle = "#174EA6";
      context.fillRect(0, 0, 1, 1);
      return canvas.toDataURL("image/png").split(",")[1];
    }),
    "base64",
  );
  const files = page.getByRole("region", {
    name: "照片与收据附件",
    exact: true,
  });
  await expect(
    files.getByRole("button", { name: "上传并保存附件", exact: true }),
  ).toBeDisabled();
  await files.locator('input[type="file"]').setInputFiles({
    name: "报修照片.png",
    mimeType: "image/png",
    buffer: png,
  });
  expect(
    (await (await request.get(`${root}/attachments`)).json()).items,
  ).toHaveLength(0);
  await files
    .getByRole("button", { name: "上传并保存附件", exact: true })
    .click();
  await expect(
    files.getByRole("link", { name: "下载 报修照片.png", exact: true }),
  ).toBeVisible();
  await expect(
    files.getByText("用户上传 · 未核实", { exact: true }),
  ).toBeVisible();
  await page.reload();
  const link = files.getByRole("link", {
    name: "下载 报修照片.png",
    exact: true,
  });
  await expect(link).toBeVisible();
  const download = await request.get((await link.getAttribute("href"))!);
  expect(download.ok()).toBe(true);
  expect(download.headers()["content-type"]).toContain("image/png");
  expect(await download.body()).toEqual(png);
  const record = await (await request.get(root)).json();
  expect(record.version).toBe(0);
});
