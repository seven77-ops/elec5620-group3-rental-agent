import { test, expect } from "@playwright/test";

test("real catalogue has 500 ads, paginates, filters, and preserves unknowns", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (["error", "warning"].includes(m.type())) errors.push(m.text());
  });
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(
    page.getByRole("heading", { name: "真实房源推荐", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("catalog-summary")).toContainText(
    "500 条真实房源",
  );
  await expect(page.getByTestId("catalog-summary")).toContainText("71 个区域");
  await expect(
    page.getByTestId("real-catalog").locator("tbody tr.ant-table-row"),
  ).toHaveCount(20);
  const first = await page
    .getByTestId("real-catalog")
    .locator("tbody tr.ant-table-row")
    .first()
    .innerText();
  await page.locator(".ant-pagination-item-2").click();
  await expect(
    page.getByTestId("real-catalog").locator("tbody tr.ant-table-row").first(),
  ).not.toHaveText(first);
  await page
    .getByRole("spinbutton", { name: "至少卧室数", exact: true })
    .fill("2");
  await page
    .getByRole("spinbutton", { name: "至少浴室数", exact: true })
    .fill("2");
  await page
    .getByRole("spinbutton", { name: "至少车位数", exact: true })
    .fill("1");
  await page
    .getByRole("spinbutton", { name: "最高周租（AUD）", exact: true })
    .fill("1500");
  await page.getByRole("button", { name: "应用筛选", exact: true }).click();
  await expect(page.locator(".ant-spin-spinning")).toHaveCount(0);
  const rows = page
    .getByTestId("real-catalog")
    .locator("tbody tr.ant-table-row");
  await expect(rows.first()).toBeVisible();
  for (const row of await rows.all()) {
    const cells = row.locator("td");
    expect(Number(await cells.nth(1).innerText())).toBeGreaterThanOrEqual(2);
    expect(Number(await cells.nth(2).innerText())).toBeGreaterThanOrEqual(2);
    expect(Number(await cells.nth(3).innerText())).toBeGreaterThanOrEqual(1);
    expect(
      Number((await cells.nth(4).innerText()).replace(/[^\d.]/g, "")),
    ).toBeLessThanOrEqual(1500);
  }
  await page
    .getByRole("button", { name: "查看房源详情", exact: true })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText("待确认事项");
  await expect(
    page.getByRole("dialog").getByRole("link", { name: "查看 Domain 房源" }),
  ).toHaveAttribute("href", /^https:\/\/www.domain.com.au\//);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("spinbutton", { name: "最高周租（AUD）", exact: true })
    .fill("1");
  await page.getByRole("button", { name: "应用筛选", exact: true }).click();
  await expect(
    page.getByText("没有符合当前筛选的真实房源，可调整区域、户型或周租。"),
  ).toBeVisible();
  expect(errors).toEqual([]);
  await expect(page.locator("vite-error-overlay")).toHaveCount(0);
});

test("confirmed Agent1 profile produces real report and durable provisional selection", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await request.post(`/api/v1/cases/${c.case_id}/profile-confirmations`, {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  // Exercise the existing preferences-to-evaluation entry point, now backed by real data.
  await page.goto(`/cases/${c.case_id}/preferences`);
  await page.getByRole("button", { name: "生成推荐", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "真实房源推荐", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("当前偏好 v1 · 候选报告已保存")).toBeVisible();
  await page
    .getByRole("button", { name: "保存候选", exact: true })
    .first()
    .click();
  await page.getByRole("button", { name: "确认保存候选", exact: true }).click();
  await expect(
    page.getByText("已保存真实房源候选", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("已保存真实房源候选", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("当前偏好 v1 · 候选报告已保存")).toBeVisible();
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.selection.data_mode).toBe("real_listings");
  expect(saved.selection.contract_ready).toBe(false);
  expect(saved.selection.listing_snapshot.weekly_rent).toBeGreaterThan(0);
  await page.getByRole("menuitem", { name: "合同助手" }).click();
  await page.getByRole("tab", { name: "上传合同复核", exact: true }).click();
  await expect(
    page.getByText("可以直接复核已有合同", { exact: true }),
  ).toBeVisible();
});

test("reload restores the filters bound to the latest real report", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await request.post(`/api/v1/cases/${c.case_id}/profile-confirmations`, {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  await request.post(`/api/v1/cases/${c.case_id}/evaluations`, {
    data: {
      request_id: "filtered",
      confirmation_version: 1,
      filters: { suburb: "Rhodes", min_bedrooms: 2 },
    },
  });
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(page.getByText("当前偏好 v1 · 候选报告已保存")).toBeVisible();
  await expect(
    page.getByRole("spinbutton", { name: "至少卧室数", exact: true }),
  ).toHaveValue("2");
  const rows = page
    .getByTestId("real-catalog")
    .locator("tbody tr.ant-table-row");
  await expect(rows.first()).toContainText("Rhodes");
  for (const row of await rows.all()) await expect(row).toContainText("Rhodes");
});

test("mobile catalogue and source details stay usable", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/real-data`);
  await expect(page.getByTestId("catalog-summary")).toContainText(
    "500 条真实房源",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/agent2-real-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "/tmp/agent2-real-desktop.png",
    fullPage: true,
  });
});

test("a late saved report does not overwrite filters the user is editing", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await request.post(`/api/v1/cases/${c.case_id}/profile-confirmations`, {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  const run = await (
    await request.post(`/api/v1/cases/${c.case_id}/evaluations`, {
      data: {
        request_id: "saved",
        confirmation_version: 1,
        filters: { suburb: "Rhodes", max_weekly_rent: 1500 },
      },
    })
  ).json();
  let release!: () => void, entered!: () => void;
  const hold = new Promise<void>((resolve) => {
    release = resolve;
  });
  const seen = new Promise<void>((resolve) => {
    entered = resolve;
  });
  await page.route(`**/api/v1/evaluations/${run.run_id}`, async (route) => {
    entered();
    await hold;
    await route.continue();
  });
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await seen;
  await page
    .getByRole("spinbutton", { name: "最高周租（AUD）", exact: true })
    .fill("1000");
  release();
  await expect(
    page.getByRole("link", { name: "下载真实候选报告", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("spinbutton", { name: "最高周租（AUD）", exact: true }),
  ).toHaveValue("1000");
});

test("preferences generate mapped budget and housing filters in the merged recommendations page", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/preferences`);
  await expect(
    page.getByRole("heading", { name: "房屋条件", exact: true }),
  ).toBeVisible();
  await page.getByRole("spinbutton", { name: /最高周预算/ }).fill("1500");
  await page
    .getByRole("combobox", { name: "偏好区域", exact: true })
    .fill("Rhodes");
  await page
    .getByRole("combobox", { name: "偏好区域", exact: true })
    .press("Enter");
  await page.getByRole("spinbutton", { name: "偏好至少卧室数" }).fill("2");
  await page.getByRole("spinbutton", { name: "偏好至少浴室数" }).fill("2");
  await page.getByRole("spinbutton", { name: "偏好至少车位数" }).fill("1");
  await page.getByRole("button", { name: "保存草稿", exact: true }).click();
  await expect(
    page.getByText("草稿已保存，请确认当前偏好后再生成推荐。"),
  ).toBeVisible();
  await page.getByRole("button", { name: "确认当前偏好", exact: true }).click();
  await page.getByRole("button", { name: "确认这些条件", exact: true }).click();
  await page.getByRole("button", { name: "生成推荐", exact: true }).click();
  await expect(page.getByText("当前偏好 v1 · 候选报告已保存")).toBeVisible();
  for (const [name, value] of [
    ["最高周租（AUD）", "1500"],
    ["至少卧室数", "2"],
    ["至少浴室数", "2"],
    ["至少车位数", "1"],
  ]) {
    await expect(
      page.getByRole("spinbutton", { name, exact: true }),
    ).toHaveValue(value);
  }
  await expect(page.getByTestId("preference-linkage")).toContainText(
    "已确认偏好 v1",
  );
  await expect(
    page.getByRole("menuitem", { name: "真实数据", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByTestId("real-catalog").locator("tbody tr.ant-table-row").first(),
  ).toContainText("Rhodes");
  await page.reload();
  await expect(
    page.getByRole("spinbutton", { name: "最高周租（AUD）", exact: true }),
  ).toHaveValue("1500");
  await page.goto(`/cases/${c.case_id}/real-data`);
  await expect(page).toHaveURL(
    new RegExp(`/cases/${c.case_id}/recommendations$`),
  );
  await page.getByText("房源补充工具", { exact: true }).click();
  await expect(
    page.getByRole("tab", { name: "租金参考", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("generation keeps applied filters stable while its response is pending", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await request.post(`/api/v1/cases/${c.case_id}/profile-confirmations`, {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(
    page.getByRole("spinbutton", { name: "最高周租（AUD）", exact: true }),
  ).toHaveValue("550");
  let release!: () => void, entered!: () => void;
  const hold = new Promise<void>((resolve) => (release = resolve)),
    seen = new Promise<void>((resolve) => (entered = resolve));
  await page.route("**/api/v1/cases/*/evaluations", async (route) => {
    entered();
    await hold;
    await route.continue();
  });
  await page
    .getByRole("button", { name: "生成当前筛选的候选报告", exact: true })
    .click();
  await seen;
  try {
    await expect(
      page.getByRole("spinbutton", {
        name: "最高周租（AUD）",
        exact: true,
      }),
    ).toBeDisabled();
  } finally {
    release();
  }
  await expect(page.getByText("当前偏好 v1 · 候选报告已保存")).toBeVisible();
});
