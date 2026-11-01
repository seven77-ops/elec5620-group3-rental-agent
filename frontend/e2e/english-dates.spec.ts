import { test, expect } from "@playwright/test";

test.use({ locale: "zh-CN" });

test("date fields remain English on a Chinese browser and save the original ISO service date", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const directory = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const provider = directory.providers.find((p: { categories: string[] }) =>
    p.categories.includes("removalist"),
  );
  await page.goto(`/cases/${c.case_id}/aftercare?tab=services`);
  await page.locator(`[data-provider-id="${provider.id}"]`).click();
  await page
    .getByRole("button", { name: "Record quote or booking", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: `Record · ${provider.name}`,
    exact: true,
  });
  const date = dialog.getByLabel("Service date", { exact: true });
  await expect(date).toHaveAttribute("placeholder", "DD/MM/YYYY");
  await expect(date).toHaveJSProperty("type", "text");
  await date.click();
  await expect(page.locator(".ant-picker-dropdown:visible")).not.toContainText(
    /\p{Script=Han}/u,
  );
  await date.press("Escape");
  // ISO input remains accepted for compatibility with existing forms and tests.
  await date.fill("2026-12-15");
  await date.press("Tab");
  await expect(date).toHaveValue("15/12/2026");
  await dialog
    .getByRole("textbox", { name: "Service notes", exact: true })
    .fill("用户原始备注，保留中文。");
  await dialog
    .getByRole("checkbox", {
      name: "I confirm this only saves a record and does not submit a booking to the provider.",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("button", { name: "Confirm service record", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const saved = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(saved.bookings[0].service_date).toBe("2026-12-15");
  expect(saved.bookings[0].notes).toBe("用户原始备注，保留中文。");
});

test("date bounds, clearing and local date/time string contracts survive the English control", async ({
  page,
}) => {
  await page.goto("/tests/english-date-input.html");
  const date = page.getByLabel("Bounded date", { exact: true });
  await expect(date).toHaveValue("16/11/2026");
  for (const outside of ["21/11/2026", "09/11/2026"]) {
    await date.fill(outside);
    await date.press("Enter");
    await page
      .getByRole("button", { name: "Outside field", exact: true })
      .click();
    await expect(page.getByTestId("date-value")).toHaveText("2026-11-16");
  }
  await date.fill("20/11/2026");
  await date.press("Enter");
  await expect(page.getByTestId("date-value")).toHaveText("2026-11-20");
  await date.hover();
  await page
    .locator(".ant-picker")
    .filter({ has: date })
    .getByRole("button", { name: "Clear", exact: true })
    .click();
  await expect(page.getByTestId("date-value")).toBeEmpty();
  const datetime = page.getByLabel("Local date and time", { exact: true });
  await datetime.fill("2026-11-17T14:45");
  await datetime.press("Enter");
  await page
    .getByRole("button", { name: "Outside field", exact: true })
    .click();
  await expect(page.getByTestId("datetime-value")).toHaveText(
    "2026-11-17T14:45",
  );
  const time = page.getByLabel("Time", { exact: true });
  await time.fill("15:25");
  await time.press("Enter");
  await page
    .getByRole("button", { name: "Outside field", exact: true })
    .click();
  await expect(page.getByTestId("time-value")).toHaveText("15:25");
  await expect(page.locator("body")).not.toContainText(/\p{Script=Han}/u);
});
