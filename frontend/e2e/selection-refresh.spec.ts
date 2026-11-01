import { test, expect } from "@playwright/test";

test("an over-limit historical card explains the mismatch without locking chat or favorites", async ({
  page,
  request,
}) => {
  let c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  const conversation = await (
    await request.post(root + "/assistant/conversations", { data: {} })
  ).json();
  const search = await request.post(
    root + `/assistant/conversations/${conversation.conversation_id}/messages`,
    {
      data: {
        request_id: "old-search",
        expected_revision: 0,
        message: "找Rhodes的两卧房源",
        allow_external_ai: true,
      },
    },
  );
  expect(search.status()).toBe(200);
  const rows = (await search.json()).messages.at(-1).listings;
  const row = rows.find(
    (item: any) =>
      item.usyd_commute?.modes?.public_transport?.duration_minutes > 30,
  );
  expect(row).toBeTruthy();
  c = await (
    await request.post(root + "/profile-drafts", {
      data: {
        expected_revision: c.draft.revision,
        profile: {
          ...c.draft.profile,
          budget: {
            currency: "AUD",
            period: "week",
            scope: "whole_property",
            maximum: 1500,
          },
          housing_preferences: {
            suburb: "Rhodes",
            min_bedrooms: 2,
            min_bathrooms: 2,
            min_car_spaces: 1,
          },
          student_commute: { mode: "public_transport", maximum_minutes: 30 },
        },
      },
    })
  ).json();
  expect(
    (
      await request.post(root + "/profile-confirmations", {
        data: {
          draft_revision: c.draft.revision,
          fingerprint: c.draft.fingerprint,
          review_token: c.agent1.review_token,
        },
      })
    ).status(),
  ).toBe(200);
  await page.goto(`/cases/${c.case_id}/assistant`);
  const card = page.locator(`[data-listing-id="${row.listing_id}"]`);
  await card
    .getByRole("button", { name: "Select and follow up", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm and start follow-up", exact: true })
    .click();
  const warning = page
    .getByRole("alert")
    .filter({ hasText: "This listing does not match your current filters" });
  await expect(warning).toContainText(/exceed(?:s|ing) your 30-minute limit/);
  await expect(warning).not.toContainText("Campus arrival time");
  await expect(
    page.getByRole("button", { name: "Retry original action", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("textbox", { name: "Message to Rental Assistant" }),
  ).toBeEnabled();
  await expect(
    card.getByRole("button", { name: "Save listing", exact: true }),
  ).toBeEnabled();
  await page.screenshot({
    path: "/tmp/selection-mismatch-warning.png",
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/selection-mismatch-mobile.png",
    animations: "disabled",
  });
  await card.getByRole("button", { name: "Save listing", exact: true }).click();
  await expect(
    card.getByRole("button", { name: "Remove favorite", exact: true }),
  ).toBeVisible();
  expect((await (await request.get(root)).json()).selection).toBeNull();
  await warning
    .getByRole("button", { name: "Adjust rental needs", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "My rental needs", exact: true }),
  ).toBeVisible();
});

test("legacy arrival deadlines do not affect approximate discovery or selecting a home", async ({
  page,
  request,
}) => {
  let c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  const row = (
    await (
      await request.get(
        "/api/v1/listings?usyd_mode=public_transport&usyd_max_minutes=30&page_size=20",
      )
    ).json()
  ).items[0];
  await request.post(root + "/favorites", {
    data: { request_id: "favorite", listing_id: row.listing_id, saved: true },
  });
  c = await (
    await request.post(root + "/profile-drafts", {
      data: {
        expected_revision: c.draft.revision,
        profile: {
          ...c.draft.profile,
          student_commute: {
            mode: "public_transport",
            maximum_minutes: 30,
            arrival_time: "03:17",
            travel_day: "weekend",
            travel_date: "2000-01-01",
          },
        },
      },
    })
  ).json();
  expect(
    (
      await request.post(root + "/profile-confirmations", {
        data: {
          draft_revision: c.draft.revision,
          fingerprint: c.draft.fingerprint,
          review_token: c.agent1.review_token,
        },
      })
    ).status(),
  ).toBe(200);
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByRole("button", { name: "My rental needs", exact: true })
    .click();
  const needs = page.getByRole("dialog", {
    name: "My rental needs",
    exact: true,
  });
  await expect(needs).not.toContainText("03:17");
  await expect(
    needs.getByRole("button", {
      name: "No fixed campus arrival time",
      exact: true,
    }),
  ).toHaveCount(0);
  await needs.getByRole("button", { name: "Close", exact: true }).click();
  await page
    .getByRole("button", { name: "My favorites (1)", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Select and follow up", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "Select this property and start follow-up?",
    exact: true,
  });
  await expect(modal).toContainText("Commute uses approximate duration");
  await expect(modal).not.toContainText("03:17");
  await modal
    .getByRole("button", { name: "Confirm and start follow-up", exact: true })
    .click();
  await expect(page.getByTestId("candidate-next")).toContainText(row.address);
  const state = await (await request.get(root)).json();
  expect(state.selection.listing_id).toBe(row.listing_id);
  expect(state.confirmations[0].profile.student_commute.arrival_time).toBe(
    "03:17",
  );
  await page.reload();
  await expect(page.getByTestId("candidate-next")).toContainText(row.address);
  await page
    .getByRole("menuitem", { name: "Housing recommendations", exact: true })
    .click();
  const result = page.getByRole("heading", { name: /Filtered results/ });
  await expect(result).toContainText(/Filtered results.*\d+ records/);
  await expect(
    page.getByTestId("real-catalog").locator("tbody tr.ant-table-row").first(),
  ).toBeVisible();
  await page.screenshot({
    path: "/tmp/timeless-commute-desktop.png",
    animations: "disabled",
  });
});
