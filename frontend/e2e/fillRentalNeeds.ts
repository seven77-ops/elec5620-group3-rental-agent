import { expect, type Page } from "@playwright/test";

export async function fillRentalNeeds(
  page: Page,
  {
    suburb = "Any area",
    budget = 1000,
    bedrooms = 0,
    bathrooms = 0,
    parking = 0,
  } = {},
) {
  const drawer = page.getByRole("dialog", {
    name: "My rental needs",
    exact: true,
  });
  await expect(drawer).toBeVisible();
  await drawer.getByLabel("Preferred area", { exact: true }).click();
  await page.getByRole("option", { name: suburb, exact: true }).click();
  await drawer
    .getByLabel("Maximum budget (AUD)", { exact: true })
    .fill(String(budget));
  for (const [field, choice] of [
    ["Budget period", "Weekly"],
    ["Pricing basis", "Whole property"],
    ["Rental type", "Whole property"],
  ]) {
    const control = drawer.getByLabel(field, { exact: true });
    await control.click();
    const options = await control.getAttribute("aria-controls");
    expect(options).toBeTruthy();
    await page.locator(`[id="${options}"]`).getByRole("option", { name: choice, exact: true }).click();
  }
  for (const [field, value] of [
    ["Number of occupants", 1],
    ["Minimum bedrooms", bedrooms],
    ["Minimum bathrooms", bathrooms],
    ["Minimum car spaces", parking],
  ] as const) {
    await drawer
      .getByRole("spinbutton", { name: field, exact: true })
      .fill(String(value));
  }
  return drawer;
}

export async function confirmRentalNeeds(page: Page) {
  const drawer = page.getByRole("dialog", {
    name: "My rental needs",
    exact: true,
  });
  await drawer
    .getByRole("button", { name: "Save rental needs", exact: true })
    .click();
  await expect(drawer).not.toBeVisible();
}
