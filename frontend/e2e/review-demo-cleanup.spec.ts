import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
const examples = JSON.parse(
  readFileSync(
    resolve(process.cwd(), "../server/app/adapters/review_examples.json"),
    "utf8",
  ),
);

test("five varied demo reviews are labelled and read-only in History", async ({
  page,
}) => {
  await page.route("**/api/v1/operator/reviews", (route) =>
    route.fulfill({ json: { items: examples, pending_count: 0 } }),
  );
  await page.goto("/operator");
  await expect(
    page.getByRole("tab", { name: "Pending (0)", exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "History (5)", exact: true }).click();
  const history = page.getByRole("region", {
    name: "Review history",
    exact: true,
  });
  const cards = history.getByTestId("operator-review");
  await expect(cards).toHaveCount(5);
  for (const example of examples) {
    const card = cards.filter({ hasText: example.reason });
    await expect(card).toContainText("Demo example");
    await expect(card).toContainText(example.decisions[0].note);
    await expect(card.getByRole("button")).toHaveCount(0);
  }
  await expect(history).not.toContainText(/\p{Script=Han}/u);
});

test("legacy recommendation context permits filtering and stops showing the upgrade error", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.route(
    `**/api/v1/cases/${c.case_id}/recommendation-context`,
    (route) =>
      route.fulfill({
        json: {
          filters: { sort: "rent_asc", suburb: "Rhodes", min_bedrooms: 2 },
          profile_version: 1,
          legacy_read_only: true,
          mapping_policy: "test",
          unverified_preferences: [],
        },
      }),
  );
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(page.getByTestId("real-catalog")).toContainText(
    /Filtered results · \d+ records/,
  );
  await expect(
    page.getByText("Browsing an earlier case", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Apply filters", exact: true }),
  ).toBeEnabled();
  await page
    .getByLabel("Maximum weekly rent (AUD)", { exact: true })
    .fill("1500");
  const done = page.waitForResponse(
    (r) =>
      r.url().includes("/api/v1/listings?") &&
      r.url().includes("max_weekly_rent=1500"),
  );
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  expect((await done).ok()).toBeTruthy();
  await expect(page.getByTestId("real-catalog")).not.toContainText(
    "Loading records",
  );
  await expect(
    page
      .getByRole("button", { name: "Select and follow up", exact: true })
      .first(),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Start a new search", exact: true })
    .click();
  await expect(page).toHaveURL(/\/assistant\?needs=1/);
});

test("a failed recommendation context cannot leave a permanent loading spinner", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.route(
    `**/api/v1/cases/${c.case_id}/recommendation-context`,
    (route) =>
      route.fulfill({
        status: 503,
        json: {
          error: {
            code: "context_unavailable",
            message: "Context temporarily unavailable",
          },
        },
      }),
  );
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(
    page.getByText("Context temporarily unavailable", { exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("real-catalog")).toContainText(
    "Could not load records",
  );
  await expect(
    page.getByRole("button", { name: "Apply filters", exact: true }),
  ).toBeEnabled();
});
