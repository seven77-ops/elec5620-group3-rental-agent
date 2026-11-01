import { expect, test, type Locator } from "@playwright/test";

async function expectColumns(cards: Locator, columns: 1 | 2) {
  await expect(cards).toHaveCount(2);
  const [first, second] = await cards.evaluateAll((elements) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect();
      return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
    }),
  );
  expect(Math.abs(first.width - second.width)).toBeLessThan(1);
  if (columns === 2) {
    expect(Math.abs(first.y - second.y)).toBeLessThan(1);
    expect(second.x).toBeGreaterThan(first.x + first.width);
  } else {
    expect(Math.abs(first.x - second.x)).toBeLessThan(1);
    expect(second.y).toBeGreaterThanOrEqual(first.y + first.height);
  }
  for (const card of await cards.all()) {
    const bounds = (await card.boundingBox())!;
    for (const button of await card
      .locator(".listing-card-actions button")
      .all()) {
      const box = (await button.boundingBox())!;
      expect(box.x).toBeGreaterThanOrEqual(bounds.x);
      expect(box.x + box.width).toBeLessThanOrEqual(
        bounds.x + bounds.width + 1,
      );
    }
  }
}

test("ordinary and commute chat listings share two columns on desktop and one on mobile", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const listings = (
    await (await request.get("/api/v1/listings?page_size=2")).json()
  ).items;
  const base = {
    role: "assistant",
    agent: "agent2",
    created_at: "2026-10-31T00:00:00Z",
    actions: [],
    recommendation_criteria: { budget_amount: 1200, budget_period: "week", budget_scope: "whole_property", min_bedrooms: 1, min_bathrooms: 1 },
    listings,
  };
  const conversation = {
    conversation_id: "grid-test",
    case_id: c.case_id,
    title: "Housing grid",
    revision: 1,
    messages: [
      {
        ...base,
        message_id: "ordinary",
        content: "Properties matching your housing needs.",
      },
      {
        ...base,
        message_id: "commute",
        content: "Properties matching your commute needs.",
        commute_recommendation: {
          status: "ready",
          destination: {
            id: "usyd:camperdown-darlington:fisher-library",
            label: "USYD main campus",
          },
          criteria: {
            commute_mode: "public_transport",
            commute_max_minutes: 50,
          },
          areas: [],
          routes: [],
        },
      },
    ],
  };
  await page.route(`**/api/v1/cases/${c.case_id}/assistant/**`, (route) =>
    route.fulfill({
      json: new URL(route.request().url()).pathname.endsWith("/conversations")
        ? {
            items: [
              {
                conversation_id: conversation.conversation_id,
                title: conversation.title,
                updated_at: base.created_at,
                message_count: 2,
              },
            ],
          }
        : conversation,
    }),
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  const ordinary = page.locator(".assistant-listings > .assistant-listing");
  const commute = page.locator(".commute-homes > .commute-home");
  await expectColumns(ordinary, 2);
  await expectColumns(commute, 2);
  for (const cards of [ordinary, commute]) {
    await expect(cards.locator(".recommendation-reasons")).toHaveCount(0);
    await expect(cards).not.toContainText(["Below budget", "meets your layout needs"]);
    await expect(cards.nth(0)).toContainText(listings[0].address);
    await expect(cards.nth(1)).toContainText(listings[1].address);
    await expect(
      cards
        .nth(0)
        .getByRole("button", { name: "Listing details", exact: true }),
    ).toBeVisible();
    await expect(
      cards.nth(0).getByRole("button", { name: "Save listing", exact: true }),
    ).toBeVisible();
    await expect(
      cards
        .nth(0)
        .getByRole("button", { name: "Select and follow up", exact: true }),
    ).toBeVisible();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await expectColumns(ordinary, 1);
  await expectColumns(commute, 1);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
