import { test, expect } from "@playwright/test";

test("both agent roles and conditional contract details save separately and generate a PDF", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  await request.post(root + "/profile-confirmations", {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  const run = await (
    await request.post(root + "/evaluations", {
      data: { request_id: "run", confirmation_version: 1 },
    })
  ).json();
  expect(
    (
      await request.post(root + "/selections", {
        data: {
          request_id: "choose",
          run_id: run.run_id,
          listing_id: run.report.pending_confirmation[0].listing_id,
          confirmed: true,
        },
      })
    ).status(),
  ).toBe(200);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await page.getByLabel("租约适用范围", { exact: true }).click();
  await page
    .getByRole("option", { name: "新州普通整租住宅", exact: true })
    .click();
  await page.getByText("出租方中介（如适用）", { exact: true }).click();
  await page
    .getByLabel("出租方中介姓名 / 公司", { exact: true })
    .fill("Owner Agency");
  await page
    .getByLabel("出租方中介联系方式（须含电话）", { exact: true })
    .fill("0400000001");
  await page
    .getByLabel("出租方中介送达地址", { exact: true })
    .fill("1 Owner Agency Road");
  await page
    .getByLabel("出租方中介区域（Suburb）", { exact: true })
    .fill("Rhodes");
  await page.getByLabel("出租方中介 State", { exact: true }).fill("NSW");
  await page.getByLabel("出租方中介邮编", { exact: true }).fill("2138");
  await page.getByText("租客代理（如适用）", { exact: true }).click();
  await page
    .getByLabel("租客代理姓名 / 公司", { exact: true })
    .fill("Tenant Representative");
  await page.getByLabel("租客代理联系方式", { exact: true }).fill("0400000002");
  await page
    .getByLabel("租客代理送达地址", { exact: true })
    .fill("2 Representative Road");
  await page
    .getByLabel("租客代理区域（Suburb）", { exact: true })
    .fill("Glebe");
  await page.getByLabel("租客代理 State", { exact: true }).fill("NSW");
  await page.getByLabel("租客代理邮编", { exact: true }).fill("2037");
  const pick = async (label: string, option: string) => {
    const control = page.getByLabel(label, { exact: true });
    await control.click();
    const list = await control.getAttribute("aria-controls");
    await page
      .locator(`[id="${list}"]`)
      .getByRole("option", { name: option, exact: true })
      .click();
  };
  await pick("是否另付用水费", "否");
  await pick("烟雾报警器类型", "电池供电");
  await pick("报警器电池是否可由租客更换", "是");
  await page.getByLabel("报警器电池型号", { exact: true }).fill("AA");
  await pick("出租方是否同意电子送达", "是");
  await page
    .getByLabel("出租方电子送达邮箱", { exact: true })
    .fill("owner@example.com");
  await pick("租客是否同意电子送达", "否");
  await expect(
    page.getByLabel("租客电子送达邮箱", { exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "核对并填入合同", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "确认保存租约草稿",
    exact: true,
  });
  await modal.getByRole("checkbox").check();
  await modal
    .getByRole("button", { name: "确认保存未签署草稿", exact: true })
    .click();
  const preview = page.getByRole("dialog", {
    name: "合同预览 · v1",
    exact: true,
  });
  await expect(preview).toBeVisible();
  const index = await (await request.get(root + "/lease-drafts")).json();
  const draft = await (
    await request.get(root + "/lease-drafts/" + index.items[0].draft_id)
  ).json();
  expect(draft.fields.agent_name).toBe("Owner Agency");
  expect(draft.fields.tenant_agent_name).toBe("Tenant Representative");
  expect(draft.fields.water_usage).toBe("no");
  expect(draft.fields.electricity_embedded).toBeNull();
  expect(draft.fields.smoke_battery_type).toBe("AA");
  expect(draft.fields.tenant_email_consent).toBe("no");
  expect(draft.fields.tenant_notice_email).toBe("");
  const pdf = await request.get(
    root + "/lease-drafts/" + draft.draft_id + "/pdf?version=1",
  );
  expect(pdf.status()).toBe(200);
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  await preview.getByRole("button", { name: "返回填写", exact: true }).click();
  await page.reload();
  await page.getByText("租客代理（如适用）", { exact: true }).click();
  await expect(
    page.getByLabel("租客代理姓名 / 公司", { exact: true }),
  ).toHaveValue("Tenant Representative");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/lease-form-mobile.png",
    animations: "disabled",
  });
});
