import { expect, test } from "@playwright/test";

test("moving and cleaning are grouped compact cards with keyboard details and a single booking dialog", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=services`);
  const moving = page.getByRole("region", { name: "搬运公司", exact: true });
  const cleaning = page.getByRole("region", { name: "清洁公司", exact: true });
  await expect(moving.locator(".living-provider-card")).toHaveCount(12);
  await expect(cleaning.locator(".living-provider-card")).toHaveCount(12);
  await expect(moving.getByRole("link")).toHaveCount(0);
  await expect(cleaning.getByRole("link")).toHaveCount(0);
  const card = moving.getByRole("button", {
    name: "Men That Move，查看服务商详情",
    exact: true,
  });
  await card.focus();
  await page.keyboard.press("Enter");
  const details = page.getByRole("dialog", {
    name: "Men That Move · 服务商详情",
    exact: true,
  });
  await expect(details).toBeVisible();
  await expect(details).toContainText("家具和住宅搬运");
  await expect(
    details.getByRole("link", { name: "公司网站", exact: true }),
  ).toHaveAttribute("href", "https://menthatmove.com/");
  await expect(details.getByRole("link")).toHaveCount(1);
  await expect(details).not.toContainText("路线");
  await expect(moving).not.toContainText("路线");
  await expect(cleaning).not.toContainText("路线");
  await page.keyboard.press("Escape");
  await expect(details).toHaveCount(0);
  await expect(card).toBeFocused();
  await card.click();
  await details
    .getByRole("button", { name: "记录报价或预约", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(1);
  const booking = page.getByRole("dialog", {
    name: "记录 · Men That Move",
    exact: true,
  });
  await expect(
    booking.getByRole("spinbutton", { name: "收到的报价（AUD）", exact: true }),
  ).toBeVisible();
  await booking.getByRole("button", { name: "取消", exact: true }).click();
  await expect(booking).toHaveCount(0);
  const state = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(state.version).toBe(0);
  expect(state.bookings).toHaveLength(0);
  await moving.screenshot({
    path: "/tmp/service-moving-cards.png",
    animations: "disabled",
  });
});
