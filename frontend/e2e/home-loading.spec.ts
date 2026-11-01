import { expect, test } from "@playwright/test";

test("home edits survive a slower initial provider-directory load", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/living-providers", async (route) => {
    await pending;
    await route.continue();
  });
  try {
    await page.goto(`/cases/${c.case_id}/aftercare`, {
      waitUntil: "domcontentloaded",
    });
    await page.getByRole("button", { name: "My home", exact: true }).click();
    const home = page.getByRole("dialog", { name: "My home", exact: true });
    await home
      .getByRole("button", { name: "Edit details", exact: true })
      .click();
    await home
      .getByLabel("Address", { exact: true })
      .fill("Fictional unsaved home");
    release();
    await expect(
      page.getByRole("button", { name: "In progress (0)", exact: true }),
    ).toBeEnabled();
    await expect(home.getByLabel("Address", { exact: true })).toHaveValue(
      "Fictional unsaved home",
    );
    expect(
      (
        await (
          await request.get(`/api/v1/cases/${c.case_id}/living-services`)
        ).json()
      ).profile.address,
    ).toBe("");
  } finally {
    release();
  }
});
