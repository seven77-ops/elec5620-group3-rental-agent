import { expect, test } from "@playwright/test";

test("AI repair email accepts raw text without title, saves edited email and restores it", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`/cases/${c.case_id}/aftercare?tab=repairs`);
  await page
    .getByRole("textbox", { name: "Repair email recipient name", exact: true })
    .fill("Alex");
  await page
    .getByRole("textbox", { name: "Issue description", exact: true })
    .fill("厨房水龙头漏水，请安排维修。");
  const called = page.waitForRequest(
    (r) => r.url().endsWith("/repair-email/polish") && r.method() === "POST",
  );
  await page.getByRole("button", { name: "Polish email with AI", exact: true }).click();
  const payload = (await called).postDataJSON();
  expect(payload).toMatchObject({
    draft: "厨房水龙头漏水，请安排维修。",
    recipient_name: "Alex",
    language: "en",
    tone: "polite",
    allow_external_ai: true,
    title: "",
  });
  await expect(
    page.getByRole("textbox", { name: "Polished email body", exact: true }),
  ).toContainText("Dear Alex");
  const before = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(before.repairs).toHaveLength(0);
  expect(before.version).toBe(0);
  await page
    .getByRole("textbox", { name: "Polished email subject", exact: true })
    .fill("Please repair the tap");
  await page
    .getByRole("textbox", { name: "Polished email body", exact: true })
    .fill(
      "Dear Alex,\n\nThe kitchen tap is leaking. Please advise the next steps.\n\nThank you.",
    );
  await page.screenshot({
    path: "/tmp/repair-email-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Save polished repair draft", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Please advise the next steps.",
  );
  await page
    .getByRole("button", { name: "Confirm repair draft", exact: true })
    .click();
  const card = page.locator(".living-repair-card");
  await expect(card).toContainText("Please advise the next steps.");
  await page.reload();
  await expect(card).toContainText("Please repair the tap");
  await expect(card).toContainText("Draft prepared · Not sent");
  const saved = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(saved.repairs).toHaveLength(1);
  expect(saved.repairs[0]).toMatchObject({
    recipient_name: "Alex",
    description: payload.draft,
    email: {
      subject: "Please repair the tap",
      delivery_status: "prepared_not_sent",
    },
  });
  expect(errors).toEqual([]);
});

test("polish failure preserves raw and edited text; retry uses same request; mobile fits", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await page
    .getByRole("textbox", { name: "Issue description", exact: true })
    .fill("厨房水龙头漏水");
  await page.getByRole("button", { name: "Polish email with AI", exact: true }).click();
  const output = page.getByRole("textbox", {
    name: "Polished email body",
    exact: true,
  });
  await expect(output).toBeVisible();
  await output.fill("My reviewed wording");
  const ids: string[] = [];
  await page.route("**/repair-email/polish", async (route) => {
    ids.push(route.request().postDataJSON().request_id);
    if (ids.length === 1)
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "ai_unavailable",
            message: "AI 暂时不可用，原稿已保留。",
          },
        }),
      });
    else await route.continue();
  });
  await page.getByRole("button", { name: "Polish email again", exact: true }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Email polishing or saving could not be completed" }),
  ).toBeVisible();
  await expect(output).toHaveValue("My reviewed wording");
  await expect(
    page.getByRole("textbox", { name: "Issue description", exact: true }),
  ).toHaveValue("厨房水龙头漏水");
  await page.getByRole("button", { name: "Polish email again", exact: true }).click();
  await expect(output).toContainText("Dear Property Manager");
  expect(ids[1]).toBe(ids[0]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/repair-email-mobile.png",
    fullPage: true,
  });
});

test("chat has a direct entry to repair email page", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page.getByRole("button", { name: "Polish repair email", exact: true }).click();
  await expect(page).toHaveURL(/aftercare\?tab=repairs/);
  await expect(
    page.getByRole("button", { name: "Polish email with AI", exact: true }),
  ).toBeVisible();
});
