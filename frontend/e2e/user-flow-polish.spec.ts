import { test, expect } from "@playwright/test";
test("recommendations header contains only the requested title and actions", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(page.locator(".page-heading")).toHaveText(
    "Housing recommendationsMy favorites (0)Find a home through chatMy rental needs",
  );
  await expect(page.locator(".case-caption")).toHaveCount(0);
  await expect(
    page.locator(".real-catalog-notes,.real-catalog-status,.demo-label"),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Apply filters", exact: true }),
  ).toBeVisible();
});
test("a chat turn sends directly and a whole-property reply advances the question", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(
    page.getByRole("checkbox", { name: /Allow this request to use external/i }),
  ).toHaveCount(0);
  const input = page.getByPlaceholder(
    "Describe your rental needs or ask a question…",
  );
  await input.fill("我想住Burwood预算1200每周");
  const first = page.waitForRequest(
    (r) => r.url().endsWith("/messages") && r.method() === "POST",
  );
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  expect((await first).postDataJSON()).toMatchObject({
    allow_external_ai: true,
  });
  const replies = page.locator(".assistant-message-assistant");
  await expect(replies.last()).toContainText("whole property, per room");
  await input.fill("Whole property");
  await input.press("Enter");
  await expect(replies.last()).toContainText("bedrooms");
  await expect(replies.last()).not.toContainText(
    "for the whole property, per room",
  );
  const list = await (
    await request.get(`/api/v1/cases/${c.case_id}/assistant/conversations`)
  ).json();
  const chat = await (
    await request.get(
      `/api/v1/cases/${c.case_id}/assistant/conversations/${list.items[0].conversation_id}`,
    )
  ).json();
  expect(chat.rental_brief.budget_scope).toBe("whole_property");
  expect(chat.rental_brief.budget_amount).toBe(1200);
});
test("contract entry explains the next step without requesting an invalid source", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  let contexts = 0;
  await page.route("**/lease-drafts/context", async (route) => {
    contexts++;
    await route.continue();
  });
  await page.goto(`/cases/${c.case_id}/contract`);
  await expect(
    page.getByText("Confirm your rental needs first", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".case-caption")).toHaveCount(0);
  await expect(
    page.getByText("Confirm the exact current saved draft before continuing", {
      exact: false,
    }),
  ).toHaveCount(0);
  await expect(
    page.getByText("unconfirmed_profile", { exact: false }),
  ).toHaveCount(0);
  expect(contexts).toBe(0);
  await page
    .getByRole("button", { name: "My rental needs", exact: true })
    .click();
  await expect(page).toHaveURL(/assistant\?needs=1$/);
});
test("aftercare keeps the heading and actions without decorative captions", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await expect(page.locator(".living-heading")).toHaveText(
    "Living and aftercare servicesLoad latest information",
  );
  await expect(page.locator(".case-caption,.living-eyebrow")).toHaveCount(0);
  await expect(
    page.getByText("Take care of daily life and prepare for what comes next.", {
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Edit home and contacts", exact: true }),
  ).toBeVisible();
});
test("technical error text is hidden until diagnostics are requested", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.route("**/lease-drafts", (route) =>
    route.fulfill({
      status: 503,
      json: {
        error: {
          code: "service_unavailable",
          message: "INTERNAL_BACKEND_DEBUG_MESSAGE",
          request_id: "error-test-internal",
        },
      },
    }),
  );
  await page.goto(`/cases/${c.case_id}/contract`);
  await expect(page.locator(".error-message")).toBeVisible();
  await expect(
    page.getByText("INTERNAL_BACKEND_DEBUG_MESSAGE", { exact: false }),
  ).toHaveCount(0);
  await expect(
    page.getByText("error-test-internal", { exact: false }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "View details", exact: true }).click();
  await expect(
    page.getByText("INTERNAL_BACKEND_DEBUG_MESSAGE", { exact: false }),
  ).toBeVisible();
});

test("aftercare initial load failure does not expose the backend message", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.route("**/living-services", (route) =>
    route.fulfill({
      status: 503,
      json: {
        error: {
          code: "service_unavailable",
          message: "INITIAL_LIVING_BACKEND_MESSAGE",
          request_id: "error-living-load",
        },
      },
    }),
  );
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await expect(
    page.getByText("Unable to complete this action", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("INITIAL_LIVING_BACKEND_MESSAGE", { exact: false }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Retry original action", exact: true }),
  ).toBeVisible();
});

for (const source of ["tenancy-source"] as const) {
  test(`aftercare ${source} errors stay readable`, async ({
    page,
    request,
  }) => {
    const c = await (await request.post("/api/v1/cases", { data: {} })).json();
    await page.route(`**/living-services/${source}`, (route) =>
      route.fulfill({
        status: 503,
        json: {
          error: {
            code: "service_unavailable",
            message: "RAW_LIVING_SERVICE_INTERNAL_ERROR",
            request_id: "error-living-subservice",
          },
        },
      }),
    );
    await page.goto(`/cases/${c.case_id}/aftercare`);
    if (source === "tenancy-source")
      await page
        .getByRole("button", { name: "View lease source", exact: true })
        .click();
    await expect(
      page.getByText("Unable to complete this action", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("RAW_LIVING_SERVICE_INTERNAL_ERROR", { exact: false }),
    ).toHaveCount(0);
  });
}
