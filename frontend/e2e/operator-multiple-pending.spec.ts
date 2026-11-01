import { test, expect } from "@playwright/test";

test("three pending reports have independent accessible advice fields and save the correct advice", async ({
  page,
  request,
}) => {
  const ids: string[] = [];
  for (let index = 0; index < 3; index++) {
    const c = await (await request.post("/api/v1/cases", { data: {} })).json();
    const created = await request.post(
      `/api/v1/cases/${c.case_id}/issue-reports`,
      {
        data: {
          request_id: `three-pending-${index}`,
          category: ["rent", "repairs", "post_tenancy"][index],
          description: `Fictional pending review ${index + 1}`,
          attachment_ids: [],
        },
      },
    );
    expect(created.ok()).toBeTruthy();
    ids.push((await created.json()).review_id);
  }
  await page.goto("/operator");
  const queue = page.getByRole("region", {
    name: "Human review queue",
    exact: true,
  });
  const advice = [
    "Compare the rent ledger with the fictional payment receipt.",
    "Request a confirmed appointment for the fictional repair.",
    "Check the fictional account closure date and meter reading.",
  ];
  for (let index = 0; index < 3; index++) {
    const card = queue
      .getByTestId("operator-review")
      .filter({ hasText: `Fictional pending review ${index + 1}` });
    const field = card.getByLabel("Review advice", { exact: true });
    await expect(field).toBeVisible();
    await field.fill(advice[index]);
  }
  for (let index = 0; index < 3; index++) {
    const card = queue
      .getByTestId("operator-review")
      .filter({ hasText: `Fictional pending review ${index + 1}` });
    await expect(card.getByLabel("Review advice", { exact: true })).toHaveValue(
      advice[index],
    );
  }
  await queue
    .getByTestId("operator-review")
    .filter({ hasText: "Fictional pending review 2" })
    .getByRole("button", {
      name: "Save advice and complete review",
      exact: true,
    })
    .click();
  const reviewed = page
    .getByRole("region", { name: "Review history", exact: true })
    .getByTestId("operator-review")
    .filter({ hasText: "Fictional pending review 2" });
  await expect(reviewed).toContainText(advice[1]);
  const saved = await (await request.get("/api/v1/operator/reviews")).json();
  expect(
    saved.items.find((item: { review_id: string }) => item.review_id === ids[1])
      .decisions[0].note,
  ).toBe(advice[1]);
  for (const id of [ids[0], ids[2]])
    expect(
      saved.items.find((item: { review_id: string }) => item.review_id === id)
        .status,
    ).toBe("open");
});
