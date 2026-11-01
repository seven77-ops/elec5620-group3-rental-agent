import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";

async function seed(
  page: Page,
  request: APIRequestContext,
  choice = false,
  obsolete = false,
) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/assistant/conversations`;
  const conversation = await (await request.post(root, { data: {} })).json();
  const catalogue = await (
    await request.get("/api/v1/listings?page=1&page_size=2")
  ).json();
  expect(catalogue.items).toHaveLength(2);
  const message = {
    message_id: "layout-message",
    role: "assistant",
    agent: "agent1",
    intent: "collect_preferences",
    content: choice
      ? "Would you like to include a commute filter?"
      : "Here are matching listings.",
    created_at: "2026-10-31T10:00:00Z",
    listings: choice ? [] : catalogue.items,
    actions: [],
    ...(choice ? { commute_preference_question: true } : {}),
  };
  await page.route(
    `**/assistant/conversations/${conversation.conversation_id}`,
    (route) =>
      route.fulfill({
        json: {
          ...conversation,
          messages: [
            message,
            ...(obsolete
              ? [
                  {
                    ...message,
                    message_id: "newer-message",
                    commute_preference_question: false,
                    content: "Your newer request is ready.",
                  },
                ]
              : []),
          ],
        },
      }),
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  return { c, catalogue };
}

for (const width of [360, 768, 1440]) {
  test(`housing card actions form two secondary buttons and a full-width primary action at ${width}px`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const { catalogue } = await seed(page, request);
    const card = page.locator("article.assistant-listing").first();
    const details = card.getByRole("button", {
      name: "Listing details",
      exact: true,
    });
    const save = card.getByRole("button", {
      name: "Save listing",
      exact: true,
    });
    const follow = card.getByRole("button", {
      name: "Select and follow up",
      exact: true,
    });
    await expect(follow).toBeVisible();
    // Capture all geometry in one browser frame while chat scrolls to the reply.
    const [d, s, f] = await card.evaluate((element) =>
      ["Listing details", "Save listing", "Select and follow up"].map(
        (label) => {
          const button = Array.from(element.querySelectorAll("button")).find(
            (button) => button.textContent?.trim() === label,
          )!;
          const { x, y, width, height } = button.getBoundingClientRect();
          return { x, y, width, height };
        },
      ),
    );
    expect(Math.abs(d.y - s.y)).toBeLessThan(2);
    expect(f.y).toBeGreaterThan(d.y + d.height + 4);
    expect(f.width).toBeGreaterThan(Math.max(d.width, s.width) * 1.5);
    expect(f.height).toBeGreaterThanOrEqual(36);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: `/tmp/rental-card-layout-${width}.png`,
      fullPage: true,
    });
    await save.click();
    await expect(
      card.getByRole("button", { name: "Remove favorite", exact: true }),
    ).toBeVisible();
    await details.click();
    const drawer = page.getByRole("dialog");
    await expect(drawer).toContainText(catalogue.items[0].address);
    await page.keyboard.press("Escape");
    await card
      .getByRole("checkbox", {
        name: `Compare ${catalogue.items[0].address}`,
        exact: true,
      })
      .check();
    await expect(
      page.getByRole("button", {
        name: "Compare selected listings",
        exact: true,
      }),
    ).toBeVisible();
  });
}

test("optional commute choices prepare an explicit include or skip reply", async ({
  page,
  request,
}) => {
  await seed(page, request, true);
  const input = page.getByRole("textbox", {
    name: "Message to Rental Assistant",
    exact: true,
  });
  await page
    .getByRole("button", { name: "Add commute filter", exact: true })
    .click();
  await expect(input).toHaveValue("Yes, I would like to filter by commute.");
  await page
    .getByRole("button", { name: "Skip commute filter", exact: true })
    .click();
  await expect(input).toHaveValue("No commute filter, please.");
});

test("obsolete commute choices cannot overwrite the current conversation input", async ({
  page,
  request,
}) => {
  await seed(page, request, true, true);
  await expect(
    page.getByRole("button", { name: "Add commute filter", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Skip commute filter", exact: true }),
  ).toBeDisabled();
});

for (const area of ["any suburb", "Burwood"]) {
  test(`real intake supports optional commute for ${area}`, async ({
    page,
    request,
  }) => {
    const c = await (await request.post("/api/v1/cases", { data: {} })).json();
    await page.goto(`/cases/${c.case_id}/assistant`);
    const input = page.getByRole("textbox", {
      name: "Message to Rental Assistant",
      exact: true,
    });
    await input.fill(
      `Record my rental needs: ${area}, AUD 900 per week for the whole property, one person, at least two bedrooms and two bathrooms, no parking.`,
    );
    await input.press("Enter");
    if (area === "any suburb") {
      await expect(
        page.getByRole("button", { name: "Skip commute filter", exact: true }),
      ).toBeEnabled();
      await expect(page.locator("article.assistant-listing")).toHaveCount(0);
      await page
        .getByRole("button", { name: "Skip commute filter", exact: true })
        .click();
      await input.press("Enter");
    }
    await expect(
      page.getByRole("region", { name: "Filtered listings", exact: true }),
    ).toBeVisible();
    const expand = page.getByRole("button", {
      name: /^View all \d+ listings$/,
    });
    if (await expand.count()) await expand.click();
    await expect(
      page.locator("article.assistant-listing").first(),
    ).toBeVisible();
    await expect(
      page.locator(".assistant-message-assistant").last(),
    ).not.toContainText("maximum one-way");
    expect(
      (await (await request.get(`/api/v1/cases/${c.case_id}`)).json())
        .confirmations,
    ).toHaveLength(0);
    await page.reload();
    await expect(
      page.getByRole("region", { name: "Filtered listings", exact: true }),
    ).toBeVisible();
    if (await expand.count()) await expand.click();
    await expect(
      page.locator("article.assistant-listing").first(),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "My rental needs", exact: true })
      .click();
    const panel = page.getByRole("dialog", {
      name: "My rental needs",
      exact: true,
    });
    await expect(
      panel.getByRole("spinbutton", {
        name: "Maximum one-way commute (minutes)",
        exact: true,
      }),
    ).toHaveValue("");
    await panel
      .getByRole("button", { name: "Save rental needs", exact: true })
      .click();
    await expect(panel).not.toBeVisible();
    const saved = await (
      await request.get(`/api/v1/cases/${c.case_id}`)
    ).json();
    expect(saved.confirmations.length).toBeGreaterThan(0);
    expect(saved.draft.profile.student_commute).toBeUndefined();
    expect(saved.draft.profile.housing_preferences.suburb).toBe(
      area === "Burwood" ? "Burwood" : null,
    );
    await page
      .getByRole("button", { name: "My rental needs", exact: true })
      .click();
    await expect(
      panel.getByRole("spinbutton", {
        name: "Maximum one-way commute (minutes)",
        exact: true,
      }),
    ).toHaveValue("");
    if (area === "any suburb") {
      await panel.getByLabel("Commute mode", { exact: true }).click();
      await panel.getByLabel("Commute mode", { exact: true }).press("Home");
      await panel.getByLabel("Commute mode", { exact: true }).press("Enter");
      await panel
        .getByRole("spinbutton", {
          name: "Maximum one-way commute (minutes)",
          exact: true,
        })
        .fill("45");
      await panel
        .getByRole("button", { name: "Save rental needs", exact: true })
        .click();
      await expect(panel).not.toBeVisible();
      const updated = await (
        await request.get(`/api/v1/cases/${c.case_id}`)
      ).json();
      expect(updated.draft.profile.student_commute).toMatchObject({
        mode: "public_transport",
        maximum_minutes: 45,
      });
    }
  });
}
