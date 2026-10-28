import { expect, test } from "@playwright/test";

test("utility providers show compact cards and open full details without saving choices", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=utilities`);
  const list = page.locator(".living-provider-grid");
  await expect(list.locator(".utility-plan")).toHaveCount(0);
  const card = page.getByRole("button", {
    name: "AGL，查看供应商详情",
    exact: true,
  });
  await expect(card).toBeVisible();
  const electricity = page.getByRole("combobox", {
    name: "电力供应商",
    exact: true,
  });
  await electricity.click();
  await page
    .locator(".ant-select-dropdown:visible")
    .getByText("AGL", { exact: true })
    .click();
  await card.focus();
  await page.keyboard.press("Enter");
  const modal = page.getByRole("dialog", {
    name: "AGL · 供应商详情",
    exact: true,
  });
  await expect(modal).toBeVisible();
  await expect(modal.locator(".utility-plan").first()).toBeVisible();
  await expect(
    modal.getByRole("link", { name: "官方网站", exact: true }),
  ).toHaveAttribute("href", /^https:\/\//);
  await modal.getByRole("button", { name: "关闭详情", exact: true }).click();
  await expect(modal).toHaveCount(0);
  await expect(card).toBeFocused();
  await expect(
    page.locator(".ant-select").filter({ has: electricity }),
  ).toContainText("AGL");
  await expect(list.locator(".utility-plan")).toHaveCount(0);
  await list.screenshot({ path: "/tmp/utility-provider-cards.png" });
  const state = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(state.version).toBe(0);
  expect(Object.values(state.profile.utilities)).toEqual([
    null,
    null,
    null,
    null,
  ]);
});
