import { expect, test } from "@playwright/test";

test("case progress is absent from desktop and mobile navigation and old URLs resume the same case", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  const saved = await (await request.get(root)).json();
  const progress = await (await request.get(`${root}/progress`)).json();
  const pageProgressCalls: string[] = [];
  page.on("request", (req) => {
    if (req.url().endsWith(`${root}/progress`))
      pageProgressCalls.push(req.url());
  });
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(
    page.getByRole("heading", { name: "AI rental assistant", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("menuitem", { name: "Case progress", exact: true }),
  ).toHaveCount(0, { timeout: 1000 });
  await page.goto(`/cases/${c.case_id}/progress`);
  await expect(page).toHaveURL(new RegExp(`/cases/${c.case_id}/assistant$`));
  await expect(
    page.getByRole("heading", { name: "AI rental assistant", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".case-progress,.progress-steps")).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "AI rental assistant", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  const drawer = page.getByRole("dialog", {
    name: "Rental Assistant navigation",
    exact: true,
  });
  await expect(
    drawer.getByRole("menuitem", { name: "Human review", exact: true }),
  ).toBeVisible();
  await expect(
    drawer.getByRole("menuitem", { name: "Case progress", exact: true }),
  ).toHaveCount(0);
  expect(pageProgressCalls).toEqual([]);
  expect(await (await request.get(root)).json()).toEqual(saved);
  expect(await (await request.get(`${root}/progress`)).json()).toEqual(
    progress,
  );
});
