import { test, expect } from "@playwright/test";

async function fixture(
  page: import("@playwright/test").Page,
  request: import("@playwright/test").APIRequestContext,
  count: number,
) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const listings = (
    await (await request.get("/api/v1/listings?page_size=100")).json()
  ).items.slice(0, count);
  const conversation = {
    conversation_id: "full-housing",
    case_id: c.case_id,
    title: "完整房源",
    revision: 1,
    messages: [
      {
        message_id: "old-results",
        role: "assistant",
        agent: "agent2",
        intent: "search",
        created_at: "2026-10-28T00:00:00Z",
        content: `按这些条件找到 ${count} 条房源，先给你看 5 条。\n这是房源标价预览，偏好尚未修改；在租状态、账单和计价对象仍需核实。`,
        listings,
        actions: [],
      },
    ],
  };
  await page.route(`**/api/v1/cases/${c.case_id}/assistant/**`, (route) =>
    route.fulfill({
      json: route.request().url().endsWith("/conversations")
        ? {
            items: [
              {
                ...conversation,
                message_count: 1,
                updated_at: "2026-10-28T00:00:00Z",
              },
            ],
          }
        : conversation,
    }),
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  return { c, listings };
}

test("thirteen matching homes are all displayed without availability or billing footers", async ({
  page,
  request,
}) => {
  const { listings } = await fixture(page, request, 13);
  await expect(page.locator(".assistant-listing")).toHaveCount(13);
  await expect(
    page.getByRole("log", { name: "Rental conversation" }),
  ).not.toContainText("showing you");
  for (const text of [
    "在租状态",
    "账单",
    "Pricing basis",
    "待核实",
    "仍需核实",
  ])
    await expect(
      page.getByRole("log", { name: "Rental conversation" }),
    ).not.toContainText(text);
  await page
    .locator(".assistant-listing")
    .last()
    .getByRole("button", { name: "Listing details", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(listings[12].address);
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Collapse listings", exact: true })
    .click();
  await expect(page.locator(".assistant-listing")).toHaveCount(0);
  await page
    .getByRole("button", { name: "View all 13 listings", exact: true })
    .click();
  await expect(page.locator(".assistant-listing")).toHaveCount(13);
});

test("large results expand from a compact all-homes button and every page remains accessible", async ({
  page,
  request,
}) => {
  const { listings } = await fixture(page, request, 41);
  await expect(page.locator(".assistant-listing")).toHaveCount(0);
  await page
    .getByRole("button", { name: "View all 41 listings", exact: true })
    .click();
  await expect(page.locator(".assistant-listing")).toHaveCount(20);
  await page
    .getByRole("navigation", { name: "Filtered listing pages" })
    .getByTitle("3", { exact: true })
    .click();
  await expect(page.locator(".assistant-listing")).toHaveCount(1);
  await expect(page.locator(".assistant-listing h3")).toHaveText(
    listings[40].address,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
