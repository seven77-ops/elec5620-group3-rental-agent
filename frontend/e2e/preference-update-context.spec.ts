import { expect, test } from "@playwright/test";

test("a budget-only chat edit retains unconfirmed 2-bed 2-bath and public transport criteria when confirmed", async ({ page, request }) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  const chat = await (await request.post(`${root}/assistant/conversations`, { data: {} })).json();
  const url = `${root}/assistant/conversations/${chat.conversation_id}`;
  const brief = { suburb: null, budget_amount: 900, budget_period: "week", budget_scope: "whole_property",
    min_bedrooms: 2, min_bathrooms: 2, min_car_spaces: 0, occupants: 2, rental_mode: "whole_property",
    recommend_areas: true, commute_mode: "public_transport", commute_max_minutes: 50 };
  const prepared = await request.post(`${url}/proposals`, { data: {
    request_id: crypto.randomUUID(), expected_revision: 0, expected_profile_fingerprint: c.draft.fingerprint, brief,
  } });
  expect(prepared.ok(), await prepared.text()).toBeTruthy();
  await page.goto(`/cases/${c.case_id}/assistant`);
  const input = page.getByRole("textbox", { name: "Message to Rental Assistant", exact: true });
  await input.fill("Change only my maximum budget to AUD 1000 per week. Keep all my other requirements unchanged.");
  await input.press("Enter");
  const proposal = page.locator(".assistant-message-assistant").last();
  await expect(proposal).toContainText("Your updated rental requirements are ready.");
  await expect(proposal).toContainText("At least 2 bedrooms");
  await expect(proposal).toContainText("At least 2 bathrooms");
  await expect(proposal).toContainText("At most 50 minutes");
  expect((await (await request.get(root)).json()).draft).toEqual(c.draft);
  await proposal.getByRole("button", { name: "Save rental needs", exact: true }).click();
  const answer = page.locator(".assistant-message-assistant").last();
  await expect(answer).toContainText("Rental requirements saved");
  const current = await (await request.get(url)).json();
  const filters = current.messages.at(-1).recommendation_filters;
  expect(filters).toMatchObject({ max_weekly_rent: 1000, min_bedrooms: 2, min_bathrooms: 2,
    min_car_spaces: 0, usyd_mode: "public_transport", usyd_max_minutes: 50 });
  const expected = await (await request.get(`/api/v1/listings?case_id=${c.case_id}&max_weekly_rent=1000&min_bedrooms=2&min_bathrooms=2&min_car_spaces=0&usyd_mode=public_transport&usyd_max_minutes=50&page_size=100`)).json();
  expect(current.messages.at(-1).listings.length).toBe(expected.total);
  expect(expected.total).toBeGreaterThan(0);
  for (const row of current.messages.at(-1).listings) {
    expect(row.bedrooms).toBeGreaterThanOrEqual(2);
    expect(row.bathrooms).toBeGreaterThanOrEqual(2);
    expect(row.weekly_rent).toBeLessThanOrEqual(1000);
  }
  const controls = page.getByRole("region", { name: "Current housing criteria", exact: true });
  await expect(controls).toContainText("At least 2 bed · 2 bath");
  await expect(controls).toContainText("Public transport ≤50 minutes");
  await expect(controls).toContainText(`Filtered ${expected.total} properties`);
  await page.reload();
  await expect(page.locator(".assistant-message-assistant").last()).toContainText("Rental requirements saved");
  await expect(controls).toContainText(`Filtered ${expected.total} properties`);
});
