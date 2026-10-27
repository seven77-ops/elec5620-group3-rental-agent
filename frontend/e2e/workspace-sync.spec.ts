import { test, expect } from "@playwright/test";
import { fillRentalNeeds, confirmRentalNeeds } from "./fillRentalNeeds";

test("AI-collected needs prefill the panel and sync without retyping other conditions", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/assistant/conversations`;
  let conversation = await (await request.post(root, { data: {} })).json();
  for (const [index, message] of [
    "Rhodes 预算最高800 人数一人 要2b2b 车位无所谓",
    "整套，每周",
  ].entries()) {
    const response = await request.post(
      `${root}/${conversation.conversation_id}/messages`,
      {
        data: {
          request_id: `ui-intake-${index}`,
          expected_revision: conversation.revision,
          message,
          allow_external_ai: true,
        },
      },
    );
    expect(response.status()).toBe(200);
    conversation = await response.json();
  }
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page.getByRole("button", { name: "我的租房需求", exact: true }).click();
  const drawer = page.getByRole("dialog", {
    name: "我的租房需求",
    exact: true,
  });
  await expect(
    drawer.getByRole("spinbutton", { name: "最高预算（AUD）", exact: true }),
  ).toHaveValue("800");
  await expect(
    drawer.getByRole("spinbutton", { name: "至少卧室", exact: true }),
  ).toHaveValue("2");
  await expect(
    drawer.getByRole("spinbutton", { name: "至少浴室", exact: true }),
  ).toHaveValue("2");
  await expect(
    drawer.getByRole("spinbutton", { name: "至少车位", exact: true }),
  ).toHaveValue("0");
  await drawer
    .getByRole("spinbutton", { name: "最高预算（AUD）", exact: true })
    .fill("900");
  await drawer
    .getByRole("button", { name: "确认并同步需求", exact: true })
    .click();
  await page
    .getByRole("dialog", { name: "确认同步租房需求？", exact: true })
    .getByRole("button", { name: "确认同步并生成推荐", exact: true })
    .click();
  await expect(page.getByTestId("assistant-needs-status")).toHaveCount(0);
  await expect(drawer).not.toBeVisible();
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.confirmations[0].profile.budget).toMatchObject({
    maximum: 900,
    scope: "whole_property",
  });
  expect(saved.confirmations[0].profile.housing_preferences).toMatchObject({
    suburb: "Rhodes",
    min_bedrooms: 2,
    min_bathrooms: 2,
    min_car_spaces: 0,
  });
  await page.getByRole("menuitem", { name: "房源推荐", exact: true }).click();
  await expect(
    page.getByRole("spinbutton", { name: "最高周租（AUD）", exact: true }),
  ).toHaveValue("900");
});

test("chat needs require confirmation, sync real recommendations and persist a selected card", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(
    page.getByRole("menuitem", { name: "租房偏好", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "我的租房需求", exact: true }).click();
  const drawer = page.getByRole("dialog", {
    name: "我的租房需求",
    exact: true,
  });
  await drawer.getByLabel("偏好区域", { exact: true }).click();
  await drawer.getByLabel("偏好区域", { exact: true }).fill("Rhodes");
  await page.getByRole("option", { name: "Rhodes", exact: true }).click();
  await drawer
    .getByRole("spinbutton", { name: "最高预算（AUD）", exact: true })
    .fill("1500");
  await drawer.getByLabel("预算周期", { exact: true }).click();
  await page.getByRole("option", { name: "每周", exact: true }).click();
  await drawer.getByLabel("计价对象", { exact: true }).click();
  await page.getByRole("option", { name: "整套", exact: true }).click();
  await drawer.getByLabel("租赁方式", { exact: true }).click();
  await page.getByRole("option", { name: "整租", exact: true }).click();
  await drawer
    .getByRole("spinbutton", { name: "居住人数", exact: true })
    .fill("1");
  await drawer
    .getByRole("spinbutton", { name: "至少卧室", exact: true })
    .fill("2");
  await drawer
    .getByRole("spinbutton", { name: "至少浴室", exact: true })
    .fill("2");
  await drawer
    .getByRole("spinbutton", { name: "至少车位", exact: true })
    .fill("1");
  await drawer
    .getByRole("button", { name: "确认并同步需求", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "确认同步租房需求？",
    exact: true,
  });
  await expect(modal).toContainText("1500");
  await expect(modal).toContainText("Rhodes");
  for (const preset of [
    "450",
    "demo-usyd",
    "2027-02-01",
    "含账单",
    "软偏好",
    "权重",
    "悉尼大学",
  ])
    await expect(modal).not.toContainText(preset);
  await modal.getByRole("button", { name: "继续修改", exact: true }).click();
  expect(
    (await (await request.get(`/api/v1/cases/${c.case_id}`)).json())
      .confirmations,
  ).toHaveLength(0);
  await drawer
    .getByRole("button", { name: "确认并同步需求", exact: true })
    .click();
  await modal
    .getByRole("button", { name: "确认同步并生成推荐", exact: true })
    .click();
  await expect(drawer).not.toBeVisible();
  await expect(page.getByTestId("assistant-needs-status")).toHaveCount(0);
  const card = page.locator(".assistant-listing").first();
  await expect(card).toBeVisible();
  const address = await card.locator("h3").innerText();
  await card.getByRole("button", { name: "保存为候选", exact: true }).click();
  await page
    .getByRole("dialog", { name: "保存这条真实房源候选？", exact: true })
    .getByRole("button", { name: "确认保存候选", exact: true })
    .click();
  await expect(card.getByText("当前候选", { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    page
      .locator(".assistant-listing")
      .first()
      .getByText("当前候选", { exact: true }),
  ).toBeVisible();
  await page.getByRole("menuitem", { name: "房源推荐", exact: true }).click();
  await expect(page.getByText(address, { exact: true }).first()).toBeVisible();
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.confirmations.at(-1).version).toBe(1);
  expect(saved.selection.listing_snapshot.address).toBe(address);
  expect(saved.confirmations[0].profile.housing_preferences).toMatchObject({
    suburb: "Rhodes",
    min_bedrooms: 2,
    min_bathrooms: 2,
    min_car_spaces: 1,
  });
});

test("mobile chat keeps needs management inside the conversation page", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(`/cases/${c.case_id}/assistant?needs=1`);
  const drawer = page.getByRole("dialog", {
    name: "我的租房需求",
    exact: true,
  });
  await expect(drawer).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await drawer.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "给租房助手的消息" }),
  ).toBeVisible();
});

test("new needs remain blank and optional dates do not block saving a real budget", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  expect(c.draft.profile).toEqual({
    schema_version: "1.0",
    search_id: c.search_id,
    profile_version: 1,
  });
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page.getByRole("button", { name: "我的租房需求", exact: true }).click();
  const drawer = page.getByRole("dialog", {
    name: "我的租房需求",
    exact: true,
  });
  await expect(
    drawer.getByRole("spinbutton", { name: "最高预算（AUD）", exact: true }),
  ).toHaveValue("");
  await expect(
    drawer.getByRole("spinbutton", { name: "居住人数", exact: true }),
  ).toHaveValue("");
  await expect(
    drawer.getByRole("spinbutton", { name: "至少卧室", exact: true }),
  ).toHaveValue("");
  await page.goto(`/cases/${c.case_id}/preferences`);
  await expect(page).toHaveURL(
    new RegExp(`/cases/${c.case_id}/assistant\\?needs=1$`),
  );
  await expect(
    page.getByRole("heading", { name: "房屋条件", exact: true }),
  ).toHaveCount(0);
  const panel = await fillRentalNeeds(page, { budget: 1000 });
  for (const copy of [
    "AI 整理的条件",
    "数量填 0",
    "上课前到达时间",
    "出行日",
    "记录你看重什么",
  ])
    await expect(panel).not.toContainText(copy);
  await expect(
    panel.getByRole("button", { name: "其他偏好与完整设置", exact: true }),
  ).toHaveCount(0);
  await expect(
    panel.getByRole("button", { name: "查看房源推荐", exact: true }),
  ).toHaveCount(0);
  await page.screenshot({ path: "/tmp/rental-needs-cleanup-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await panel
    .getByRole("button", { name: "确认并同步需求", exact: true })
    .scrollIntoViewIfNeeded();
  await expect.poll(async () => {
    const box = await panel.boundingBox();
    return !!box && box.x >= 0 && box.x + box.width <= 391;
  }).toBe(true);
  await page.screenshot({ path: "/tmp/rental-needs-cleanup-mobile.png" });
  await confirmRentalNeeds(page);
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.draft.profile.budget.maximum).toBe(1000);
  expect(saved.confirmations.at(-1).profile.budget.maximum).toBe(1000);
  expect(saved.draft.profile).not.toHaveProperty("commute");
  expect(saved.draft.profile).not.toHaveProperty("move_in_window");
  expect(saved.draft.profile).not.toHaveProperty("hard_requirements");
  expect(saved.draft.profile).not.toHaveProperty("soft_preferences");
});
