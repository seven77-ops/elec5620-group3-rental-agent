import { expect, test } from "@playwright/test";

test("all 24 moving and cleaning companies are shown and new quotes remain durable on mobile", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=services`);
  await expect(page.locator(".living-provider-card")).toHaveCount(24);
  const men = page.locator('[data-provider-id="men-that-move"]');
  await expect(men).not.toContainText("1800 438 668");
  await men.click();
  const details = page.getByRole("dialog", {
    name: "Men That Move · Provider details",
    exact: true,
  });
  await expect(details).toContainText("furniture and residential moving");
  await expect(
    details.getByRole("link", { name: "Company website", exact: true }),
  ).toHaveAttribute("href", "https://menthatmove.com/");
  await details
    .getByRole("button", { name: "Record quote or booking", exact: true })
    .hover();
  await page.screenshot({
    path: "/tmp/service-directory-expanded-desktop.png",
    fullPage: false,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await details
    .getByRole("button", { name: "Record quote or booking", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("spinbutton", { name: "Quote received (AUD)", exact: true })
    .fill("250");
  await dialog
    .getByRole("checkbox", {
      name: "I confirm this only saves a record and does not submit a booking to the provider.",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("button", { name: "Confirm service record", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("AUD 250", { exact: true })).toBeVisible();
  const saved = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(saved.bookings[0].provider_id).toBe("men-that-move");
  const last = page.locator('[data-provider-id="clean-australia"]');
  await last.click();
  const cleaningDetails = page.getByRole("dialog", {
    name: "Clean Australia Service · Provider details",
    exact: true,
  });
  await expect(cleaningDetails).toBeVisible();
  await expect(cleaningDetails).toBeInViewport();
  await expect(cleaningDetails).toContainText("house, apartment, end-of-lease");
  await expect(cleaningDetails.getByRole("link")).toHaveCount(1);
  await cleaningDetails
    .getByRole("button", { name: "Close details", exact: true })
    .hover();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/service-directory-expanded-mobile.png",
    fullPage: false,
    animations: "disabled",
  });
});

test("AI moving and cleaning replies use all twelve sourced companies in each category", async ({
  page,
  request,
}) => {
  for (const query of ["多推荐一些搬家公司", "多推荐一些退租清洁公司"]) {
    const c = await (await request.post("/api/v1/cases", { data: {} })).json();
    await page.goto(`/cases/${c.case_id}/assistant`);
    await page
      .getByRole("textbox", { name: "Message to Rental Assistant" })
      .fill(query);
    await page
      .getByRole("button", { name: "Send message", exact: true })
      .click();
    await expect(
      page.locator(".assistant-listing[data-provider-id]"),
    ).toHaveCount(12);
    const id = query.includes("搬家") ? "men-that-move" : "this-is-neat";
    await expect(
      page.locator(`.assistant-listing[data-provider-id="${id}"]`),
    ).toBeVisible();
    const state = await (
      await request.get(`/api/v1/cases/${c.case_id}/living-services`)
    ).json();
    expect(state.bookings).toHaveLength(0);
  }
});
