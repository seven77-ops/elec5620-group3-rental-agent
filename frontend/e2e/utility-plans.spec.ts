import { expect, test } from "@playwright/test";

test("stored plans show promotional and ongoing fees with official sources", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const directory = await (
    await request.get("/api/v1/living-providers")
  ).json();
  expect(directory.plan_catalog.total).toBe(165);
  expect(
    directory.providers.filter((p: { plans?: unknown[] }) => p.plans?.length),
  ).toHaveLength(9);
  await page.goto(`/cases/${c.case_id}/aftercare?tab=utilities`);
  const telstra = page.locator(
    '.living-provider-card[data-provider-id="telstra"]',
  );
  await expect(telstra).not.toContainText("AUD");
  await telstra.click();
  const telstraDetails = page.getByRole("dialog", {
    name: "Telstra · 供应商详情",
    exact: true,
  });
  await expect(telstraDetails).toContainText("AUD 89/月");
  await expect(telstraDetails).toContainText(
    "前6个月 AUD 69/月；之后 AUD 99/月",
  );
  const plan = telstraDetails.locator('[data-plan-id="telstra-essential"]');
  await plan.getByText("计价详情与适用条件", { exact: true }).click();
  await expect(plan).toContainText("2026-11-02");
  await expect(plan).toContainText("AUD360");
  await expect(
    plan.getByRole("link", { name: "官方套餐与费率 ↗" }),
  ).toHaveAttribute("href", "https://www.telstra.com.au/internet/plans");
  await telstraDetails
    .getByRole("button", { name: "关闭详情", exact: true })
    .click();
  await expect(telstraDetails).toHaveCount(0);
  const water = page.locator(
    '.living-provider-card[data-provider-id="sydney-water"]',
  );
  await water.click();
  const waterDetails = page.getByRole("dialog", {
    name: "Sydney Water · 供应商详情",
    exact: true,
  });
  await expect(waterDetails).toContainText("AUD 3.41/kL");
  await expect(waterDetails).toContainText("房东固定费用");
  await waterDetails.getByText("计价详情与适用条件", { exact: true }).click();
  await expect(
    waterDetails.getByRole("link", { name: "NSW费用责任说明 ↗" }),
  ).toHaveAttribute("href", /www.nsw.gov.au/);
  await page.screenshot({
    path: "/tmp/utility-plans-desktop.png",
    animations: "disabled",
    fullPage: false,
  });
});

test("chat recommendations use ongoing budget and do not save a supplier", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByRole("textbox", { name: "给租房助手的消息" })
    .fill("推荐每月80以内的网络套餐");
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
  await expect(
    page.locator(".assistant-message-assistant .assistant-bubble").last(),
  ).toContainText("按恢复原价后的月租筛选");
  await expect(page.locator(".assistant-listing .utility-plan")).toHaveCount(2);
  const data = await (
    await request.get(`/api/v1/cases/${c.case_id}/assistant/conversations`)
  ).json();
  const convo = await (
    await request.get(
      `/api/v1/cases/${c.case_id}/assistant/conversations/${data.items[0].conversation_id}`,
    )
  ).json();
  const shown = convo.messages
    .at(-1)
    .providers.flatMap(
      (p: { plans: { pricing: { monthly_aud: number } }[] }) => p.plans,
    );
  expect(
    shown.every(
      (p: { pricing: { monthly_aud: number } }) => p.pricing.monthly_aud <= 80,
    ),
  ).toBe(true);
  expect(
    (
      await (
        await request.get(`/api/v1/cases/${c.case_id}/living-services`)
      ).json()
    ).version,
  ).toBe(0);
  await page.screenshot({
    path: "/tmp/utility-plans-chat.png",
    fullPage: true,
  });
});

test("tariff and eligibility cards fit mobile", async ({ page, request }) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/cases/${c.case_id}/aftercare?tab=utilities`);
  const energy = page.locator('.living-provider-card[data-provider-id="agl"]');
  await energy.click();
  const details = page.getByRole("dialog", {
    name: "AGL · 供应商详情",
    exact: true,
  });
  await details.locator(".utility-plan-details > summary").first().click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(details).toContainText("优惠前基准费率");
  await page.screenshot({
    path: "/tmp/utility-plans-mobile.png",
    animations: "disabled",
    fullPage: false,
  });
  await page.keyboard.press("Escape");
  await expect(details).toHaveCount(0);
  await expect(energy).toBeFocused();
});
