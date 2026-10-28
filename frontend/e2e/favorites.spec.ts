import { test, expect } from "@playwright/test";

test("favorites persist across pages, compare independently, and only explicit selection starts follow-up", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  const rows = (
    await (await request.get("/api/v1/listings?page_size=3")).json()
  ).items;
  await page.goto(`/cases/${c.case_id}/recommendations`);
  const table = page.getByTestId("real-catalog");
  await table
    .getByRole("button", { name: "收藏房源", exact: true })
    .first()
    .click();
  await expect(
    table.getByRole("button", { name: "取消收藏", exact: true }),
  ).toHaveCount(1);
  await table
    .getByRole("button", { name: "收藏房源", exact: true })
    .first()
    .click();
  await expect(
    table.getByRole("button", { name: "取消收藏", exact: true }),
  ).toHaveCount(2);
  expect((await (await request.get(root)).json()).selection).toBeNull();
  await page.reload();
  await page
    .getByRole("button", { name: "我的收藏（2）", exact: true })
    .click();
  const drawer = page.getByRole("dialog", { name: "我的收藏", exact: true });
  await expect(drawer.locator('[data-testid="favorite-home"]')).toHaveCount(2);
  await drawer.getByRole("checkbox").nth(0).check();
  await drawer.getByRole("checkbox").nth(1).check();
  await expect(
    drawer.getByRole("table", { name: "收藏房源比较" }),
  ).toContainText(rows[0].address);
  await page.screenshot({ path: "/tmp/favorites-desktop.png" });
  await drawer
    .getByRole("searchbox", { name: "筛选收藏房源" })
    .fill("no-such-area");
  await expect(drawer.locator('[data-testid="favorite-home"]')).toHaveCount(0);
  await drawer.getByRole("searchbox", { name: "筛选收藏房源" }).fill("");
  await drawer
    .getByRole("button", { name: "关闭", exact: true })
    .first()
    .click();
  await page.getByRole("menuitem", { name: "AI租房助手", exact: true }).click();
  await page
    .getByRole("button", { name: "我的收藏（2）", exact: true })
    .click();
  await expect(drawer.locator('[data-testid="favorite-home"]')).toHaveCount(2);
  await drawer
    .getByRole("button", { name: "关闭", exact: true })
    .first()
    .click();
  const confirmed = await request.post(root + "/profile-confirmations", {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  expect(confirmed.status()).toBe(200);
  await page.reload();
  await page
    .getByRole("button", { name: "我的收藏（2）", exact: true })
    .click();
  await drawer
    .getByRole("button", { name: "选定并跟进", exact: true })
    .first()
    .click();
  await page
    .getByRole("button", { name: "确认并开始跟进", exact: true })
    .click();
  await expect(page.getByTestId("candidate-next")).toBeVisible();
  await expect(drawer).not.toBeVisible();
  await page.getByRole("button", { name: /我的收藏（[12]）/ }).click();
  await expect(drawer.getByText("当前跟进房源", { exact: true })).toBeVisible();
  const first = (await (await request.get(root)).json()).selection;
  const active = drawer
    .locator('[data-testid="favorite-home"]')
    .filter({ hasText: first.listing_snapshot.address });
  await active.getByRole("button", { name: "取消收藏", exact: true }).click();
  await expect(drawer.locator('[data-testid="favorite-home"]')).toHaveCount(1);
  expect((await (await request.get(root)).json()).selection.listing_id).toBe(
    first.listing_id,
  );
  await drawer.getByRole("button", { name: "选定并跟进", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "选定这套房并开始跟进？" }),
  ).toContainText("将替换当前跟进房源");
  await page.getByRole("button", { name: "继续比较", exact: true }).click();
  expect((await (await request.get(root)).json()).selection.listing_id).toBe(
    first.listing_id,
  );
  await drawer.getByRole("button", { name: "选定并跟进", exact: true }).click();
  await page
    .getByRole("button", { name: "确认并开始跟进", exact: true })
    .click();
  await expect(drawer).not.toBeVisible();
  await page.getByRole("button", { name: /我的收藏（[12]）/ }).click();
  await expect(drawer.getByText("当前跟进房源", { exact: true })).toBeVisible();
  expect(
    (await (await request.get(root)).json()).selection.listing_id,
  ).not.toBe(first.listing_id);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(async () =>
    expect((await drawer.boundingBox())!.width).toBeLessThanOrEqual(390),
  ).toPass();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await expect(page.locator(".ant-message-notice")).toHaveCount(0);
  await page.screenshot({ path: "/tmp/favorites-mobile.png" });
  expect(errors).toEqual([]);
});

test("chat cards collect multiple homes without confirming needs or choosing a follow-up home", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  const input = page.getByRole("textbox", { name: "给租房助手的消息" });
  await input.fill("帮我找一下房源");
  await input.press("Enter");
  const cards = page.locator(".assistant-listing");
  await expect(cards.first()).toBeVisible();
  await cards
    .nth(0)
    .getByRole("button", { name: "收藏房源", exact: true })
    .click();
  await expect(
    cards.nth(0).getByRole("button", { name: "取消收藏", exact: true }),
  ).toBeVisible();
  await cards
    .nth(1)
    .getByRole("button", { name: "收藏房源", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "我的收藏（2）", exact: true }),
  ).toBeVisible();
  const state = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(state.selection).toBeNull();
  expect(state.confirmations).toHaveLength(0);
  await page.getByRole("menuitem", { name: "房源推荐", exact: true }).click();
  await page
    .getByRole("button", { name: "我的收藏（2）", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog", { name: "我的收藏", exact: true })
      .getByTestId("favorite-home"),
  ).toHaveCount(2);
});
