import { test, expect, type APIRequestContext } from "@playwright/test";

async function seed(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  await request.post(root + "/profile-confirmations", {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  const run = await (
    await request.post(root + "/evaluations", {
      data: { request_id: "eval", confirmation_version: 1 },
    })
  ).json();
  const row = run.report.pending_confirmation[0];
  const response = await request.post(root + "/selections", {
    data: {
      request_id: "select",
      run_id: run.run_id,
      listing_id: row.listing_id,
      confirmed: true,
    },
  });
  expect(response.status()).toBe(200);
  return { c, root, row };
}

test("candidate facts sync between search/chat and the real contract compares frozen sources", async ({
  page,
  request,
}) => {
  const { c, root, row } = await seed(request);
  await page.goto(`/cases/${c.case_id}/recommendations`);
  const next = page.getByTestId("candidate-next");
  await expect(next).toContainText(row.address);
  await next
    .getByRole("button", { name: "准备看房与询问", exact: true })
    .click();
  const drawer = page.getByRole("dialog", { name: "房源跟进", exact: true });
  await expect(
    drawer.getByText("目前是否仍可租？何时可以看房？", { exact: true }),
  ).toBeVisible();
  await drawer
    .getByRole("spinbutton", { name: "回复中的租金（AUD）", exact: true })
    .fill("600");
  await drawer.getByLabel("租金周期", { exact: true }).click();
  await page.getByRole("option", { name: "每周", exact: true }).click();
  await drawer.getByLabel("租金计价对象", { exact: true }).click();
  await page.getByRole("option", { name: "整套", exact: true }).click();
  await drawer.getByLabel("信息来源", { exact: true }).fill("10月22日中介邮件");
  await drawer
    .getByLabel("看房安排", { exact: true })
    .fill("周六 11:30，尚未预约");
  await drawer
    .getByRole("button", { name: "确认保存跟进信息", exact: true })
    .click();
  await expect(
    drawer.getByText("已保存 v1 · 用户记录", { exact: true }),
  ).toBeVisible();
  const state = await (await request.get(root)).json();
  expect(state.selection.contract_ready).toBe(false);
  expect(state.selection.listing_snapshot.rent_scope).toBeNull();
  await drawer.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("menuitem", { name: "AI租房助手", exact: true }).click();
  await page
    .getByTestId("candidate-next")
    .getByRole("button", { name: "准备看房与询问", exact: true })
    .click();
  await expect(
    drawer.getByRole("spinbutton", {
      name: "回复中的租金（AUD）",
      exact: true,
    }),
  ).toHaveValue("600");
  await expect(drawer.getByLabel("信息来源", { exact: true })).toHaveValue(
    "10月22日中介邮件",
  );
  await drawer
    .getByRole("button", { name: "已有合同，开始复核", exact: true })
    .click();
  await expect(
    page.getByText("可以直接复核已有合同", { exact: true }),
  ).toBeVisible();
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
  const contract = `Address: ${row.address}\nLandlord: Example Owner\nTenant: Example Tenant\nRent: AUD 620 per week whole property\nBond: AUD 2480\nStart date: 2026-11-01\nEnd date: 2027-11-01\n`;
  await page
    .locator("input[type=file]")
    .setInputFiles({
      name: "actual-lease.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(contract),
    });
  await page
    .getByRole("checkbox", {
      name: "我确认有权提交此合同用于本次复核。",
      exact: true,
    })
    .check();
  await page.getByRole("button", { name: "上传并复核", exact: true }).click();
  const comparison = page.getByTestId("real-contract-comparison");
  await expect(comparison).toContainText("10月22日中介邮件");
  await expect(page.getByTestId("comparison-recorded_rent")).toContainText(
    "需要核对差异",
  );
  await expect(page.getByTestId("comparison-recorded_rent")).toContainText(
    "600",
  );
  await expect(page.getByTestId("comparison-recorded_rent")).toContainText(
    "620",
  );
  // Contract 620/week vs the 300/week advert with no stated charging basis: shown as a possible gap.
  await expect(page.getByTestId("comparison-advertised_rent")).toContainText(
    "金额不同，口径待确认",
  );
  await page.reload();
  await expect(comparison).toContainText(row.address);
});

test("chat follow-up intent routes to the saved candidate without inventing verification", async ({
  page,
  request,
}) => {
  const { c, root, row } = await seed(request);
  const conversation = await (
    await request.post(root + "/assistant/conversations", { data: {} })
  ).json();
  const r = await request.post(
    root + `/assistant/conversations/${conversation.conversation_id}/messages`,
    {
      data: {
        request_id: "follow",
        expected_revision: 0,
        message: "就这套，下一步问中介什么？",
        allow_external_ai: true,
      },
    },
  );
  expect(r.status()).toBe(200);
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(page.getByText(new RegExp("围绕你已保存的"))).toContainText(
    row.address,
  );
  await page
    .getByRole("button", { name: "记录回复与看房安排", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "房源跟进", exact: true }),
  ).toBeVisible();
  expect(
    (await (await request.get(root)).json()).selection.requires_verification,
  ).toBe(true);
});

test("mobile follow-up fits the viewport and only saves after an explicit action", async ({
  page,
  request,
}) => {
  const { c, root } = await seed(request);
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByTestId("candidate-next")
    .getByRole("button", { name: "准备看房与询问", exact: true })
    .click();
  const drawer = page.getByRole("dialog", { name: "房源跟进", exact: true });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByLabel("信息来源", { exact: true })).toBeEnabled();
  await drawer
    .getByLabel("信息来源", { exact: true })
    .fill("手机上未保存的记录");
  await expect(async () => {
    const rect = await drawer.boundingBox();
    expect(rect!.width).toBeLessThanOrEqual(360);
    expect(rect!.x).toBeGreaterThanOrEqual(0);
  }).toPass();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await drawer.getByRole("button", { name: "关闭", exact: true }).click();
  expect(
    (await (await request.get(root + "/candidate-followup")).json()).version,
  ).toBe(0);
});
