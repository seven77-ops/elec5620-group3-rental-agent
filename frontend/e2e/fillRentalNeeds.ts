import { expect, type Page } from "@playwright/test";

export async function fillRentalNeeds(
  page: Page,
  {
    suburb = "不限区域",
    budget = 1000,
    bedrooms = 0,
    bathrooms = 0,
    parking = 0,
  } = {},
) {
  const drawer = page.getByRole("dialog", {
    name: "我的租房需求",
    exact: true,
  });
  await expect(drawer).toBeVisible();
  await drawer.getByLabel("偏好区域", { exact: true }).click();
  await page.getByRole("option", { name: suburb, exact: true }).click();
  await drawer
    .getByLabel("最高预算（AUD）", { exact: true })
    .fill(String(budget));
  for (const [field, choice] of [
    ["预算周期", "每周"],
    ["计价对象", "整套"],
    ["租赁方式", "整租"],
  ]) {
    await drawer.getByLabel(field, { exact: true }).click();
    await page.getByRole("option", { name: choice, exact: true }).click();
  }
  for (const [field, value] of [
    ["居住人数", 1],
    ["至少卧室", bedrooms],
    ["至少浴室", bathrooms],
    ["至少车位", parking],
  ] as const) {
    await drawer
      .getByRole("spinbutton", { name: field, exact: true })
      .fill(String(value));
  }
  return drawer;
}

export async function confirmRentalNeeds(page: Page) {
  const drawer = page.getByRole("dialog", {
    name: "我的租房需求",
    exact: true,
  });
  await drawer
    .getByRole("button", { name: "保存找房条件", exact: true })
    .click();
  await expect(drawer).not.toBeVisible();
}
