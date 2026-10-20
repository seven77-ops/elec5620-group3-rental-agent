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
  return { c, e, review: (await r.json()).review, consent, agreement };
}

test("obsolete AI apply completion preserves a different selected review", async ({
  page,
  request,
}) => {
  const { c, review: first, consent, agreement } = await contract(request);
  const upload = await request.post(
    `/api/v1/cases/${c.case_id}/contract-reviews`,
    {
      headers: {
        "Content-Type": "application/octet-stream",
        "X-Consent-Id": consent.consent_id,
        "X-Request-Id": crypto.randomUUID(),
        "X-Filename": "review-b.txt",
      },
      data: Buffer.from(`${agreement}\nSynthetic review B note.\n`),
    },
  );
  expect(upload.ok()).toBeTruthy();
  const second = (await upload.json()).review;
  expect(second.review_id).not.toBe(first.review_id);
  await page.goto(`/cases/${c.case_id}/contract`);
  const selector = page.getByRole("combobox", { name: "选择合同复核记录" });
  await selector.click();
  await page.getByTitle("合同 1 · v1", { exact: true }).click();
  await expect(page.locator(".review-status")).toContainText("复核版本 v1");
  await page
    .getByRole("checkbox", {
      name: "我同意将本合同文本及选房核对资料发送到配置的模型，用于本次 AI 辅助分析。",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "AI 辅助分析合同", exact: true })
    .click();
  await page
    .getByRole("checkbox", { name: "选择 AI 字段：合同租金", exact: true })
    .check();
  await page
    .getByRole("checkbox", {
      name: "我已逐项核对所选字段的原文，确认应用到当前复核。",
      exact: true,
    })
    .check();

  let release!: () => void;
  const heldResponse = new Promise<void>((resolve) => {
    release = resolve;
  });
  let written!: () => void;
  const serverWritten = new Promise<void>((resolve) => {
    written = resolve;
  });
  await page.route(
    `**/contract-reviews/${first.review_id}/ai-analyses/*/apply`,
    async (route) => {
      // Execute the real write before holding only the browser response.
      const response = await route.fetch();
      expect(response.ok()).toBeTruthy();
      written();
      await heldResponse;
      await route.fulfill({ response });
    },
  );
  await page
    .getByRole("button", { name: "确认应用所选字段", exact: true })
    .click();
  await serverWritten;
  expect(
    (
      await (
        await request.get(`/api/v1/contract-reviews/${first.review_id}`)
      ).json()
    ).version,
  ).toBe(2);
  try {
    const loadedB = page.waitForResponse(
      (r) =>
        r.url().endsWith(`/contract-reviews/${second.review_id}`) &&
        r.request().method() === "GET",
    );
    await selector.click();
    await page.getByTitle("合同 2 · v1", { exact: true }).click();
    await loadedB;
    await expect(
      page.getByRole("link", { name: "下载复核 JSON", exact: true }),
    ).toHaveAttribute(
      "href",
      `/api/v1/contract-reviews/${second.review_id}/export`,
    );
    const completed = page.waitForResponse(
      (r) => r.url().endsWith("/apply") && r.request().method() === "POST",
    );
    release();
    await completed;
    // The success message is emitted after onApplied has completed.
    await expect(
      page.getByText("已应用核对字段并保存新复核版本。", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "下载复核 JSON", exact: true }),
    ).toHaveAttribute(
      "href",
      `/api/v1/contract-reviews/${second.review_id}/export`,
    );
    await expect(
      page.locator(".ant-select").filter({ has: selector }),
    ).toContainText("合同 2 · v1");
    await expect(
      page.getByRole("heading", { name: "合同提取字段", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "AI 合同辅助分析", exact: true }),
    ).toBeVisible();
  } finally {
    release();
  }
});

test("obsolete AI apply completion does not refresh a departed case page", async ({
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
  await page
    .getByRole("checkbox", { name: "选择 AI 字段：合同租金", exact: true })
    .check();
  await page
    .getByRole("checkbox", {
      name: "我已逐项核对所选字段的原文，确认应用到当前复核。",
      exact: true,
    })
    .check();
  let release!: () => void;
  const heldResponse = new Promise<void>((resolve) => {
    release = resolve;
  });
  let written!: () => void;
  const serverWritten = new Promise<void>((resolve) => {
    written = resolve;
  });
  await page.route(
    `**/contract-reviews/${review.review_id}/ai-analyses/*/apply`,
    async (route) => {
      const response = await route.fetch();
      expect(response.ok()).toBeTruthy();
      written();
      await heldResponse;
      await route.fulfill({ response });
    },
  );
  await page
    .getByRole("button", { name: "确认应用所选字段", exact: true })
    .click();
  await serverWritten;
  try {
    // The app refresh callback reads the current case ref; leaving this page
    // makes the old Contract callback obsolete even if the app stays mounted.
    await page.getByRole("button", { name: "新建案例", exact: true }).click();
    await expect(page).not.toHaveURL(new RegExp(c.case_id));
    await expect(
      page.getByRole("heading", { name: "租房偏好", exact: true }),
    ).toBeVisible();
    let caseReads = 0;
    page.on("request", (r) => {
      if (r.method() === "GET" && /\/api\/v1\/cases\/[^/]+$/.test(r.url()))
        caseReads++;
    });
    const completed = page.waitForResponse(
      (r) => r.url().endsWith("/apply") && r.request().method() === "POST",
    );
    release();
    await completed;
    await expect(
      page.getByText("已应用核对字段并保存新复核版本。", { exact: true }),
    ).toBeVisible();
    expect(caseReads).toBe(0);
  } finally {
    release();
  }
});

for (const update of ["newer correction", "same-version questions"] as const) {
  test(`same-review AI apply completion preserves ${update}`, async ({
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
    const field = update === "newer correction" ? "合同租金" : "合同地址";
    await page
      .getByRole("checkbox", { name: `选择 AI 字段：${field}`, exact: true })
      .check();
    await page
      .getByRole("checkbox", {
        name: "我已逐项核对所选字段的原文，确认应用到当前复核。",
        exact: true,
      })
      .check();

    let release!: () => void;
    const heldResponse = new Promise<void>((resolve) => {
      release = resolve;
    });
    let written!: (version: number) => void;
    const serverWritten = new Promise<number>((resolve) => {
      written = resolve;
    });
    await page.route(
      `**/contract-reviews/${review.review_id}/ai-analyses/*/apply`,
      async (route) => {
        const response = await route.fetch();
        expect(response.ok()).toBeTruthy();
        written((await response.json()).review.version);
        await heldResponse;
        await route.fulfill({ response });
      },
    );
    await page
      .getByRole("button", { name: "确认应用所选字段", exact: true })
      .click();
    expect(await serverWritten).toBe(update === "newer correction" ? 2 : 1);

    const pendingGets = new Set();
    page.on("request", (r) => {
      if (r.method() === "GET" && r.url().includes("/api/v1/"))
        pendingGets.add(r);
    });
    page.on("requestfinished", (r) => pendingGets.delete(r));
    page.on("requestfailed", (r) => pendingGets.delete(r));
    const readLatest = async () => {
      const loaded = page.waitForResponse(
        (r) =>
          r.request().method() === "GET" &&
          r.url().endsWith(`/contract-reviews/${review.review_id}`),
      );
      const context = page.waitForResponse(
        (r) =>
          r.request().method() === "GET" &&
          r.url().endsWith(`/contract-reviews/${review.review_id}/context`),
      );
      await page
        .getByRole("button", { name: "读取最新复核状态", exact: true })
        .click();
      await Promise.all([
        loaded.then((r) => r.finished()),
        context.then((r) => r.finished()),
      ]);
      await expect.poll(() => pendingGets.size).toBe(0);
    };
    try {
      await readLatest();
      if (update === "newer correction") {
        await expect(
          page.getByText("复核版本 v2", { exact: true }),
        ).toBeVisible();
        await page
          .getByRole("button", { name: "修正提取字段", exact: true })
          .click();
        await page
          .getByRole("spinbutton", { name: "合同租金（AUD）" })
          .fill("510");
        await page
          .getByRole("button", { name: "保存为新复核版本", exact: true })
          .click();
        await expect(
          page.getByText("新复核版本已保存，旧问题已失效。", { exact: true }),
        ).toBeVisible();
        await expect(
          page.locator(".ant-select").filter({
            has: page.getByRole("combobox", { name: "选择合同复核记录" }),
          }),
        ).toContainText("合同 1 · v3");
      } else {
        await page
          .getByRole("button", { name: "准备问题清单", exact: true })
          .click();
        await expect(
          page.getByRole("heading", {
            name: "问题清单 · 尚未发送",
            exact: true,
          }),
        ).toBeVisible();
      }
      // Finish all summary-driven reads and explicitly load the latest object
      // before releasing the older apply response for this same review.
      await readLatest();
      const latest = await (
        await request.get(`/api/v1/contract-reviews/${review.review_id}`)
      ).json();
      expect(latest.version).toBe(update === "newer correction" ? 3 : 1);
      if (update === "same-version questions") {
        expect(latest.questions.length).toBeGreaterThan(0);
        expect(latest.status).toBe("Questions Ready");
      }
      const completed = page.waitForResponse(
        (r) => r.request().method() === "POST" && r.url().endsWith("/apply"),
      );
      release();
      await completed;
      await expect(
        page.getByText(
          update === "newer correction"
            ? "已应用核对字段并保存新复核版本。"
            : "所选字段与现有值一致，无需新增版本。",
          { exact: true },
        ),
      ).toBeVisible();
      await expect.poll(() => pendingGets.size).toBe(0);
      await expect(
        page.getByText(`复核版本 v${latest.version}`, { exact: true }),
      ).toBeVisible();
      if (update === "newer correction") {
        await expect(
          page.getByRole("cell", { name: /合同租金 : 510/ }),
        ).toBeVisible();
      } else {
        await expect(
          page.getByRole("heading", {
            name: "问题清单 · 尚未发送",
            exact: true,
          }),
        ).toBeVisible();
        for (const question of latest.questions)
          await expect(
            page.getByText(question.text, { exact: true }),
          ).toBeVisible();
      }
      expect(
        await (
          await request.get(`/api/v1/contract-reviews/${review.review_id}`)
        ).json(),
      ).toEqual(latest);
    } finally {
      release();
    }
  });
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
