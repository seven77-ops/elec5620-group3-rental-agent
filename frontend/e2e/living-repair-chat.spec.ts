import { test, expect, type Page } from "@playwright/test";

async function send(page: Page, text: string) {
  await page.getByRole("textbox", { name: "给租房助手的消息" }).fill(text);
  await page.getByRole("button", { name: "发送消息", exact: true }).click();
}
async function confirmLatest(page: Page) {
  await page
    .getByRole("button", { name: "确认更新这条报修", exact: true })
    .last()
    .click();
  const modal = page.getByRole("dialog", {
    name: "确认同步到租后服务？",
    exact: true,
  });
  await expect(modal).toBeVisible();
  await modal
    .getByRole("button", { name: "确认保存租后资料", exact: true })
    .click();
  await expect(modal).not.toBeVisible();
}

test("repair dialogue rewrites one pending draft then tracks reply and resolution on the same saved issue", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  await page.goto(`/cases/${c.case_id}/assistant`);
  await send(page, "厨房水槽下面一直漏水，帮我写报修邮件");
  await expect(
    page.getByRole("button", { name: "确认生成报修草稿", exact: true }),
  ).toBeVisible();
  await send(page, "这封邮件写得客气一点");
  await expect(
    page.getByRole("button", { name: "已由后续修改替代", exact: true }),
  ).toBeDisabled();
  expect((await (await request.get(root)).json()).repairs).toHaveLength(0);
  await confirmLatest(page);
  let record = await (await request.get(root)).json();
  expect(record.repairs).toHaveLength(1);
  const rid = record.repairs[0].repair_id;
  expect(record.repairs[0].email_tone).toBe("polite");
  expect(record.repairs[0].email.body).toContain("厨房水槽下面一直漏水");
  await page.reload();
  await send(page, "中介回复说明天上午来修");
  await expect(
    page.getByRole("button", { name: "确认更新这条报修", exact: true }),
  ).toBeVisible();
  record = await (await request.get(root)).json();
  expect(record.repairs[0].status).toBe("prepared");
  await confirmLatest(page);
  record = await (await request.get(root)).json();
  expect(record.repairs).toHaveLength(1);
  expect(record.repairs[0].repair_id).toBe(rid);
  expect(record.repairs[0].updates.at(-1).note).toBe("中介回复说明天上午来修");
  expect(record.repairs[0].status).toBe("contacted");
  await send(page, "已经修好了，请标记解决");
  await confirmLatest(page);
  record = await (await request.get(root)).json();
  expect(record.repairs).toHaveLength(1);
  expect(record.repairs[0].status).toBe("resolved");
  expect(record.repairs[0].email.delivery_status).toBe("prepared_not_sent");
  await page.goto(`/cases/${c.case_id}/aftercare?tab=repairs&repair=${rid}`);
  await expect(page.locator(".living-hub")).toContainText(
    "中介回复说明天上午来修",
  );
});
