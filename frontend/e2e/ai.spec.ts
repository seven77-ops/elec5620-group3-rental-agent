import { test, expect, type APIRequestContext } from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
const root = resolve(process.cwd(), "..");
const screenshotDir = resolve(root, ".runtime/ai-qa");
mkdirSync(screenshotDir, { recursive: true });
async function seed(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const confirm = await request.post(
    `/api/v1/cases/${c.case_id}/profile-confirmations`,
    {
      data: {
        draft_revision: c.draft.revision,
        fingerprint: c.draft.fingerprint,
        review_token: c.agent1.review_token,
      },
    },
  );
  expect(confirm.ok()).toBeTruthy();
  const e = await (
    await request.post(`/api/v1/cases/${c.case_id}/evaluations`, {
      data: { request_id: crypto.randomUUID(), confirmation_version: 1 },
    })
  ).json();
  return { c, e };
}
async function contract(request: APIRequestContext) {
  const { c, e } = await seed(request);
  await request.post(`/api/v1/cases/${c.case_id}/selections`, {
    data: {
      request_id: crypto.randomUUID(),
      run_id: e.run_id,
      listing_id: "DEMO-006",
      confirmed: true,
    },
  });
  const consent = await (
    await request.post(`/api/v1/cases/${c.case_id}/contract-consents`, {
      data: { confirmed: true },
    })
  ).json();
  const agreement = readFileSync(
    resolve(root, "agent3/data/demo/agreements/selection-demo.txt"),
    "utf8",
  ).replace(
    "Weekly rent: $500 per person",
    "The weekly rent payable is AUD 500 per person.",
  );
  const r = await request.post(`/api/v1/cases/${c.case_id}/contract-reviews`, {
    headers: {
      "Content-Type": "application/octet-stream",
      "X-Consent-Id": consent.consent_id,
      "X-Request-Id": crypto.randomUUID(),
      "X-Filename": "ai-test.txt",
    },
    data: Buffer.from(agreement),
  });
  expect(r.ok()).toBeTruthy();
  return { c, e, review: (await r.json()).review, consent };
}

test("recommendation AI requires separate consent, displays test source and preserves actual ranking", async ({
  page,
  request,
}) => {
  const { c, e } = await seed(request);
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(
    page.getByRole("button", { name: "生成推荐解读", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", {
      name: "我同意将本报告的偏好、评分及证据摘要发送到配置的模型，用于推荐解读。",
      exact: true,
    })
    .check();
  await page.getByRole("button", { name: "生成推荐解读", exact: true }).click();
  await expect(
    page
      .getByText("测试替身解读：请结合已保存评分与证据比较通勤和费用。")
      .first(),
  ).toBeVisible();
  await page.getByText("本次 AI 调用", { exact: true }).click();
  await expect(
    page.getByText("test_stub", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.locator("article.listing-row").first()).toContainText(
    "92.75",
  );
  await expect(page.locator("article.listing-row").first()).toContainText(
    "DEMO-006",
  );
  expect(
    (await (await request.get(`/api/v1/evaluations/${e.run_id}`)).json())
      .report,
  ).toEqual(e.report);
  await page.screenshot({
    path: resolve(screenshotDir, "recommendation-ai-desktop.png"),
  });
  await page.reload();
  await expect(
    page
      .getByText("测试替身解读：请结合已保存评分与证据比较通勤和费用。")
      .first(),
  ).toBeVisible();
});

test("contract AI cites original lines and requires user-selected confirmation before applying new review version", async ({
  page,
  request,
}) => {
  const { c, review } = await contract(request);
  await page.goto(`/cases/${c.case_id}/contract`);
  await expect(
    page.getByRole("button", { name: "AI 辅助分析合同", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", {
      name: "我同意将本合同文本及选房核对资料发送到配置的模型，用于本次 AI 辅助分析。",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "AI 辅助分析合同", exact: true })
    .click();
  await expect(
    page.getByText("AI 候选提取结果", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByText("The weekly rent payable is AUD 500 per person.", {
        exact: true,
      })
      .first(),
  ).toBeVisible();
  expect(
    (
      await (
        await request.get(`/api/v1/contract-reviews/${review.review_id}`)
      ).json()
    ).version,
  ).toBe(1);
  await expect(
    page.getByRole("button", { name: "确认应用所选字段", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", { name: "选择 AI 字段：合同租金", exact: true })
    .check();
  await page
    .getByRole("checkbox", {
      name: "我已逐项核对所选字段的原文，确认应用到当前复核。",
      exact: true,
    })
    .check();
  await page.screenshot({
    path: resolve(screenshotDir, "contract-ai-desktop.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "确认应用所选字段", exact: true })
    .click();
  await expect(page.getByText("复核版本 v2", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      "AI 候选对应的复核已变化，历史分析可读；请重新分析当前版本。",
      { exact: true },
    ),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText("复核版本 v2", { exact: true })).toBeVisible();
});

test("AI transport failure keeps rule results and offers original request retry", async ({
  page,
  request,
}) => {
  const { c } = await seed(request);
  await page.goto(`/cases/${c.case_id}/recommendations`);
  let originalBody: string | null = null;
  await page.route("**/api/v1/evaluations/*/ai-explanations", async (route) => {
    originalBody = route.request().postData();
    await route.abort("failed");
  });
  await page
    .getByRole("checkbox", {
      name: "我同意将本报告的偏好、评分及证据摘要发送到配置的模型，用于推荐解读。",
      exact: true,
    })
    .check();
  await page.getByRole("button", { name: "生成推荐解读", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "重试原操作", exact: true }),
  ).toBeVisible();
  await expect(page.locator("article.listing-row").first()).toContainText(
    "92.75",
  );
  await page
    .getByRole("checkbox", {
      name: "我同意将本报告的偏好、评分及证据摘要发送到配置的模型，用于推荐解读。",
      exact: true,
    })
    .uncheck();
  await expect(
    page.getByRole("button", { name: "重试原操作", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("checkbox", {
      name: "我同意将本报告的偏好、评分及证据摘要发送到配置的模型，用于推荐解读。",
      exact: true,
    })
    .check();
  await page.unroute("**/api/v1/evaluations/*/ai-explanations");
  const retry = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/ai-explanations"),
  );
  await page.getByRole("button", { name: "重试原操作", exact: true }).click();
  expect((await retry).postData()).toBe(originalBody);
  await expect(
    page
      .getByText("测试替身解读：请结合已保存评分与证据比较通勤和费用。")
      .first(),
  ).toBeVisible();
});

test("contract AI candidate view stays usable at 360px", async ({
  page,
  request,
}) => {
  const { c } = await contract(request);
  await page.setViewportSize({ width: 360, height: 1000 });
  await page.goto(`/cases/${c.case_id}/contract`);
  await page
    .getByRole("checkbox", {
      name: "我同意将本合同文本及选房核对资料发送到配置的模型，用于本次 AI 辅助分析。",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "AI 辅助分析合同", exact: true })
    .click();
  await expect(
    page.getByText("AI 候选提取结果", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: resolve(screenshotDir, "contract-ai-mobile.png"),
    fullPage: true,
  });
});

test("reading another AI analysis resets selected candidates and user acknowledgment", async ({
  page,
  request,
}) => {
  const { c, review } = await contract(request);
  await page.goto(`/cases/${c.case_id}/contract`);
  await page
    .getByRole("checkbox", {
      name: "我同意将本合同文本及选房核对资料发送到配置的模型，用于本次 AI 辅助分析。",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "AI 辅助分析合同", exact: true })
    .click();
  await expect(
    page.getByText("AI 候选提取结果", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("checkbox", { name: "选择 AI 字段：合同租金", exact: true })
    .check();
  await page
    .getByRole("checkbox", {
      name: "我已逐项核对所选字段的原文，确认应用到当前复核。",
      exact: true,
    })
    .check();
  await expect(
    page.getByRole("button", { name: "确认应用所选字段", exact: true }),
  ).toBeEnabled();
  const next = await request.post(
    `/api/v1/contract-reviews/${review.review_id}/ai-analyses`,
    {
      data: {
        request_id: crypto.randomUUID(),
        expected_version: 1,
        allow_external_ai: true,
      },
    },
  );
  expect(next.ok()).toBeTruthy();
  await page
    .getByRole("button", { name: "读取最新 AI 分析", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "确认应用所选字段", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("checkbox", { name: "选择 AI 字段：合同租金", exact: true }),
  ).not.toBeChecked();
});
