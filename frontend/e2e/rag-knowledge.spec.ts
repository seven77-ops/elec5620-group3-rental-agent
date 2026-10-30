import { test, expect } from "@playwright/test";

test("Historical multilingual sources-only chat regenerates an English summary without rewriting the conversation", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  let original: unknown;
  await page.route(
    "**/api/v1/cases/*/assistant/conversations/*/messages",
    async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      const response = await route.fetch();
      const body = await response.json();
      // Change only the displayed historic response; backend records remain immutable.
      function historical(value: any) {
        if (!value || typeof value !== "object") return;
        if (value.knowledge) {
          value.knowledge = {
            ...value.knowledge,
            status: "sources_only",
            language: "zh",
            source_preserving: false,
            question: "需要维修时先找谁？",
            generation_outcome: "unsupported_claim",
            answer:
              "English source excerpts are available below. No AI summary has been applied.",
          };
        }
        for (const child of Object.values(value))
          if (typeof child === "object") historical(child);
      }
      historical(body);
      original = body;
      await route.fulfill({ response, json: body });
    },
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByPlaceholder("Describe your rental needs or ask a question…")
    .fill("How do I request repairs?");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  const last = page.locator(".assistant-message-assistant").last();
  await expect(
    last.getByRole("button", { name: "Summarise again", exact: true }),
  ).toBeVisible();
  const conversations = await (
    await request.get(`/api/v1/cases/${c.case_id}/assistant/conversations`)
  ).json();
  const before = JSON.stringify(conversations);
  const conversationUrl = `/api/v1/cases/${c.case_id}/assistant/conversations/${conversations.items[0].conversation_id}`;
  const saved = await (await request.get(conversationUrl)).json();
  let submitted: any;
  page.on("request", (req) => {
    if (req.url().endsWith("/rag/answers")) submitted = req.postDataJSON();
  });
  await last
    .getByRole("button", { name: "Summarise again", exact: true })
    .click();
  await expect(last.locator(".knowledge-answer")).toContainText(
    "Contact the landlord or agent",
  );
  await expect(last).toContainText("Cited answer");
  await expect(last.locator(".knowledge-source")).toHaveCount(0);
  await expect(last.locator(".assistant-bubble")).toHaveCount(0);
  expect(submitted.language).toBe("en");
  expect(submitted.allow_external_ai).toBe(true);
  expect(
    JSON.stringify(
      await (
        await request.get(`/api/v1/cases/${c.case_id}/assistant/conversations`)
      ).json(),
    ),
  ).toBe(before);
  expect(await (await request.get(conversationUrl)).json()).toEqual(saved);
  expect(original).toBeTruthy();
});

test("Chinese public questions receive English answers before collapsed evidence", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  // The isolated model fixture selects knowledge; the HTTP/chat/rendering pipeline is real.
  await page
    .getByPlaceholder("Describe your rental needs or ask a question…")
    .fill("在 NSW，租客怎么报修？");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  const last = page.locator(".assistant-message-assistant").last();
  await expect(last.locator(".knowledge-answer")).toContainText(
    "Contact the landlord or agent",
  );
  await expect(last.locator(".knowledge-source")).toHaveCount(0);
  await expect(last.locator(".assistant-bubble")).toHaveCount(0);
  await last.getByText("Read source excerpts", { exact: true }).click();
  await expect(last.locator(".knowledge-source").first()).toBeVisible();
});

test("English knowledge sources work without external consent and preserve case data", async ({
  page,
  request,
}) => {
  const before = await (
    await request.post("/api/v1/cases", { data: {} })
  ).json();
  await page.goto(`/cases/${before.case_id}/contract`);
  await page
    .getByRole("button", { name: "Ask rental knowledge", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Rental knowledge",
    exact: true,
  });
  await expect(dialog).toContainText("English official sources");
  await dialog
    .getByRole("textbox", { name: "Rental knowledge question" })
    .fill("How do I request repairs?");
  await dialog
    .getByRole("button", { name: "Find sources", exact: true })
    .click();
  await expect(
    dialog.getByRole("region", { name: "Knowledge evidence" }),
  ).toBeVisible();
  await expect(dialog).toContainText("Sources only");
  await dialog.getByText("Read source excerpts", { exact: true }).click();
  await expect(
    dialog.getByRole("link", { name: /NSW Government/ }).first(),
  ).toHaveAttribute("href", /^https:\/\/www\.nsw\.gov\.au\//);
  expect(
    await (await request.get(`/api/v1/cases/${before.case_id}`)).json(),
  ).toEqual(before);
  await dialog.locator(".ant-modal-footer").getByRole("button", { name: "Close", exact: true }).click();
  await page
    .getByRole("menuitem", { name: "Aftercare services", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Ask rental knowledge", exact: true }),
  ).toBeVisible();
});

test("English public knowledge questions in chat show citations without recommending houses", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByPlaceholder("Describe your rental needs or ask a question…")
    .fill("How do I request repairs?");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  const last = page.locator(".assistant-message-assistant").last();
  await expect(
    last.getByRole("region", { name: "Knowledge evidence" }),
  ).toBeVisible();
  await expect(last).toContainText("English rental sources");
  await expect(last.locator(".housing-card")).toHaveCount(0);
});

test("An intentional no-answer shows missing facts without claiming an AI outage", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/contract`);
  await page
    .getByRole("button", { name: "Ask rental knowledge", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Rental knowledge",
    exact: true,
  });
  await dialog
    .getByRole("textbox", { name: "Rental knowledge question" })
    .fill("What is my exact rent debt?");
  await dialog.getByRole("checkbox").check();
  await dialog
    .getByRole("button", { name: "Ask with AI", exact: true })
    .click();
  await expect(dialog).toContainText("More information needed");
  await expect(dialog).toContainText(
    "Your rent ledger and payment dates are not supplied.",
  );
  await expect(dialog).not.toContainText("The AI summary was unavailable");
  await expect(dialog).not.toContainText("The AI summary is unavailable");
  await expect(dialog).not.toContainText("failed citation checks");
});

test("The product guide is readable and product questions cite the app guide only", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  const guide = page.getByRole("link", { name: "User guide", exact: true });
  await expect(guide).toHaveAttribute("href", "/api/v1/rag/product-guide");
  const help = await request.get("/api/v1/rag/product-guide");
  expect(help.status()).toBe(200);
  expect(help.headers()["content-type"]).toContain("text/html");
  expect(await help.text()).toContain(
    "Favorites, comparison and direct selection",
  );
  await page
    .getByRole("button", { name: "Ask rental knowledge", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Rental knowledge",
    exact: true,
  });
  await dialog
    .getByRole("textbox", { name: "Rental knowledge question" })
    .fill("Do I need to favorite a listing before selecting it?");
  await dialog
    .getByRole("button", { name: "Find sources", exact: true })
    .click();
  await expect(dialog).toContainText("Product usage guide");
  await dialog.getByText("Read source excerpts", { exact: true }).click();
  await expect(
    dialog.getByRole("link", { name: /Rental assistant guide/ }).first(),
  ).toHaveAttribute("href", /^\/api\/v1\/rag\/product-guide\?version=/);
  await expect(dialog.locator(".knowledge-source")).not.toContainText([
    "NSW Government",
  ]);
  await expect(dialog).toContainText("two parallel choices");
});

test("University advice carries its own source label", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/contract`);
  await page
    .getByRole("button", { name: "Ask rental knowledge", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Rental knowledge",
    exact: true,
  });
  await dialog
    .getByRole("textbox", { name: "Rental knowledge question" })
    .fill(
      "How can I avoid rental scams when finding accommodation near university?",
    );
  await dialog
    .getByRole("button", { name: "Find sources", exact: true })
    .click();
  await dialog.getByText("Read source excerpts", { exact: true }).click();
  const student = dialog
    .locator(".knowledge-source")
    .filter({ has: page.getByRole("link", { name: /University of Sydney/ }) });
  await expect(student.first()).toBeVisible();
  await expect(student.first()).not.toContainText("NSW Government");
});
