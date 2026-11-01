import { expect, test } from "@playwright/test";

test("an older Human review contract opens its own file and source, not the latest upload", async ({
  page,
  request,
}) => {
  const caseId = (
    await (await request.post("/api/v1/cases", { data: {} })).json()
  ).case_id;
  const root = `/api/v1/cases/${caseId}`;
  const reviews: { review_id: string }[] = [];
  for (const [name, address] of [
    ["original-a.txt", "1 Fictional Alpha Street"],
    ["later-b.txt", "2 Fictional Beta Street"],
  ]) {
    const consent = await (
      await request.post(`${root}/contract-consents`, {
        data: { confirmed: true, scope: "document" },
      })
    ).json();
    const uploaded = await request.post(`${root}/contract-reviews`, {
      headers: {
        "Content-Type": "application/octet-stream",
        "X-Consent-Id": consent.consent_id,
        "X-Request-Id": name,
        "X-Filename": name,
      },
      data: Buffer.from(
        `Address: ${address}, Sydney NSW 2000\nRent: AUD 650 per week whole property\nBond: AUD 5000\nStart date: 2027-11-01\nEnd date: 2026-11-01\n`,
      ),
    });
    expect(uploaded.ok()).toBeTruthy();
    reviews.push((await uploaded.json()).review);
  }
  await page.goto("/operator");
  const card = page
    .locator("article")
    .filter({ hasText: "1 Fictional Alpha Street" });
  await card
    .getByRole("button", { name: "View contract record", exact: true })
    .click();
  const results = page.getByRole("region", {
    name: "Contract review results",
    exact: true,
  });
  await expect(results).toHaveAttribute("data-review-id", reviews[0].review_id);
  await expect(results).toContainText("original-a.txt");
  await expect(results).not.toContainText("later-b.txt");
  const source = results
    .locator("details")
    .filter({ hasText: "1 Fictional Alpha Street" })
    .first();
  await source.locator("summary").click();
  await expect(source.locator("blockquote")).toContainText(
    "1 Fictional Alpha Street",
  );
  await page.goto(
    `/cases/${caseId}/contract?mode=review&review_id=foreign-review`,
  );
  await expect(
    page.getByText("This contract is not available in the current case.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(results).toHaveCount(0);
  await page
    .getByRole("button", { name: "View latest contract", exact: true })
    .click();
  await expect(results).toHaveAttribute("data-review-id", reviews[1].review_id);
  await expect(results).toContainText("later-b.txt");
});
