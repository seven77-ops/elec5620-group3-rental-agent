import { test, expect, type APIRequestContext } from "@playwright/test";
import { writeFile } from "node:fs/promises";
async function seed(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json(),
    root = `/api/v1/cases/${c.case_id}`;
  await request.post(root + "/profile-confirmations", {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  const r = await (
    await request.post(root + "/evaluations", {
      data: { request_id: "run", confirmation_version: 1 },
    })
  ).json();
  await request.post(root + "/selections", {
    data: {
      request_id: "choose",
      run_id: r.run_id,
      listing_id: r.report.pending_confirmation[0].listing_id,
      confirmed: true,
    },
  });
  return { c, root };
}
test("calendar lease lengths calculate end dates, preserve explicit custom dates and clear periodic terms", async ({
  page,
  request,
}) => {
  const { c } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await page.getByLabel("租期类型", { exact: true }).click();
  await page.getByRole("option", { name: "固定租期", exact: true }).click();
  await expect(
    page
      .locator(".ant-form-item")
      .filter({ has: page.getByLabel("租期时长", { exact: true }) }),
  ).toContainText("1年");
  await page.getByLabel("租期时长", { exact: true }).click();
  await page.getByRole("option", { name: "6个月", exact: true }).click();
  await page.getByLabel("起租日期", { exact: true }).fill("2026-08-31");
  await expect(page.getByLabel("结束日期", { exact: true })).toHaveValue(
    "2027-02-28",
  );
  await expect(page.getByLabel("结束日期", { exact: true })).toBeDisabled();
  await page.getByLabel("租期时长", { exact: true }).click();
  await page.getByRole("option", { name: "1年", exact: true }).click();
  await expect(page.getByLabel("结束日期", { exact: true })).toHaveValue(
    "2027-08-31",
  );
  await page.getByLabel("租期时长", { exact: true }).click();
  await page.getByRole("option", { name: "自定义日期", exact: true }).click();
  await expect(page.getByLabel("结束日期", { exact: true })).toBeEnabled();
  await page.getByLabel("结束日期", { exact: true }).fill("2026-08-01");
  await page
    .getByRole("button", { name: "核对并填入合同", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "确认保存租约草稿", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("结束日期须晚于起租日期。", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("租期类型", { exact: true }).click();
  await page
    .getByRole("option", { name: "持续租约（无结束日期）", exact: true })
    .click();
  await expect(page.getByLabel("结束日期", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("结束日期", { exact: true })).toBeDisabled();
});
test("chosen addresses populate structured PDF boxes, additional fields and a standard calendar term", async ({
  page,
  request,
}) => {
  const { c, root } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  for (const [prefix, street, suburb, postcode] of [
    ["出租方", "1 Example Street", "Redfern", "2016"],
    ["租客", "Unit 2001, 10 Example Street", "Redfern", "2016"],
    ["出租方中介", "2 Example Road", "Burwood", "2134"],
  ]) {
    if (prefix === "出租方中介")
      await page.getByText("出租方中介（如适用）", { exact: true }).click();
    await page.getByLabel(`${prefix}送达地址`, { exact: true }).fill(street);
    await page.getByLabel(`${prefix} State`, { exact: true }).fill("NSW");
    await page
      .getByLabel(`${prefix}区域（Suburb）`, { exact: true })
      .fill(suburb);
    const field =
      prefix === "出租方" ? "landlord" : prefix === "租客" ? "tenant" : "agent";
    await page
      .locator(`#${field}_notice_suburb_list`)
      .getByRole("option", { name: `${suburb} · NSW ${postcode}`, exact: true })
      .click();
    await expect(
      page.getByLabel(`${prefix}送达地址`, { exact: true }),
    ).toHaveValue(street);
    await expect(
      page.getByLabel(`${prefix}区域（Suburb）`, { exact: true }),
    ).toHaveValue(suburb);
    await expect(
      page.getByLabel(`${prefix} State`, { exact: true }),
    ).toHaveValue("NSW");
    await expect(page.getByLabel(`${prefix}邮编`, { exact: true })).toHaveValue(
      postcode,
    );
  }
  await page.getByLabel("租约适用范围", { exact: true }).click();
  await page
    .getByRole("option", { name: "新州普通整租住宅", exact: true })
    .click();
  await page.getByLabel("租期类型", { exact: true }).click();
  await page.getByRole("option", { name: "固定租期", exact: true }).click();
  await page.getByLabel("租期时长", { exact: true }).click();
  await page.getByRole("option", { name: "6个月", exact: true }).click();
  await page.getByLabel("起租日期", { exact: true }).fill("2026-08-31");
  await page.getByText("签约信息（可选）", { exact: true }).click();
  await page.getByLabel("拟定签约日期", { exact: true }).fill("2026-08-20");
  await page.getByLabel("拟定签约地点", { exact: true }).fill("Sydney");
  await page
    .getByRole("button", { name: "核对并填入合同", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "确认保存租约草稿",
    exact: true,
  });
  await expect(modal).toContainText("2016");
  await expect(modal).toContainText("6个月");
  await modal.getByRole("checkbox").check();
  await modal
    .getByRole("button", { name: "确认保存未签署草稿", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "合同预览 · v1", exact: true }),
  ).toBeVisible();
  const list = await (await request.get(root + "/lease-drafts")).json();
  const draft = await (
    await request.get(root + `/lease-drafts/${list.items[0].draft_id}`)
  ).json();
  expect(draft.fields.landlord_notice_postcode).toBe("2016");
  expect(draft.fields.tenant_notice_suburb).toBe("Redfern");
  expect(draft.fields.agent_notice_postcode).toBe("2134");
  expect(draft.fields.end_date).toBe("2027-02-28");
  expect(draft.fields.lease_term_months).toBe(6);
  const pdf = await request.get(
    root + `/lease-drafts/${list.items[0].draft_id}/pdf?version=1`,
  );
  expect(pdf.ok()).toBe(true);
  await writeFile("/tmp/lease-autofill-browser.pdf", await pdf.body());
  await page.reload();
  await expect(page.getByLabel("出租方邮编", { exact: true })).toHaveValue(
    "2016",
  );
  await expect(page.getByLabel("结束日期", { exact: true })).toHaveValue(
    "2027-02-28",
  );
});

test("mobile property search ignores late results and permits explicit manual addresses", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 900 });
  const { c } = await seed(request);
  const redfern = await (
    await request.get("/api/v1/lease-addresses?q=Redfern")
  ).json();
  const burwood = await (
    await request.get("/api/v1/lease-addresses?q=Burwood")
  ).json();
  let releaseOld!: () => void;
  const oldGate = new Promise<void>((resolve) => {
    releaseOld = resolve;
  });
  let oldStarted = false;
  await page.route("**/api/v1/lease-addresses?*", async (route) => {
    const q = new URL(route.request().url()).searchParams.get("q");
    if (q === "Redfern") {
      oldStarted = true;
      await oldGate;
      await route.fulfill({ json: redfern });
    } else if (q === "Burwood") await route.fulfill({ json: burwood });
    else await route.fulfill({ json: { items: [], source: "local_catalog" } });
  });
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  const input = page.getByLabel("房屋地址", { exact: true });
  await input.fill("Redfern");
  await expect.poll(() => oldStarted).toBe(true);
  await input.fill("Burwood");
  const list = page.locator("#address_list");
  await expect(list).toContainText("Burwood");
  const oldResponse = page.waitForResponse((r) =>
    r.url().includes("/lease-addresses?q=Redfern"),
  );
  releaseOld();
  await oldResponse;
  await expect(list).not.toContainText("Redfern");
  await list
    .getByRole("option")
    .filter({ has: page.locator('[data-address-kind="address"]') })
    .first()
    .click();
  await expect(page.getByLabel("房屋邮编", { exact: true })).toHaveValue(
    "2134",
  );
  await input.fill("Unit 20, Unlisted Example Road");
  await expect(page.getByLabel("房屋邮编", { exact: true })).toHaveValue("");
  await page.getByLabel("房屋区域（Suburb）", { exact: true }).fill("Sydney");
  await page.getByLabel("房屋 State", { exact: true }).fill("NSW");
  await page.getByLabel("房屋邮编", { exact: true }).fill("2000");
  await expect(input).toHaveValue("Unit 20, Unlisted Example Road");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
