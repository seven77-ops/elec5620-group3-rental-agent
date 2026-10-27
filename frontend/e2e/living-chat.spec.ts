import { test, expect, type Page } from "@playwright/test";

async function send(page: Page, text: string) {
  await page.getByRole("textbox", { name: "给租房助手的消息" }).fill(text);
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
}

test("chat utility confirmation synchronizes the living page and remains applied after reload", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  await page.goto(`/cases/${c.case_id}/assistant`);
  await send(page, "我的电是AGL，网络用TPG，帮我记下来");
  await expect(
    page.getByRole("button", { name: "确认同步租后资料", exact: true }),
  ).toBeVisible();
  expect((await (await request.get(root)).json()).version).toBe(0);
  await page
    .getByRole("button", { name: "确认同步租后资料", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "确认同步到租后服务？",
    exact: true,
  });
  await expect(modal).toContainText("AGL");
  await expect(modal).toContainText("TPG");
  await modal
    .getByRole("button", { name: "确认保存租后资料", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "已同步保存", exact: true }),
  ).toBeDisabled();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "已同步保存", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "查看对应租后服务", exact: true })
    .click();
  await expect(page).toHaveURL(/aftercare\?tab=utilities$/);
  const profile = (await (await request.get(root)).json()).profile;
  expect(profile.utilities.electricity).toBe("agl");
  expect(profile.utilities.internet).toBe("tpg");
  await expect(
    page.getByRole("combobox", { name: "电力供应商", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".living-hub")).toContainText("AGL");
});

test("chat repair proposal becomes an unsent record and recommendations use actual company cards", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  await page.goto(`/cases/${c.case_id}/assistant`);
  await send(page, "厨房水槽下面一直漏水，帮我写报修邮件");
  await page
    .getByRole("button", { name: "确认生成报修草稿", exact: true })
    .click();
  expect((await (await request.get(root)).json()).repairs).toHaveLength(0);
  await page
    .getByRole("button", { name: "确认保存租后资料", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "已同步保存", exact: true }),
  ).toBeDisabled();
  const saved = (await (await request.get(root)).json()).repairs[0];
  expect(saved.email.delivery_status).toBe("prepared_not_sent");
  await page
    .getByRole("button", { name: "查看对应租后服务", exact: true })
    .click();
  await expect(
    page.getByText("草稿已准备 · 尚未发送", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".living-email-body")).toContainText(
    "厨房水槽下面一直漏水",
  );
  await page.goto(
    `/cases/${c.case_id}/assistant?message=${encodeURIComponent("帮我找悉尼搬家公司")}`,
  );
  await expect(
    page.getByRole("textbox", { name: "给租房助手的消息" }),
  ).toHaveValue("帮我找悉尼搬家公司");
  await expect(page.getByRole("checkbox", { name: /同意本次/ })).toHaveCount(0);
  await send(page, "帮我找悉尼搬家公司");
  const card = page.locator(
    '.assistant-listing[data-provider-id="two-men-and-a-truck"]',
  );
  await expect(
    card.getByRole("link", { name: "公司网站 ↗", exact: true }),
  ).toHaveAttribute("href", "https://www.twomen.com.au/");
  await expect(
    card.getByRole("link", { name: "1300 880 412", exact: true }),
  ).toHaveAttribute("href", "tel:1300880412");
  expect((await (await request.get(root)).json()).bookings).toHaveLength(0);
});
