import { test, expect } from "@playwright/test";

test("soft preference evidence separates property claims, suburb facts and unknowns", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/e2e/fixtures/soft-preferences.html");
  const summary = page.getByRole("region", { name: "Soft preference ranking" });
  await expect(summary).toContainText("All 2 hard matches retained");
  await expect(summary).toContainText("1 / 2 matching suburbs");
  await expect(summary).toContainText("1 / 2 listings have evidence");
  await expect(summary).toContainText("Not established by this evidence: Quietness, Safety");
  const known = page.getByRole("region", { name: "Soft preference evidence for b" });
  await expect(known).toContainText("Unknown: Quietness, Safety");
  await expect(known.getByText("These sources do not verify property walking distance, quietness or safety.", { exact: true })).toBeVisible();
  await known.getByText("Sources and scope").click();
  await expect(known.getByRole("heading", { name: "Property advertisement claims" })).toBeVisible();
  await expect(known.getByRole("heading", { name: "Suburb facility context" })).toBeVisible();
  await expect(known.getByRole("link", { name: /Public advertisement/ })).toHaveAttribute("href", "https://www.domain.com.au/example-b");
  await expect(known.getByRole("link", { name: /Council/ })).toHaveAttribute("href", "https://example.org/council");
  await expect(known).toContainText("walking distance");
  await expect(known).toContainText("advertised:b:shopping");
  const unknown = page.getByRole("region", { name: "Soft preference evidence for c" });
  await expect(unknown).toContainText("Unknown: Shopping, Quietness, Safety");
  await expect(unknown).toContainText("not evidence that facilities are absent");
  await page.setViewportSize({ width: 360, height: 800 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
});
