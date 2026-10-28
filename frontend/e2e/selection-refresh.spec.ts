import { test, expect } from "@playwright/test";

test("an over-limit historical card explains the mismatch without locking chat or favorites", async ({
  page,
  request,
}) => {
  let c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  const conversation = await (
    await request.post(root + "/assistant/conversations", { data: {} })
  ).json();
  const search = await request.post(
    root + `/assistant/conversations/${conversation.conversation_id}/messages`,
    {
      data: {
        request_id: "old-search",
        expected_revision: 0,
        message: "找Rhodes的两卧房源",
        allow_external_ai: true,
      },
    },
  );
  expect(search.status()).toBe(200);
  const rows = (await search.json()).messages.at(-1).listings;
  const row = rows.find(
    (item: any) =>
      item.usyd_commute?.modes?.public_transport?.duration_minutes > 30,
  );
  expect(row).toBeTruthy();
  c = await (
    await request.post(root + "/profile-drafts", {
      data: {
        expected_revision: c.draft.revision,
        profile: {
          ...c.draft.profile,
          budget: {
            currency: "AUD",
            period: "week",
            scope: "whole_property",
            maximum: 1500,
          },
          housing_preferences: {
            suburb: "Rhodes",
            min_bedrooms: 2,
            min_bathrooms: 2,
            min_car_spaces: 1,
          },
          student_commute: { mode: "public_transport", maximum_minutes: 30 },
        },
      },
    })
  ).json();
  expect(
    (
      await request.post(root + "/profile-confirmations", {
        data: {
          draft_revision: c.draft.revision,
          fingerprint: c.draft.fingerprint,
          review_token: c.agent1.review_token,
        },
      })
    ).status(),
  ).toBe(200);
  await page.goto(`/cases/${c.case_id}/assistant`);
  const card = page.locator(`[data-listing-id="${row.listing_id}"]`);
  await card.getByRole("button", { name: "选定并跟进", exact: true }).click();
  await page
    .getByRole("button", { name: "确认并开始跟进", exact: true })
    .click();
  const warning = page
    .getByRole("alert")
    .filter({ hasText: "这套房源不符合当前筛选条件" });
  await expect(warning).toContainText("超过你设置的 30 分钟");
  await expect(warning).not.toContainText("到校时刻");
  await expect(
    page.getByRole("button", { name: "重试原操作", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("textbox", { name: "给租房助手的消息" }),
  ).toBeEnabled();
  await expect(
    card.getByRole("button", { name: "收藏房源", exact: true }),
  ).toBeEnabled();
  await page.screenshot({
    path: "/tmp/selection-mismatch-warning.png",
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/selection-mismatch-mobile.png",
    animations: "disabled",
  });
  await card.getByRole("button", { name: "收藏房源", exact: true }).click();
  await expect(
    card.getByRole("button", { name: "取消收藏", exact: true }),
  ).toBeVisible();
  expect((await (await request.get(root)).json()).selection).toBeNull();
  await warning
    .getByRole("button", { name: "调整租房需求", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "我的租房需求", exact: true }),
  ).toBeVisible();
});

test("legacy arrival deadlines do not affect approximate discovery or selecting a home", async ({
  page,
  request,
}) => {
  let c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  const row = (
    await (
      await request.get(
        "/api/v1/listings?usyd_mode=public_transport&usyd_max_minutes=30&page_size=20",
      )
    ).json()
  ).items[0];
  await request.post(root + "/favorites", {
    data: { request_id: "favorite", listing_id: row.listing_id, saved: true },
  });
  c = await (
    await request.post(root + "/profile-drafts", {
      data: {
        expected_revision: c.draft.revision,
        profile: {
          ...c.draft.profile,
          student_commute: {
            mode: "public_transport",
            maximum_minutes: 30,
            arrival_time: "03:17",
            travel_day: "weekend",
            travel_date: "2000-01-01",
          },
        },
      },
    })
  ).json();
  expect(
    (
      await request.post(root + "/profile-confirmations", {
        data: {
          draft_revision: c.draft.revision,
          fingerprint: c.draft.fingerprint,
          review_token: c.agent1.review_token,
        },
      })
    ).status(),
  ).toBe(200);
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page.getByRole("button", { name: "我的租房需求", exact: true }).click();
  const needs = page.getByRole("dialog", { name: "我的租房需求", exact: true });
  await expect(needs).not.toContainText("03:17");
  await expect(
    needs.getByRole("button", { name: "不限定到校时刻", exact: true }),
  ).toHaveCount(0);
  await needs.getByRole("button", { name: "关闭", exact: true }).click();
  await page
    .getByRole("button", { name: "我的收藏（1）", exact: true })
    .click();
  await page.getByRole("button", { name: "选定并跟进", exact: true }).click();
  const modal = page.getByRole("dialog", {
    name: "选定这套房并开始跟进？",
    exact: true,
  });
  await expect(modal).toContainText("通勤按大概时长参考");
  await expect(modal).not.toContainText("03:17");
  await modal
    .getByRole("button", { name: "确认并开始跟进", exact: true })
    .click();
  await expect(page.getByTestId("candidate-next")).toContainText(row.address);
  const state = await (await request.get(root)).json();
  expect(state.selection.listing_id).toBe(row.listing_id);
  expect(state.confirmations[0].profile.student_commute.arrival_time).toBe(
    "03:17",
  );
  await page.reload();
  await expect(page.getByTestId("candidate-next")).toContainText(row.address);
  await page.getByRole("menuitem", { name: "房源推荐", exact: true }).click();
  const result = page.getByRole("heading", { name: /筛选结果/ });
  await expect(result).toContainText(/筛选结果.*\d+ 条/);
  await expect(
    page.getByTestId("real-catalog").locator("tbody tr.ant-table-row").first(),
  ).toBeVisible();
  await page.screenshot({
    path: "/tmp/timeless-commute-desktop.png",
    animations: "disabled",
  });
});
