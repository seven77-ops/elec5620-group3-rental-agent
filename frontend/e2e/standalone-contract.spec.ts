import { test, expect } from "@playwright/test";

test("upload and privately query a contract before selecting housing", async ({
  page,
  request,
}) => {
  const created = await request.post("/api/v1/cases", { data: {} });
  expect(created.ok()).toBeTruthy();
  const current = await created.json();
  const root = `/api/v1/cases/${current.case_id}`;
  await page.goto(`/cases/${current.case_id}/contract?mode=review`);

  await page.getByLabel("Select contract", { exact: true }).setInputFiles({
    name: "standalone-contract.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "Address: 1 Example Street, Sydney NSW 2000\nRent: AUD 650 per week whole property\nBond: AUD 2600\nStart date: 2026-11-01\nEnd date: 2027-11-01\n6. Cleaning\nThe tenant must leave the premises reasonably clean, except for fair wear and tear.\n",
    ),
  });
  await page
    .getByRole("checkbox", {
      name: "I am authorised to upload this contract and agree to send it to the AI service for review.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "Upload and analyse", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Contract check results", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("1 Example Street, Sydney NSW 2000", { exact: true }),
  ).toBeVisible();
  await page.goto(`/cases/${current.case_id}/assistant`);
  await page
    .getByRole("textbox", { name: "Message to Rental Assistant", exact: true })
    .fill("Review my uploaded contract.");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
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
    .fill("合同清洁条款怎么写？");
  await panel
    .getByRole("button", { name: "Find contract text", exact: true })
    .click();
  await expect(
    panel.getByRole("region", { name: "Knowledge evidence", exact: true }),
  ).toBeVisible();
  const saved = await (await request.get(root)).json();
  expect(saved.selection).toBeNull();
  expect(saved.confirmations).toEqual([]);
  expect(saved.reviews).toHaveLength(1);
});
