import { test, expect } from "@playwright/test";

test("a new issue with evidence appears before an earlier contract and returns reviewer advice", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  const consent = await (
    await request.post(root + "/contract-consents", {
      data: { confirmed: true, scope: "document" },
    })
  ).json();
  const uploaded = await request.post(root + "/contract-reviews", {
    headers: {
      "Content-Type": "application/octet-stream",
      "X-Consent-Id": consent.consent_id,
      "X-Request-Id": "older-contract",
      "X-Filename": "fictional-older-contract.txt",
    },
    data: Buffer.from(
      "Property address: 42 Fictional Street, Sydney NSW 2000\nLandlord: Fictional Owner\nTenant: Fictional Tenant\nWeekly rent: AUD 500 per week whole property\nBond: AUD 2000\nStart date: 2026-11-01\nEnd date: 2026-10-31\n",
    ),
  });
  expect(uploaded.ok()).toBeTruthy();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=issues`);
  const form = page.getByRole("region", { name: "Report issue", exact: true });
  await form.getByLabel("Issue type", { exact: true }).click();
  await page.getByRole("option", { name: "Rent / bond", exact: true }).click();
  const description = "Fictional latest report: disputed wall-mark deduction.";
  await form.getByLabel("Issue description", { exact: true }).fill(description);
  await form.getByLabel("Add evidence files", { exact: true }).setInputFiles({
    name: "fictional-evidence.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGOUDNjCwMDAxAAGAAzrASEtu9dZAAAAAElFTkSuQmCC",
      "base64",
    ),
  });
  await expect(
    form.getByRole("button", { name: "Submit report", exact: true }),
  ).toBeEnabled();
  await form
    .getByRole("button", { name: "Submit report", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Issue report history", exact: true }),
  ).toContainText(description);
  await page
    .getByRole("menuitem", { name: "Human review", exact: true })
    .click();
  const queue = page.getByRole("region", {
    name: "Human review queue",
    exact: true,
  });
  const newest = queue.getByTestId("operator-review").first();
  await expect(newest).toContainText(description);
  await expect(
    newest.getByRole("img", { name: "fictional-evidence.png", exact: true }),
  ).toBeVisible();
  const advice =
    "Compare the entry record with the proposed deduction before replying.";
  await newest.getByLabel("Review advice", { exact: true }).fill(advice);
  await newest
    .getByRole("button", {
      name: "Save advice and complete review",
      exact: true,
    })
    .click();
  const history = page.getByRole("region", {
    name: "Review history",
    exact: true,
  });
  const reviewed = history
    .getByTestId("operator-review")
    .filter({ hasText: description });
  await expect(reviewed).toContainText(advice);
  await reviewed
    .getByRole("button", { name: "View report", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Issue report history", exact: true }),
  ).toContainText(advice);
});

test("Human review opens its queue directly without a key or active tenant case", async ({
  page,
}) => {
  await page.goto("/operator");
  await expect(
    page.getByRole("heading", { name: "Human review", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Human review queue", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Local operator key", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Review queue locked", { exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("region", { name: "Human review queue", exact: true }),
  ).toBeVisible();
});

test("contract review retains source quotes and uses the supported advice length", async ({
  page,
}) => {
  await page.route("**/api/v1/operator/reviews", (route) =>
    route.fulfill({
      json: {
        pending_count: 1,
        items: [
          {
            kind: "contract",
            case_id: "fictional-case",
            review_id: "fictional-review",
            version: 1,
            status: "open",
            address: "Fictional contract address",
            reason: "Rent difference",
            created_at: "2026-10-31T03:00:00Z",
            decisions: [],
            review: {
              findings: [
                {
                  title: "Rent mismatch",
                  reason: "Check the proposed rent.",
                  evidence: [
                    {
                      source_name: "fictional-contract.txt",
                      page: 1,
                      line: 2,
                      quote: "Rent: AUD 900 per week",
                    },
                  ],
                },
              ],
            },
          },
        ],
      },
    }),
  );
  await page.goto("/operator");
  const item = page.getByTestId("operator-review");
  await expect(item).toContainText("Rent: AUD 900 per week");
  await expect(item).toContainText("fictional-contract.txt");
  await expect(
    item.getByLabel("Review advice", { exact: true }),
  ).toHaveAttribute("maxlength", "1000");
});
