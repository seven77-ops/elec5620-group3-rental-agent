import { test, expect } from "@playwright/test";

const savedFilters = {
  suburb: "Burwood",
  min_bedrooms: 1,
  min_bathrooms: 1,
  min_car_spaces: 0,
  max_weekly_rent: 1000,
  usyd_mode: "public_transport",
  usyd_max_minutes: 50,
  usyd_max_transfers: 0,
  sort: "bedrooms_desc",
};

test("All areas removes only the area and Reset filters immediately restores the unrestricted catalogue", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const original = await (
    await request.get(`/api/v1/cases/${c.case_id}`)
  ).json();
  await page.route(
    `**/api/v1/cases/${c.case_id}/recommendation-context`,
    (route) =>
      route.fulfill({
        json: {
          filters: savedFilters,
          mapping_policy: "reset-test",
          unverified_preferences: [],
        },
      }),
  );
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(page.getByTestId("real-catalog")).toContainText(
    /Filtered results · \d+ records/,
  );
  await page
    .getByRole("combobox", { name: "Listing area", exact: true })
    .click();
  await page.getByRole("option", { name: "All areas", exact: true }).click();
  const areaResponse = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/listings?") &&
      !new URL(r.url()).searchParams.has("suburb") &&
      new URL(r.url()).searchParams.get("max_weekly_rent") === "1000",
  );
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  expect((await areaResponse).ok()).toBeTruthy();
  await expect(
    page.getByRole("button", { name: "Apply filters", exact: true }),
  ).toBeEnabled();
  const resetResponse = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/listings?") &&
      new URL(r.url()).searchParams.get("sort") === "rent_asc" &&
      !new URL(r.url()).searchParams.has("max_weekly_rent"),
  );
  await page
    .getByRole("button", { name: "Reset filters", exact: true })
    .click();
  const response = await resetResponse;
  expect(response.ok()).toBeTruthy();
  const query = new URL(response.url()).searchParams;
  expect([...query.keys()].sort()).toEqual([
    "case_id",
    "page",
    "page_size",
    "sort",
  ]);
  expect(query.get("page")).toBe("1");
  const full = await (await request.get("/api/v1/listings?page_size=1")).json();
  await expect(page.getByTestId("real-catalog")).toContainText(
    `Filtered results · ${full.total} records`,
  );
  for (const name of [
    "Minimum bedrooms",
    "Minimum bathrooms",
    "Minimum car spaces",
    "Maximum weekly rent (AUD)",
    "Maximum commute to USYD (minutes)",
  ])
    await expect(
      page.getByRole("spinbutton", { name, exact: true }),
    ).toHaveValue("");
  await expect(
    page.getByText("Filters have been edited. Apply the filters first.", {
      exact: true,
    }),
  ).toHaveCount(0);
  expect(
    await (await request.get(`/api/v1/cases/${c.case_id}`)).json(),
  ).toEqual(original);
  await page
    .getByRole("button", { name: "Restore preference filters", exact: true })
    .click();
  await expect(
    page.getByRole("spinbutton", {
      name: "Maximum weekly rent (AUD)",
      exact: true,
    }),
  ).toHaveValue("1000");
});

test("reset during preference loading is not overwritten by the delayed saved context", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  let release!: () => void;
  const ready = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    `**/api/v1/cases/${c.case_id}/recommendation-context`,
    async (route) => {
      await ready;
      await route.fulfill({
        json: {
          filters: savedFilters,
          mapping_policy: "reset-test",
          unverified_preferences: [],
        },
      });
    },
  );
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await page
    .getByRole("button", { name: "Reset filters", exact: true })
    .click();
  release();
  const full = await (await request.get("/api/v1/listings?page_size=1")).json();
  await expect(page.getByTestId("real-catalog")).toContainText(
    `Filtered results · ${full.total} records`,
  );
  await expect(
    page.getByRole("spinbutton", {
      name: "Maximum weekly rent (AUD)",
      exact: true,
    }),
  ).toHaveValue("");
});
