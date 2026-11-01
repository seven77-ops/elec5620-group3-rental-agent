import { test, expect, type APIRequestContext } from "@playwright/test";
async function seed(request: APIRequestContext, conversation = true) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  const confirmed = await request.post(root + "/profile-confirmations", {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  expect(confirmed.ok()).toBeTruthy();
  const run = await (
    await request.post(root + "/evaluations", {
      data: { request_id: "header-eval", confirmation_version: 1 },
    })
  ).json();
  const row = run.report.pending_confirmation[0];
  expect(
    (
      await request.post(root + "/selections", {
        data: {
          request_id: "header-select",
          run_id: run.run_id,
          listing_id: row.listing_id,
          confirmed: true,
        },
      })
    ).ok(),
  ).toBeTruthy();
  if (conversation) {
    const chat = await (
      await request.post(root + "/assistant/conversations", { data: {} })
    ).json();
    expect(
      (
        await request.post(
          root + `/assistant/conversations/${chat.conversation_id}/messages`,
          {
            data: {
              request_id: "header-search",
              expected_revision: 0,
              message: "Find matching properties.",
              allow_external_ai: true,
            },
          },
        )
      ).ok(),
    ).toBeTruthy();
  }
  return { c, row };
}
for (const width of [1440, 390]) {
  test(`selected property and contact action share the criteria area at ${width}px`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const { c, row } = await seed(request);
    await page.goto(`/cases/${c.case_id}/assistant`);
    const criteria = page.getByRole("region", {
      name: "Current housing criteria",
      exact: true,
    });
    await expect(criteria).toContainText(row.address);
    await expect(
      criteria.getByRole("button", {
        name: "Contact property agent",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page
        .locator(".assistant-workspace")
        .getByRole("button", { name: "Generate lease draft", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.locator(".assistant-workspace").getByRole("button", {
        name: "Review an existing contract",
        exact: true,
      }),
    ).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await page.screenshot({ path: `/tmp/rental-selected-header-${width}.png` });
    await criteria
      .getByRole("button", { name: "Contact property agent", exact: true })
      .click();
    const drawer = page.getByRole("dialog", {
      name: "Contact property agent",
      exact: true,
    });
    await expect(drawer).toContainText(row.address);
    await drawer.getByRole("button", { name: "Close", exact: true }).click();
    if (width < 600)
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
    await page
      .getByRole("menuitem", { name: "Contract assistant", exact: true })
      .click();
    await expect(
      page.getByRole("tab", { name: "Generate lease draft", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByLabel("Property address", { exact: true }),
    ).toHaveValue(row.address);
  });
}
test("selected property remains accessible before a conversation has housing filters", async ({
  page,
  request,
}) => {
  const { c, row } = await seed(request, false);
  await page.goto(`/cases/${c.case_id}/assistant`);
  const criteria = page.getByRole("region", {
    name: "Current housing criteria",
    exact: true,
  });
  await expect(criteria).toContainText(row.address);
  await expect(
    criteria.getByRole("button", {
      name: "Contact property agent",
      exact: true,
    }),
  ).toBeVisible();
});
