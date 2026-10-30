import { test, expect } from "@playwright/test";

// Run against server.tests.jev_demo_app only. Both model providers are doubles.
for (const scenario of [
  {
    message: "How do I request repairs?",
    intent: "knowledge",
    source: "jev",
    reason: "accepted",
  },
  {
    message: "Compare commute options, then review my lease.",
    intent: "clarify",
    source: "jev",
    reason: "accepted",
  },
  {
    message: "Rhodes 两卧房源",
    intent: "search",
    source: "jev",
    reason: "accepted",
  },
  {
    message: "Rhodes 两卧房源 fallback-test",
    intent: "search",
    source: "ali",
    reason: "decision_failed",
  },
]) {
  test(`simulated Decisions routing: ${scenario.intent} ${scenario.source}`, async ({
    page,
    request,
  }) => {
    const before = await (
      await request.post("/api/v1/cases", { data: {} })
    ).json();
    await page.goto(`/cases/${before.case_id}/assistant`);
    await page
      .getByPlaceholder("Describe your rental needs or ask a question…")
      .fill(scenario.message);
    const responsePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/messages") &&
        response.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Send message", exact: true })
      .click();
    const response = await responsePromise;
    expect(response.status()).toBe(200);
    const answer = (await response.json()).messages.at(-1);
    expect(answer.intent).toBe(scenario.intent);
    expect(answer.routing.source).toBe(scenario.source);
    expect(answer.routing.reason).toBe(scenario.reason);
    const last = page.locator(".assistant-message-assistant").last();
    if (scenario.intent === "knowledge") {
      await expect(
        last.getByRole("region", { name: "Knowledge evidence" }),
      ).toBeVisible();
      expect(answer.knowledge.citations.length).toBeGreaterThan(0);
    } else if (scenario.intent === "clarify") {
      await expect(last).toContainText("handle first");
      expect(answer.actions).toEqual([]);
      expect(
        await (await request.get(`/api/v1/cases/${before.case_id}`)).json(),
      ).toEqual(before);
    } else {
      expect(answer.listings.length).toBeGreaterThan(0);
      await expect(last.locator(".assistant-listing").first()).toBeVisible();
    }
  });
}
