import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

// Runs against the isolated AssistantDemoProvider runner. Every browser request
// stays on that runner's origin, including when catalogue cards contain photos.
test.beforeEach(async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  await page.route(/^https?:\/\//, (route) =>
    new URL(route.request().url()).origin === origin
      ? route.continue()
      : route.abort("blockedbyclient"),
  );
});

async function newCase(request: APIRequestContext) {
  const response = await request.post("/api/v1/cases", { data: {} });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function send(page: Page, message: string) {
  await page
    .getByRole("textbox", { name: "Message to Rental Assistant", exact: true })
    .fill(message);
  const [response] = await Promise.all([
    page.waitForResponse(
      (r) => r.request().method() === "POST" && r.url().endsWith("/messages"),
    ),
    page.getByRole("button", { name: "Send message", exact: true }).click(),
  ]);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function expectEnglish(page: Page) {
  // These journeys use English source files and user input. A Han character here
  // therefore exposes untranslated product output rather than a source quotation.
  await expect(page.locator("body")).not.toContainText(/\p{Script=Han}/u);
}

async function saveRepair(page: Page) {
  await page
    .getByRole("button", {
      name: /^(Save to Aftercare|Confirm repair update)$/,
      exact: true,
    })
    .last()
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Confirm sync to Aftercare services?",
    exact: true,
  });
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("button", {
      name: "Confirm and save aftercare details",
      exact: true,
    })
    .click();
  await expect(dialog).not.toBeVisible();
}

test("English shell navigation, favorites and empty repair records", async ({
  page,
  request,
}) => {
  const c = await newCase(request);
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(
    page.getByRole("heading", { name: "AI rental assistant", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Where would you like to live?",
      exact: true,
    }),
  ).toBeVisible();
  for (const name of [
    "AI rental assistant",
    "Housing recommendations",
    "Contract assistant",
    "Aftercare services",
    "Case progress",
    "Human review",
  ])
    await expect(
      page.getByRole("menuitem", { name, exact: true }),
    ).toBeVisible();
  await expectEnglish(page);
  await page
    .getByRole("menuitem", { name: "Housing recommendations", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Housing recommendations", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "My favorites (0)", exact: true })
    .click();
  const favorites = page.getByRole("dialog", {
    name: "My favorites",
    exact: true,
  });
  await expect(favorites).toContainText(
    "No saved listings yet. Save a listing when you find one you like.",
  );
  await expectEnglish(page);
  await page.keyboard.press("Escape");
  await page
    .getByRole("menuitem", { name: "Contract assistant", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Contract assistant", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("tab", { name: "Upload contract for review", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Upload your contract", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("menuitem", { name: "Aftercare services", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Living and aftercare services",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("No repairs recorded yet.", { exact: true }),
  ).toBeVisible();
  await expectEnglish(page);
});

test("English housing chat retains source details and comparison prompts", async ({
  page,
  request,
}) => {
  const c = await newCase(request);
  await page.goto(`/cases/${c.case_id}/assistant`);
  const conversation = await send(
    page,
    "Find a two-bedroom, two-bathroom home in Rhodes with parking and a weekly rent under AUD 1500.",
  );
  const answer = conversation.messages.at(-1);
  expect(answer.listings.length).toBeGreaterThan(0);
  expect(answer.content).not.toMatch(/\p{Script=Han}/u);
  const listing = answer.listings[0];
  const card = page.locator(`[data-listing-id="${listing.listing_id}"]`);
  await expect(card.getByRole("heading")).toHaveText(listing.address);
  await card
    .getByRole("button", { name: "Listing details", exact: true })
    .click();
  const details = page.getByRole("dialog", {
    name: "Listing details",
    exact: true,
  });
  await expect(details).toContainText("Bedrooms");
  await expect(
    details.getByRole("link", { name: "View Domain listing", exact: true }),
  ).toHaveAttribute("href", listing.source_url);
  await expectEnglish(page);
  await page.keyboard.press("Escape");
  for (const item of answer.listings.slice(0, 2))
    await page
      .getByRole("checkbox", { name: `Compare ${item.address}`, exact: true })
      .check();
  await page
    .getByRole("button", { name: "Compare selected listings", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", {
      name: "Message to Rental Assistant",
      exact: true,
    }),
  ).toHaveValue(
    "Compare the weekly rent, bedrooms, bathrooms and car spaces of the selected listings.",
  );
});

test("English knowledge answers expose official citations without changing case data", async ({
  page,
  request,
}) => {
  const before = await newCase(request);
  await page.goto(`/cases/${before.case_id}/assistant`);
  await send(page, "How do I request repairs?");
  const reply = page.locator(".assistant-message-assistant").last();
  const evidence = reply.getByRole("region", {
    name: "Knowledge evidence",
    exact: true,
  });
  await expect(evidence).toBeVisible();
  await expect(evidence).not.toContainText("English rental sources");
  await expect(evidence).toContainText("Cited answer");
  await expect(evidence.locator(".knowledge-answer")).toContainText(
    /landlord|agent/i,
  );
  await evidence.getByText("Read source excerpts", { exact: true }).click();
  await expect(
    evidence.getByRole("link", { name: /NSW Government/ }).first(),
  ).toHaveAttribute("href", /^https:\/\/www\.nsw\.gov\.au\//);
  await expect(evidence.locator("blockquote").first()).not.toBeEmpty();
  await expect(reply.locator(".housing-card")).toHaveCount(0);
  await expectEnglish(page);
  const after = await (
    await request.get(`/api/v1/cases/${before.case_id}`)
  ).json();
  expect(after.selection).toBeNull();
  expect(after.confirmations).toEqual(before.confirmations);
  expect(after.reviews).toEqual(before.reviews);
});

test("English repair preview can be copied, rewritten, saved and updated on one record", async ({
  page,
  request,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const c = await newCase(request);
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  await page.goto(`/cases/${c.case_id}/assistant`);
  await send(
    page,
    "The kitchen sink has been leaking since last night. Please write a repair email.",
  );
  const draft = page
    .getByRole("region", { name: "Repair email draft", exact: true })
    .last();
  await expect(draft).toContainText("English email draft · Not sent");
  await expect(draft).toContainText(
    "The kitchen sink has been leaking since last night.",
  );
  await expect(
    draft.getByRole("button", { name: "Regenerate in English", exact: true }),
  ).toBeVisible();
  await draft
    .getByRole("button", { name: "Copy email draft", exact: true })
    .click();
  await expect
    .poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .toContain("The kitchen sink has been leaking since last night.");
  expect((await (await request.get(root)).json()).repairs).toHaveLength(0);
  await draft.getByRole("button", { name: "More polite", exact: true }).click();
  const rewrite =
    "Make this repair email more polite in English, keep the original facts and do not send it.";
  await expect(
    page.getByRole("textbox", {
      name: "Message to Rental Assistant",
      exact: true,
    }),
  ).toHaveValue(rewrite);
  await send(page, rewrite);
  await expect(
    page
      .getByRole("region", { name: "Repair email draft", exact: true })
      .last(),
  ).toContainText("let me know the next steps");
  await saveRepair(page);
  const saved = await (await request.get(root)).json();
  expect(saved.repairs).toHaveLength(1);
  const repair = saved.repairs[0];
  expect(repair.email_language).toBe("en");
  expect(repair.email_tone).toBe("polite");
  expect(repair.email.delivery_status).toBe("prepared_not_sent");
  expect(JSON.stringify(repair)).not.toMatch(/\p{Script=Han}/u);
  await send(
    page,
    "The agent replied and will arrange a repair tomorrow morning.",
  );
  await saveRepair(page);
  let updated = await (await request.get(root)).json();
  expect(updated.repairs).toHaveLength(1);
  expect(updated.repairs[0].repair_id).toBe(repair.repair_id);
  expect(updated.repairs[0].status).toBe("contacted");
  await send(page, "The repair is complete. Please mark it resolved.");
  await saveRepair(page);
  updated = await (await request.get(root)).json();
  expect(updated.repairs[0].status).toBe("resolved");
  await page.goto(
    `/cases/${c.case_id}/aftercare?tab=repairs&repair=${repair.repair_id}`,
  );
  await expect(page.locator(".living-repair-card")).toContainText(
    "Issue resolved",
  );
  await expect(page.locator(".living-repair-card")).toContainText(
    "Draft prepared · Not sent",
  );
  await expectEnglish(page);
});

test("English standalone contract upload supports private source Q&A without housing selection", async ({
  page,
  request,
}) => {
  const c = await newCase(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=review`);
  await page
    .getByRole("checkbox", {
      name: "I agree to process this uploaded contract independently, without linking it to a property.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", {
      name: "Agree to process this contract",
      exact: true,
    })
    .click();
  const clause =
    "The tenant must leave the premises reasonably clean, except for fair wear and tear.";
  await page.getByLabel("Select contract", { exact: true }).setInputFiles({
    name: "english-standalone-contract.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      `Address: 1 Example Street, Sydney NSW 2000\nRent: AUD 650 per week whole property\nBond: AUD 2600\nStart date: 2026-11-01\nEnd date: 2027-11-01\n6. Cleaning\n${clause}\n`,
    ),
  });
  await page
    .getByRole("checkbox", {
      name: "I confirm I am authorised to submit this contract for review.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "Upload and review", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Contract details",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("1 Example Street, Sydney NSW 2000", { exact: true }),
  ).toBeVisible();
  await page.getByText("Ask more about this contract", { exact: true }).click();
  const panel = page.getByRole("region", {
    name: "Private contract Q&A",
    exact: true,
  });
  await panel
    .getByRole("checkbox", {
      name: "I agree to enable private search for this contract on this device.",
      exact: true,
    })
    .check();
  await panel
    .getByRole("button", { name: "Enable contract search", exact: true })
    .click();
  await expect(panel).toContainText("Contract search ready");
  await panel
    .getByRole("textbox", { name: "Contract question", exact: true })
    .fill("What does the contract say about cleaning?");
  await panel
    .getByRole("button", { name: "Find contract text", exact: true })
    .click();
  const evidence = panel.getByRole("region", {
    name: "Knowledge evidence",
    exact: true,
  });
  await expect(evidence).toBeVisible();
  await evidence.getByText("Read source excerpts", { exact: true }).click();
  await expect(
    evidence
      .locator(".knowledge-source")
      .filter({ hasText: "Uploaded contract" })
      .first(),
  ).toContainText(clause);
  await expectEnglish(page);
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.selection).toBeNull();
  expect(saved.confirmations).toEqual([]);
  expect(saved.reviews).toHaveLength(1);
});

test("English mobile navigation and rental needs fit a 360px viewport", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const c = await newCase(request);
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(
    page.getByRole("heading", { name: "AI rental assistant", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "My rental needs", exact: true })
    .click();
  const needs = page.getByRole("dialog", {
    name: "My rental needs",
    exact: true,
  });
  await expect(
    needs.getByRole("combobox", { name: "Preferred area", exact: true }),
  ).toBeVisible();
  await expectEnglish(page);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  const navigation = page.getByRole("dialog", {
    name: "Rental Assistant navigation",
    exact: true,
  });
  await navigation
    .getByRole("menuitem", { name: "Aftercare services", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Living and aftercare services",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("No repairs recorded yet.", { exact: true }),
  ).toBeVisible();
  await expectEnglish(page);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
