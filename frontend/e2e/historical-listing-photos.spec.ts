import { test, expect } from "@playwright/test";

for (const hasOrigin of [true, false]) {
  test(`old chat details load current photos with existing origin=${hasOrigin}`, async ({ page, request }) => {
    const rentalCase = await (await request.post("/api/v1/cases", { data: {} })).json();
    const fresh = await (await request.get("/api/v1/listings/domain%3A10908712")).json();
    expect(fresh.photos.length).toBeGreaterThan(0);
    expect(fresh.usyd_commute.origin).toBeTruthy();
    const older = {
      ...fresh,
      photos: [],
      weekly_rent: 1111,
      usyd_commute: {
        ...fresh.usyd_commute,
        origin: hasOrigin ? fresh.usyd_commute.origin : null,
        modes: {
          ...fresh.usyd_commute.modes,
          public_transport: {
            ...fresh.usyd_commute.modes.public_transport,
            status: "planned",
            basis: "recent_checked_query",
            duration_minutes: 7,
            queried_at: new Date().toISOString(),
          },
        },
      },
    };
    const conversation = {
      conversation_id: "older-housing-photos",
      case_id: rentalCase.case_id,
      title: "原有租房对话",
      revision: 1,
      messages: [{
        message_id: "older-property-result", role: "assistant", agent: "agent2",
        intent: "search", created_at: "2026-10-24T00:00:00Z",
        content: "这是之前找到的房源。", listings: [older], actions: [],
      }],
    };
    let writes = 0;
    await page.route(`**/api/v1/cases/${rentalCase.case_id}/assistant/**`, async route => {
      if (route.request().method() !== "GET") writes++;
      await route.fulfill({ json: route.request().url().endsWith("/conversations")
        ? { items: [{ conversation_id: conversation.conversation_id, title: conversation.title,
            updated_at: "2026-10-24T00:00:00Z", message_count: 1 }] }
        : conversation });
    });
    await page.goto(`/cases/${rentalCase.case_id}/assistant`);
    await page.getByRole("button", { name: "Listing details", exact: true }).click();
    const drawer = page.getByRole("dialog");
    const photo = drawer.locator(".listing-photo-gallery img").first();
    await expect(photo).toHaveAttribute("src", fresh.photos[0].url);
    await expect.poll(() => photo.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0)).toBeTruthy();
    await expect(drawer.getByTestId("listing-detail-rent")).toContainText("1,111");
    await expect(drawer.locator(".usyd-mode-grid > div").filter({ has: page.getByText("Public transport", { exact: true }) }))
      .toContainText(/Approx\.\s*7\s*minutes/);
    await expect(drawer.getByRole("link", { name: "Photo source", exact: true }))
      .toHaveAttribute("href", fresh.photos[0].photo_source_url ?? fresh.source_url);
    expect(writes).toBe(0);
    expect(conversation.messages[0].listings[0].photos).toEqual([]);
  });
}
