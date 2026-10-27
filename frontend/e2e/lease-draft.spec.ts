import { test, expect, type APIRequestContext } from "@playwright/test";
import { readFile } from "node:fs/promises";
async function seed(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json(),
    root = `/api/v1/cases/${c.case_id}`;
  await request.post(root + "/profile-confirmations", {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  const run = await (
    await request.post(root + "/evaluations", {
      data: { request_id: "run", confirmation_version: 1 },
    })
  ).json();
  const row = run.report.pending_confirmation[0];
  expect(
    (
      await request.post(root + "/selections", {
        data: {
          request_id: "select",
          run_id: run.run_id,
          listing_id: row.listing_id,
          confirmed: true,
        },
      })
    ).ok(),
  ).toBe(true);
  return { c, root, row };
}
test("official lease draft requires confirmation, saves versions, reloads and downloads an unsigned PDF", async ({
  page,
  request,
}, info) => {
  const { c, root, row } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await expect(
    page.getByRole("heading", { name: "合同助手", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("房屋地址", { exact: true })).toHaveValue(
    row.address,
  );
  await expect(page.getByLabel("拟定租金（AUD）", { exact: true })).toHaveValue(
    "",
  );
  await expect(
    page.getByRole("heading", { name: "直接填写合同信息", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "租赁双方", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "合同要点描述", exact: true }),
  ).not.toBeVisible();
  await page.getByLabel("租约适用范围", { exact: true }).click();
  await page
    .getByRole("option", { name: "新州普通整租住宅", exact: true })
    .click();
  for (const [label, value] of [
    ["出租方姓名", "Example Owner"],
    ["出租方联系方式", "owner@example.com"],
    ["出租方送达地址", "1 Example Road, Sydney NSW 2000"],
    ["租客姓名（每行一名）", "张三"],
    ["租客联系方式", "tenant@example.com"],
    ["起租日期", "2026-11-01"],
    ["结束日期", "2027-11-01"],
    ["拟定租金（AUD）", "600"],
    ["拟定押金（AUD）", "2400"],
    ["约定最多居住人数", "2"],
    ["首期租金付款日期", "2026-11-01"],
    ["租金付款日", "每周一"],
  ])
    await page.getByLabel(label, { exact: true }).fill(value);
  await page.getByLabel("租期类型", { exact: true }).click();
  await page.getByRole("option", { name: "固定租期", exact: true }).click();
  await page.getByLabel("租金周期", { exact: true }).click();
  await page.getByRole("option", { name: "每周", exact: true }).click();
  await page
    .getByRole("button", { name: "核对并填入合同", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "确认保存租约草稿",
    exact: true,
  });
  await expect(modal).toContainText("张三");
  expect(
    (await (await request.get(root + "/lease-drafts")).json()).items,
  ).toHaveLength(0);
  await expect(
    modal.getByRole("button", { name: "确认保存未签署草稿", exact: true }),
  ).toBeDisabled();
  await modal.getByRole("checkbox").check();
  await modal
    .getByRole("button", { name: "确认保存未签署草稿", exact: true })
    .click();
  const preview = page.getByRole("dialog", {
    name: "合同预览 · v1",
    exact: true,
  });
  await expect(preview).toBeVisible();
  await expect(
    preview.locator('iframe[title="已填写的合同草稿 v1"]'),
  ).toHaveAttribute("src", /^blob:/);
  await expect(
    preview.getByRole("link", { name: "下载此版本 PDF", exact: true }),
  ).toHaveAttribute("href", /\/pdf\?version=1$/);
  await preview.getByRole("button", { name: "返回填写", exact: true }).click();
  const link = page.getByRole("link", {
    name: "下载已保存 v1 PDF",
    exact: true,
  });
  await expect(link).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await link.click();
  const download = await downloadPromise;
  const file = info.outputPath("lease-v1.pdf");
  await download.saveAs(file);
  expect((await readFile(file)).subarray(0, 4).toString()).toBe("%PDF");
  const state = await (await request.get(root)).json();
  expect(state.selection.contract_ready).toBe(false);
  expect(state.reviews).toHaveLength(0);
  await page.reload();
  await expect(page.getByLabel("拟定租金（AUD）", { exact: true })).toHaveValue(
    /^600(?:\.00)?$/,
  );
  await page.getByLabel("拟定租金（AUD）", { exact: true }).fill("610");
  await expect(
    page.getByText("表单有未保存修改，预览和下载仍为已保存的 v1。", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "预览已保存 v1 合同", exact: true })
    .click();
  await expect(
    preview.locator('iframe[title="已填写的合同草稿 v1"]'),
  ).toHaveAttribute("src", /^blob:/);
  expect(
    (await (await request.get(root + "/lease-drafts")).json()).items[0].version,
  ).toBe(1);
  await preview.getByRole("button", { name: "返回填写", exact: true }).click();
  await page
    .getByRole("button", { name: "核对并填入合同", exact: true })
    .click();
  await modal.getByRole("checkbox").check();
  await modal
    .getByRole("button", { name: "确认保存未签署草稿", exact: true })
    .click();
  const v2Preview = page.getByRole("dialog", {
    name: "合同预览 · v2",
    exact: true,
  });
  await expect(
    v2Preview.locator('iframe[title="已填写的合同草稿 v2"]'),
  ).toHaveAttribute("src", /^blob:/);
  await v2Preview
    .getByRole("button", { name: "返回填写", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "下载已保存 v2 PDF", exact: true }),
  ).toBeVisible();
  let releaseVersion!: () => void;
  const versionGate = new Promise<void>((resolve) => {
    releaseVersion = resolve;
  });
  let markRequested!: () => void;
  const requested = new Promise<void>((resolve) => {
    markRequested = resolve;
  });
  await page.route(
    /\/lease-drafts\/lease-draft-.*\?version=1$/,
    async (route) => {
      markRequested();
      await versionGate;
      await route.continue();
    },
  );
  await page.getByRole("combobox", { name: "草稿版本", exact: true }).click();
  await page.getByRole("option", { name: "草稿 1 · v1", exact: true }).click();
  await requested;
  try {
    await expect(
      page.getByRole("button", { name: "新建当前候选草稿", exact: true }),
    ).toBeDisabled();
    await expect(
      page.getByLabel("拟定租金（AUD）", { exact: true }),
    ).toBeDisabled();
  } finally {
    releaseVersion();
  }
  await expect(
    page.getByText("正在查看历史版本", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("拟定租金（AUD）", { exact: true })).toHaveValue(
    /^600(?:\.00)?$/,
  );
  await page
    .getByRole("button", { name: "新建当前候选草稿", exact: true })
    .click();
  await expect(page.getByLabel("房屋地址", { exact: true })).toHaveValue(
    row.address,
  );
  await expect(page.getByLabel("拟定租金（AUD）", { exact: true })).toHaveValue(
    "",
  );
  await page.getByRole("tab", { name: "上传合同复核", exact: true }).click();
  await expect(
    page.getByText("可以直接复核已有合同", { exact: true }),
  ).toBeVisible();
});

test("AI only fills the form after review and never creates a draft automatically", async ({
  page,
  request,
}) => {
  const { c, root } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await page
    .getByRole("button", { name: "AI 辅助填写（可选）", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "合同要点描述", exact: true })
    .fill("整租，每周600，押金2400，租客 Zhang San");
  await expect(
    page.getByRole("button", { name: "AI 整理合同要点", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", {
      name: "同意将这段文字发送至配置的外部 AI，用于本次字段提取。",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "AI 整理合同要点", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "核对 AI 整理的字段",
    exact: true,
  });
  await expect(modal).toContainText("Zhang San");
  await expect(page.getByLabel("拟定租金（AUD）", { exact: true })).toHaveValue(
    "",
  );
  await modal
    .getByRole("button", { name: "将这些字段填入表单", exact: true })
    .click();
  await expect(page.getByLabel("拟定租金（AUD）", { exact: true })).toHaveValue(
    /^600(?:\.00)?$/,
  );
  await expect(
    page.getByLabel("租客姓名（每行一名）", { exact: true }),
  ).toHaveValue("Zhang San");
  expect(
    (await (await request.get(root + "/lease-drafts")).json()).items,
  ).toHaveLength(0);
});

test("saved PDF preview can retry a failed load on mobile without saving another version", async ({
  page,
  request,
}) => {
  const { c, root } = await seed(request);
  const context = await (
    await request.get(root + "/lease-drafts/context")
  ).json();
  const saved = await (
    await request.post(root + "/lease-drafts", {
      data: {
        request_id: "preview-retry",
        context_token: context.context_token,
        expected_version: 0,
        confirmed: true,
        applicability_confirmed: true,
        fields: {
          ...context.defaults,
          rental_mode: "whole_property",
          tenant_names: "Preview Tenant",
          rent_amount: 700,
          rent_period: "week",
        },
      },
    })
  ).json();
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  let allowPdf = false;
  await page.route("**/lease-drafts/*/pdf?version=1", async (route) => {
    if (!allowPdf) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: { message: "PDF 暂时无法读取" } }),
      });
    } else await route.continue();
  });
  await page
    .getByRole("button", { name: "预览已保存 v1 合同", exact: true })
    .click();
  const preview = page.getByRole("dialog", {
    name: "合同预览 · v1",
    exact: true,
  });
  await expect(preview).toContainText("PDF 暂时无法读取");
  allowPdf = true;
  await preview
    .getByRole("button", { name: "重新加载预览", exact: true })
    .click();
  await expect(
    preview.locator('iframe[title="已填写的合同草稿 v1"]'),
  ).toHaveAttribute("src", /^blob:/);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    (
      await (
        await request.get(root + `/lease-drafts/${saved.draft_id}?version=1`)
      ).json()
    ).version,
  ).toBe(1);
  await preview.getByRole("button", { name: "返回填写", exact: true }).click();
  await expect(
    page.getByLabel("租客姓名（每行一名）", { exact: true }),
  ).toHaveValue("Preview Tenant");
});

test("mobile contract assistant fits and missing candidate has a useful next step", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await expect(
    page.getByRole("button", { name: "我的租房需求", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const seeded = await seed(request);
  await page.goto(`/cases/${seeded.c.case_id}/contract?mode=draft`);
  await expect(page.getByLabel("房屋地址", { exact: true })).toBeEnabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "打开导航", exact: true }).click();
  await expect(
    page.getByRole("menuitem", { name: "合同助手", exact: true }),
  ).toBeVisible();
});
