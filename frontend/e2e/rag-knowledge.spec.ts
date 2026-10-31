import { test, expect, type Page } from "@playwright/test";

async function askInChat(page: Page, caseId: string, question: string) {
  await page.goto(`/cases/${caseId}/assistant`);
  await page
    .getByRole("textbox", { name: "Message to Rental Assistant", exact: true })
    .fill(question);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  const reply = page.locator(".assistant-message-assistant").last();
  await expect(
    reply.getByRole("region", { name: "Knowledge evidence", exact: true }),
  ).toBeVisible();
  return reply;
}

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

test("public source retrieval still works locally and obsolete modal buttons are absent across work screens", async ({
  page,
  request,
}) => {
  const before = await (
    await request.post("/api/v1/cases", { data: {} })
  ).json();
  const response = await request.post(
    `/api/v1/cases/${before.case_id}/rag/answers`,
    {
      data: {
        question: "How do I request repairs?",
        allow_external_ai: false,
        language: "en",
      },
    },
  );
  expect(response.ok()).toBeTruthy();
  const answer = await response.json();
  expect(answer.status).toBe("sources_only");
  expect(answer.generation_outcome).toBe("local_only");
  expect(
    answer.citations.some((source: { source_url: string }) =>
      source.source_url.startsWith("https://www.nsw.gov.au/"),
    ),
  ).toBeTruthy();
  expect(
    await (await request.get(`/api/v1/cases/${before.case_id}`)).json(),
  ).toEqual(before);
  for (const [screen, title] of [
    ["assistant", "AI rental assistant"],
    ["contract", "Contract assistant"],
    ["aftercare", "Living and aftercare services"],
  ]) {
    await page.goto(`/cases/${before.case_id}/${screen}`);
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Ask rental knowledge", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("dialog", { name: "Rental knowledge", exact: true }),
    ).toHaveCount(0);
  }
});

test("English public knowledge questions in chat show citations without recommending houses", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(
    page.getByRole("heading", { name: "AI rental assistant", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Ask rental knowledge", exact: true }),
  ).toHaveCount(0);
  await page
    .getByPlaceholder("Describe your rental needs or ask a question…")
    .fill("How do I request repairs?");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  const last = page.locator(".assistant-message-assistant").last();
  await expect(
    last.getByRole("region", { name: "Knowledge evidence" }),
  ).toBeVisible();
  await expect(last).not.toContainText("English rental sources");
  await expect(last).toContainText("Cited answer");
  await expect(last.locator(".housing-card")).toHaveCount(0);
});

test("a knowledge question in chat states missing facts without claiming an AI outage", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const reply = await askInChat(page, c.case_id, "What is my exact rent debt?");
  await expect(reply).toContainText("More information needed");
  await expect(reply).toContainText(
    "Your rent ledger and payment dates are not supplied.",
  );
  await expect(reply).not.toContainText("The AI summary was unavailable");
  await expect(reply).not.toContainText("The AI summary is unavailable");
  await expect(reply).not.toContainText("failed citation checks");
  await expect(page.locator("article.assistant-listing")).toHaveCount(0);
});

test("the product guide stays accessible and product questions are answered with guide citations in chat", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const reply = await askInChat(
    page,
    c.case_id,
    "Do I need to favorite a listing before selecting it?",
  );
  await expect(
    page.getByRole("link", { name: "User guide", exact: true }),
  ).toHaveAttribute("href", "/api/v1/rag/product-guide");
  const help = await request.get("/api/v1/rag/product-guide");
  expect(help.status()).toBe(200);
  expect(help.headers()["content-type"]).toContain("text/html");
  expect(await help.text()).toContain(
    "Favorites, comparison and direct selection",
  );
  await expect(reply).toContainText("Product usage guide");
  await reply.getByText("Read source excerpts", { exact: true }).click();
  await expect(
    reply.getByRole("link", { name: /Rental assistant guide/ }).first(),
  ).toHaveAttribute("href", /^\/api\/v1\/rag\/product-guide\?version=/);
  await expect(reply.locator(".knowledge-source")).not.toContainText([
    "NSW Government",
  ]);
  await expect(reply).toContainText("two parallel choices");
});

test("university advice in chat retains its own source label", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const reply = await askInChat(
    page,
    c.case_id,
    "How can I avoid rental scams when finding accommodation near university?",
  );
  await reply.getByText("Read source excerpts", { exact: true }).click();
  const student = reply
    .locator(".knowledge-source")
    .filter({ has: page.getByRole("link", { name: /University of Sydney/ }) });
  await expect(student.first()).toBeVisible();
  await expect(student.first()).not.toContainText("NSW Government");
});

test("knowledge questions interrupt housing intake without changing preferences and remain after reload", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  const input = page.getByRole("textbox", {
    name: "Message to Rental Assistant",
    exact: true,
  });
  await input.fill("I want to live in Burwood with a weekly budget of 1200");
  await input.press("Enter");
  await expect(
    page.locator(".assistant-message-assistant").last(),
  ).toContainText("whole property");
  const root = `/api/v1/cases/${c.case_id}/assistant/conversations`;
  const list = await (await request.get(root)).json();
  const url = `${root}/${list.items[0].conversation_id}`;
  const before = await (await request.get(url)).json();
  await input.fill("How do I request repairs?");
  await input.press("Enter");
  await expect(
    page
      .locator(".assistant-message-assistant")
      .last()
      .getByRole("region", { name: "Knowledge evidence" }),
  ).toBeVisible();
  const after = await (await request.get(url)).json();
  expect(after.rental_brief).toEqual(before.rental_brief);
  expect(after.last_search_filters).toEqual(before.last_search_filters);
  expect(
    (await (await request.get(`/api/v1/cases/${c.case_id}`)).json()).draft,
  ).toEqual(c.draft);
  expect(after.messages.at(-1).listings).toHaveLength(0);
  await page.reload();
  await expect(
    page
      .locator(".assistant-message-assistant")
      .last()
      .getByRole("region", { name: "Knowledge evidence" }),
  ).toBeVisible();
  await input.fill("Whole property");
  await input.press("Enter");
  await expect(
    page.locator(".assistant-message-assistant").last(),
  ).toContainText("bedrooms");
  const resumed = await (await request.get(url)).json();
  expect(resumed.rental_brief).toMatchObject({
    suburb: "Burwood",
    budget_amount: 1200,
    budget_scope: "whole_property",
  });
});
