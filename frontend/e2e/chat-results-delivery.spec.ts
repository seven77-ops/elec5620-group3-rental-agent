import { test, expect, type Page } from "@playwright/test";

async function send(page: Page, message: string) {
  await page.getByRole("textbox", { name: "Message to Rental Assistant" }).fill(message);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
}

test("chat previews English repair mail and saves the exact rewritten draft", async ({ page, request, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  await page.goto(`/cases/${c.case_id}/assistant`);
  await send(page, "厨房水槽从昨晚开始漏水，帮我准备一封礼貌的英文报修邮件，只准备草稿，不要发送。");
  let draft = page.getByRole("region", { name: "Repair email draft", exact: true }).last();
  await expect(draft).toContainText("The kitchen sink has been leaking since last night.");
  await expect(draft).toContainText("English email draft");
  await page.screenshot({ path: "/tmp/rental-chat-mail-preview.png", fullPage: true });
  expect((await (await request.get(root)).json()).repairs).toEqual([]);
  await draft.getByRole("button", { name: "Copy email draft", exact: true }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("since last night");
  await draft.getByRole("button", { name: "More concise", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Message to Rental Assistant" })).toHaveValue(/concise/i);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.getByRole("button", { name: "Replaced by a later change", exact: true })).toBeDisabled();
  draft = page.getByRole("region", { name: "Repair email draft", exact: true }).last();
  await expect(page.getByRole("region", { name: "Repair email draft", exact: true }).first().getByRole("button", { name: "More polite", exact: true })).toBeDisabled();
  const body = await draft.locator(".repair-email-body").innerText();
  await page.getByRole("button", { name: "Save to Aftercare", exact: true }).last().click();
  const modal = page.getByRole("dialog", { name: "Confirm sync to Aftercare services?", exact: true });
  await modal.getByRole("button", { name: "Confirm and save aftercare details", exact: true }).click();
  await expect(modal).not.toBeVisible();
  const saved = await (await request.get(root)).json();
  expect(saved.repairs).toHaveLength(1);
  expect(saved.repairs[0].email.body).toBe(body);
  expect(saved.repairs[0].email_tone).toBe("concise");
  expect(saved.repairs[0].email.delivery_status).toBe("prepared_not_sent");
  await page.reload();
  await expect(page.getByRole("region", { name: "Repair email draft", exact: true }).last().locator(".repair-email-body")).toHaveText(body);
  await send(page, "另外厨房水槽从昨晚开始漏水，请另外准备一封英文报修邮件。");
  await expect(page.getByRole("region", { name: "Repair email draft", exact: true })).toHaveCount(3);
  await expect(page.getByRole("region", { name: "Repair email draft", exact: true }).nth(1).getByRole("button", { name: "More polite", exact: true })).toBeDisabled();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test("chat uploads an existing contract and shows review and source Q&A without leaving chat", async ({ page, request }) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  await send(page, "我有一份租约，想检查租金、押金和特殊条款，请让我上传合同复核。");
  const widget = page.getByRole("region", { name: "Contract review in chat", exact: true });
  await expect(widget).toBeVisible();
  await widget.getByRole("checkbox", { name: "I agree to process this uploaded contract independently, without linking it to a property.", exact: true }).check();
  await widget.getByRole("button", { name: "Agree to process this contract", exact: true }).click();
  await widget.getByLabel("Select contract", { exact: true }).setInputFiles({
    name: "chat-test-contract.txt", mimeType: "text/plain", buffer: Buffer.from(
      "Address: 1 Example Street, Sydney NSW 2000\nLandlord: Example Landlord\nTenant: Example Tenant\nRent: AUD 650 per week whole property\nBond: AUD 2600\nStart date: 2026-11-01\nEnd date: 2027-11-01\n6. Cleaning\nThe tenant must leave the premises reasonably clean, except for fair wear and tear.\n"),
  });
  await widget.getByRole("checkbox", { name: "I confirm I am authorised to submit this contract for review.", exact: true }).check();
  await widget.getByRole("button", { name: "Upload and review", exact: true }).click();
  await expect(widget.getByRole("region", { name: "Contract review summary", exact: true })).toContainText("2600");
  await expect(page).toHaveURL(/\/assistant/);
  await widget.getByRole("button", { name: "View source text", exact: true }).first().click();
  await expect(page.getByRole("dialog", { name: "Contract source evidence", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  const panel = widget.getByRole("region", { name: "Private contract Q&A", exact: true });
  await panel.getByRole("checkbox", { name: "I agree to enable private search for this contract on this device.", exact: true }).check();
  await panel.getByRole("button", { name: "Enable contract search", exact: true }).click();
  await expect(panel).toContainText("Contract search ready");
  await panel.getByRole("textbox", { name: "Contract question", exact: true }).fill("合同清洁条款怎么写？");
  await panel.getByRole("button", { name: "Find contract text", exact: true }).click();
  await expect(panel.getByRole("region", { name: "Knowledge evidence", exact: true })).toBeVisible();
  await page.screenshot({ path: "/tmp/rental-chat-contract-review.png", fullPage: true });
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.selection).toBeNull();
  expect(saved.reviews).toHaveLength(1);
  await page.reload();
  await expect(page.getByRole("region", { name: "Contract review summary", exact: true })).toContainText("chat-test-contract.txt");
});
