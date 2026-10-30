import { test, expect } from "@playwright/test";
import { fillRentalNeeds, confirmRentalNeeds } from "./fillRentalNeeds";

test("AI-collected needs prefill the panel and sync without retyping other conditions", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/assistant/conversations`;
  let conversation = await (await request.post(root, { data: {} })).json();
  for (const [index, message] of [
    "Rhodes 预算最高800 人数一人 要2b2b 车位无所谓",
    "整套，每周",
  ].entries()) {
    const response = await request.post(
      `${root}/${conversation.conversation_id}/messages`,
      {
        data: {
          request_id: `ui-intake-${index}`,
          expected_revision: conversation.revision,
          message,
          allow_external_ai: true,
        },
      },
    );
    expect(response.status()).toBe(200);
    conversation = await response.json();
  }
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByRole("button", { name: "My rental needs", exact: true })
    .click();
  const drawer = page.getByRole("dialog", {
    name: "My rental needs",
    exact: true,
  });
  await expect(
    drawer.getByRole("spinbutton", {
      name: "Maximum budget (AUD)",
      exact: true,
    }),
  ).toHaveValue("800");
  await expect(
    drawer.getByRole("spinbutton", { name: "Minimum bedrooms", exact: true }),
  ).toHaveValue("2");
  await expect(
    drawer.getByRole("spinbutton", { name: "Minimum bathrooms", exact: true }),
  ).toHaveValue("2");
  await expect(
    drawer.getByRole("spinbutton", { name: "Minimum car spaces", exact: true }),
  ).toHaveValue("0");
  await drawer
    .getByRole("spinbutton", { name: "Maximum budget (AUD)", exact: true })
    .fill("900");
  await drawer
    .getByRole("button", { name: "Save rental needs", exact: true })
    .click();
  await expect(page.getByTestId("assistant-needs-status")).toHaveCount(0);
  await expect(drawer).not.toBeVisible();
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.confirmations[0].profile.budget).toMatchObject({
    maximum: 900,
    scope: "whole_property",
  });
  expect(saved.confirmations[0].profile.housing_preferences).toMatchObject({
    suburb: "Rhodes",
    min_bedrooms: 2,
    min_bathrooms: 2,
    min_car_spaces: 0,
  });
  await page
    .getByRole("menuitem", { name: "Housing recommendations", exact: true })
    .click();
  await expect(
    page.getByRole("spinbutton", {
      name: "Maximum weekly rent (AUD)",
      exact: true,
    }),
  ).toHaveValue("900");
});

test("chat needs require confirmation, sync real recommendations and persist a selected card", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(
    page.getByRole("menuitem", { name: "Rental preferences", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "My rental needs", exact: true })
    .click();
  const drawer = page.getByRole("dialog", {
    name: "My rental needs",
    exact: true,
  });
  await drawer.getByLabel("Preferred area", { exact: true }).click();
  await drawer.getByLabel("Preferred area", { exact: true }).fill("Rhodes");
  await page.getByRole("option", { name: "Rhodes", exact: true }).click();
  await drawer
    .getByRole("spinbutton", { name: "Maximum budget (AUD)", exact: true })
    .fill("1500");
  await drawer.getByLabel("Budget period", { exact: true }).click();
  await page.getByRole("option", { name: "Weekly", exact: true }).click();
  await drawer.getByLabel("Pricing basis", { exact: true }).click();
  await page
    .locator("#chat-rental-needs_budget_scope_list")
    .getByRole("option", { name: "Whole property", exact: true })
    .click();
  await drawer.getByLabel("Rental type", { exact: true }).click();
  await page
    .locator("#chat-rental-needs_rental_mode_list")
    .getByRole("option", { name: "Whole property", exact: true })
    .click();
  await drawer
    .getByRole("spinbutton", { name: "Number of occupants", exact: true })
    .fill("1");
  await drawer
    .getByRole("spinbutton", { name: "Minimum bedrooms", exact: true })
    .fill("2");
  await drawer
    .getByRole("spinbutton", { name: "Minimum bathrooms", exact: true })
    .fill("2");
  await drawer
    .getByRole("spinbutton", { name: "Minimum car spaces", exact: true })
    .fill("1");
  await drawer
    .getByRole("button", { name: "Save rental needs", exact: true })
    .click();
  await expect(drawer).not.toBeVisible();
  await expect(page.getByTestId("assistant-needs-status")).toHaveCount(0);
  const card = page.locator(".assistant-listing").first();
  await expect(card).toBeVisible();
  const address = await card.locator("h3").innerText();
  await card
    .getByRole("button", { name: "Select and follow up", exact: true })
    .click();
  await page
    .getByRole("dialog", {
      name: "Select this property and start follow-up?",
      exact: true,
    })
    .getByRole("button", { name: "Confirm and start follow-up", exact: true })
    .click();
  await expect(
    card.getByText("Current follow-up property", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page
      .locator(".assistant-listing")
      .first()
      .getByText("Current follow-up property", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("menuitem", { name: "Housing recommendations", exact: true })
    .click();
  await expect(page.getByText(address, { exact: true }).first()).toBeVisible();
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.confirmations.at(-1).version).toBe(1);
  expect(saved.selection.listing_snapshot.address).toBe(address);
  expect(saved.confirmations[0].profile.housing_preferences).toMatchObject({
    suburb: "Rhodes",
    min_bedrooms: 2,
    min_bathrooms: 2,
    min_car_spaces: 1,
  });
});

test("mobile chat keeps needs management inside the conversation page", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(`/cases/${c.case_id}/assistant?needs=1`);
  const drawer = page.getByRole("dialog", {
    name: "My rental needs",
    exact: true,
  });
  await expect(drawer).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await drawer.getByRole("button", { name: "Close", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Message to Rental Assistant" }),
  ).toBeVisible();
});

test("new needs remain blank and optional dates do not block saving a real budget", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  expect(c.draft.profile).toEqual({
    schema_version: "1.0",
    search_id: c.search_id,
    profile_version: 1,
  });
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByRole("button", { name: "My rental needs", exact: true })
    .click();
  const drawer = page.getByRole("dialog", {
    name: "My rental needs",
    exact: true,
  });
  await expect(
    drawer.getByRole("spinbutton", {
      name: "Maximum budget (AUD)",
      exact: true,
    }),
  ).toHaveValue("");
  await expect(
    drawer.getByRole("spinbutton", {
      name: "Number of occupants",
      exact: true,
    }),
  ).toHaveValue("");
  await expect(
    drawer.getByRole("spinbutton", { name: "Minimum bedrooms", exact: true }),
  ).toHaveValue("");
  await page.goto(`/cases/${c.case_id}/preferences`);
  await expect(page).toHaveURL(
    new RegExp(`/cases/${c.case_id}/assistant\\?needs=1$`),
  );
  await expect(
    page.getByRole("heading", { name: "Housing criteria", exact: true }),
  ).toHaveCount(0);
  const panel = await fillRentalNeeds(page, { budget: 1000 });
  for (const copy of [
    "AI 整理的条件",
    "数量填 0",
    "上课前到达时间",
    "Travel day",
    "记录你看重什么",
  ])
    await expect(panel).not.toContainText(copy);
  await expect(
    panel.getByRole("button", {
      name: "Other preferences and full settings",
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(
    panel.getByRole("button", {
      name: "View housing recommendations",
      exact: true,
    }),
  ).toHaveCount(0);
  await page.screenshot({ path: "/tmp/rental-needs-cleanup-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  await panel
    .getByRole("button", { name: "Save rental needs", exact: true })
    .scrollIntoViewIfNeeded();
  await expect
    .poll(async () => {
      const box = await panel.boundingBox();
      return !!box && box.x >= 0 && box.x + box.width <= 391;
    })
    .toBe(true);
  await page.screenshot({ path: "/tmp/rental-needs-cleanup-mobile.png" });
  await confirmRentalNeeds(page);
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.draft.profile.budget.maximum).toBe(1000);
  expect(saved.confirmations.at(-1).profile.budget.maximum).toBe(1000);
  expect(saved.draft.profile).not.toHaveProperty("commute");
  expect(saved.draft.profile).not.toHaveProperty("move_in_window");
  expect(saved.draft.profile).not.toHaveProperty("hard_requirements");
  expect(saved.draft.profile).not.toHaveProperty("soft_preferences");
});
