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
    name: "Telstra · Provider details",
    exact: true,
  });
  await expect(telstraDetails).toContainText("AUD 89/month");
  await expect(telstraDetails).toContainText(
    "First 6 months AUD 69/month; then AUD 99/month",
  );
  const plan = telstraDetails.locator('[data-plan-id="telstra-essential"]');
  await plan
    .getByText("Pricing details and eligibility", { exact: true })
    .click();
  await expect(plan).toContainText("2026-11-02");
  await expect(plan).toContainText("AUD360");
  await expect(
    plan.getByRole("link", { name: "Official plans and rates ↗" }),
  ).toHaveAttribute("href", "https://www.telstra.com.au/internet/plans");
  await telstraDetails
    .getByRole("button", { name: "Close details", exact: true })
    .click();
  await expect(telstraDetails).toHaveCount(0);
  const water = page.locator(
    '.living-provider-card[data-provider-id="sydney-water"]',
  );
  await water.click();
  const waterDetails = page.getByRole("dialog", {
    name: "Sydney Water · Provider details",
    exact: true,
  });
  await expect(waterDetails).toContainText("AUD 3.41/kL");
  await expect(waterDetails).toContainText("Landlord fixed-charge reference");
  await waterDetails
    .getByText("Pricing details and eligibility", { exact: true })
    .click();
  await expect(
    waterDetails.getByRole("link", {
      name: "NSW utility cost responsibilities ↗",
    }),
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
    .getByRole("textbox", { name: "Message to Rental Assistant" })
    .fill("推荐每月80以内的网络套餐");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.locator(".assistant-message-assistant .assistant-bubble").last(),
  ).toContainText("ongoing monthly fee after promotions");
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
    name: "AGL · Provider details",
    exact: true,
  });
  await details.locator(".utility-plan-details > summary").first().click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect(details).toContainText(
    "baseline rates below include GST, before discounts",
  );
  await page.screenshot({
    path: "/tmp/utility-plans-mobile.png",
    animations: "disabled",
    fullPage: false,
  });
  await page.keyboard.press("Escape");
  await expect(details).toHaveCount(0);
  await expect(energy).toBeFocused();
});
