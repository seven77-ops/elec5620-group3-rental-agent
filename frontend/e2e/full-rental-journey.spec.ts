import { expect, test, type Locator, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { confirmRentalNeeds, fillRentalNeeds } from "./fillRentalNeeds";

async function choose(
  page: Page,
  scope: Page | Locator,
  label: string,
  option: string,
) {
  const control = scope.getByLabel(label, { exact: true });
  await control.click();
  const listId = await control.getAttribute("aria-controls");
  expect(listId).toBeTruthy();
  await page
    .locator(".ant-select-dropdown")
    .filter({ has: page.locator(`[id="${listId}"]`) })
    .locator(".ant-select-item-option-content")
    .getByText(option, { exact: true })
    .click();
}

test("完整主流程：找房 → 收藏跟进 → 合同生成复核 → 租后服务 → 报修 → 问题报告与人工建议", async ({
  page,
  request,
}, info) => {
  test.skip(
    process.env.FULL_JOURNEY_ISOLATED !== "1",
    "请通过 scripts/test_full_journey.py 启动隔离环境。",
  );
  test.setTimeout(240_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  let root = "",
    caseId = "",
    address = "",
    agreedRent = 0;
  const today = new Date();
  const start = `${today.getFullYear() + 1}-01-01`;
  const end = `${today.getFullYear() + 2}-01-01`;
  const state = async () => (await request.get(root)).json();
  const living = async () =>
    (await request.get(`${root}/living-services`)).json();
  const screenshot = async (name: string) => {
    const path = info.outputPath(`${name}.png`);
    await page.screenshot({ path, animations: "disabled" });
    await info.attach(name, { path, contentType: "image/png" });
  };

  await test.step("01 从首页新建案例，并通过聊天收集找房条件", async () => {
    await page.goto("/");
    await page
      .getByRole("button", { name: "New demo case", exact: true })
      .click();
    await expect(page).toHaveURL(/\/cases\/[^/]+\/assistant$/);
    caseId = new URL(page.url()).pathname.split("/")[2];
    root = `/api/v1/cases/${caseId}`;
    const input = page.getByRole("textbox", {
      name: "Message to Rental Assistant",
      exact: true,
    });
    await input.fill(
      "想找悉大步行20分钟以内的整租，每周1200澳元，至少1卧1卫，1人入住，不限区域。",
    );
    await input.press("Enter");
    await expect(
      page.locator(".commute-results .commute-home").first(),
    ).toBeVisible();
    const controls = page.getByRole("region", {
      name: "Current housing criteria",
      exact: true,
    });
    await expect(controls).toContainText("Walking");
    await expect(controls).toContainText("≤20 minutes");
    expect((await state()).selection).toBeNull();
    expect((await state()).confirmations).toHaveLength(0);
  });

  await test.step("02 零结果调整方案使用真实计数；用户选择后才改变预算", async () => {
    const reference = await (
      await request.get(
        "/api/v1/listings?min_bedrooms=1&min_bathrooms=1&usyd_mode=walk&usyd_max_minutes=20&sort=rent_asc",
      )
    ).json();
    expect(reference.items.length).toBeGreaterThan(1);
    const cap = reference.items[0].weekly_rent - 25;
    const controls = page.getByRole("region", {
      name: "Current housing criteria",
      exact: true,
    });
    async function budget(value: number) {
      await controls
        .getByRole("button", { name: "Edit budget criteria", exact: true })
        .click();
      const dialog = page.getByRole("dialog", {
        name: "Adjust budget",
        exact: true,
      });
      await dialog
        .getByRole("spinbutton", { name: "Current budget limit", exact: true })
        .fill(String(value));
      await dialog
        .getByRole("button", {
          name: "Apply changes and filter again",
          exact: true,
        })
        .click();
      await expect(dialog).toHaveCount(0);
    }
    await budget(cap);
    await expect(controls).toContainText("Filtered 0 properties");
    const conversations = await (
      await request.get(`${root}/assistant/conversations`)
    ).json();
    const contextUrl = `${root}/assistant/conversations/${conversations.items[0].conversation_id}/recommendation-context`;
    const context = await (await request.get(contextUrl)).json();
    const option = context.alternatives.find(
      (item: { id: string }) => item.id === "budget",
    );
    expect(option.count).toBeGreaterThan(0);
    expect(context.criteria.budget_amount).toBe(cap);
    await controls
      .getByRole("button", {
        name: `${option.label} · Matches available: ${option.count} properties`,
        exact: true,
      })
      .click();
    await expect(controls).toContainText(`Filtered ${option.count} properties`);
    const updated = await (await request.get(contextUrl)).json();
    expect(updated.criteria).toMatchObject({
      budget_amount: cap + 50,
      commute_mode: "walk",
      commute_max_minutes: 20,
    });
    await budget(1200);
    const results = page.locator(".commute-results").last();
    await expect(
      results.getByRole("list", { name: "Recommendation reasons" }),
    ).toHaveCount(0);
    await expect(results).not.toContainText("Average commute");
    await controls
      .getByRole("button", { name: "Edit commute criteria", exact: true })
      .click();
    const commute = page.getByRole("dialog", {
      name: "Adjust commute",
      exact: true,
    });
    await choose(
      page,
      commute,
      "Current travel mode",
      "Public transport (any combination)",
    );
    await commute
      .getByLabel("Current commute limit", { exact: true })
      .fill("30");
    await commute
      .getByRole("button", {
        name: "Apply changes and filter again",
        exact: true,
      })
      .click();
    await expect(commute).toHaveCount(0);
    await expect(controls).toContainText("Public transport ≤30 minutes");
    await expect(
      results.getByRole("list", { name: "Recommendation reasons" }),
    ).toHaveCount(0);
    await expect(results).not.toContainText("Average commute");
    const publicContext = await (await request.get(contextUrl)).json();
    const currentConversation = await (
      await request.get(contextUrl.replace(/\/recommendation-context$/, ""))
    ).json();
    expect(currentConversation.messages.at(-1).listings).toHaveLength(
      publicContext.total,
    );
    await results.getByRole("button", { name: "All", exact: true }).click();
    await expect(results.locator(".commute-home")).toHaveCount(
      Math.min(12, publicContext.total),
    );
    await screenshot("01-recommendations");
  });

  await test.step("03 确认需求，收藏两套并比较；收藏本身不选定房源", async () => {
    await page
      .getByRole("button", { name: "My rental needs", exact: true })
      .click();
    await fillRentalNeeds(page, { budget: 1200, bedrooms: 1, bathrooms: 1 });
    await confirmRentalNeeds(page);
    expect((await state()).confirmations).toHaveLength(1);
    await page
      .getByRole("menuitem", { name: "Housing recommendations", exact: true })
      .click();
    const table = page.getByTestId("real-catalog");
    for (let n = 1; n <= 2; n++) {
      await table
        .getByRole("button", { name: "Save listing", exact: true })
        .first()
        .click();
      await expect(
        table.getByRole("button", { name: "Remove favorite", exact: true }),
      ).toHaveCount(n);
    }
    expect((await state()).selection).toBeNull();
    await page.reload();
    await page
      .getByRole("button", { name: "My favorites (2)", exact: true })
      .click();
    const drawer = page.getByRole("dialog", {
      name: "My favorites",
      exact: true,
    });
    await expect(drawer.getByTestId("favorite-home")).toHaveCount(2);
    await drawer.getByRole("checkbox").nth(0).check();
    await drawer.getByRole("checkbox").nth(1).check();
    await expect(
      drawer.getByRole("table", { name: "Saved listing comparison" }),
    ).toBeVisible();
    await screenshot("02-favorites-comparison");
    await drawer
      .getByRole("button", { name: "Select and follow up", exact: true })
      .first()
      .click();
    expect((await state()).selection).toBeNull();
    await page
      .getByRole("button", { name: "Confirm and start follow-up", exact: true })
      .click();
    await expect(drawer).not.toBeVisible();
    const selected = (await state()).selection;
    address = selected.listing_snapshot.address;
    agreedRent = selected.listing_snapshot.weekly_rent + 20;
    expect(selected.contract_ready).toBe(false);
    await expect(page.getByTestId("candidate-next")).toContainText(address);
  });

  await test.step("04 查看询问清单后直接填写合同，无需录入中介回复", async () => {
    await page
      .getByTestId("candidate-next")
      .getByRole("button", {
        name: "Contact property agent",
        exact: true,
      })
      .click();
    const drawer = page.getByRole("dialog", {
      name: "Contact property agent",
      exact: true,
    });
    await expect(
      drawer.getByLabel("Agent name (optional)", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Record agent reply", exact: true }),
    ).toHaveCount(0);
    await drawer.getByRole("button", { name: "Close", exact: true }).click();
    await page
      .getByRole("menuitem", { name: "Contract assistant", exact: true })
      .click();
    await page
      .getByRole("tab", { name: "Generate lease draft", exact: true })
      .click();
    await expect(
      page.getByLabel("Property address", { exact: true }),
    ).toHaveValue(address);
    await expect(
      page.getByLabel("Proposed rent (AUD)", { exact: true }),
    ).toBeEmpty();
    await page
      .getByLabel("Proposed rent (AUD)", { exact: true })
      .fill(String(agreedRent));
    await choose(page, page, "Rent period", "Weekly");
  });

  await test.step("05 录入双方及中介资料，明确确认后生成并检查真实 PDF", async () => {
    await choose(
      page,
      page,
      "Lease scope",
      "Standard NSW whole-property residential tenancy",
    );
    for (const [label, value] of [
      ["Landlord name", "E2E Example Owner"],
      ["Landlord contact details", "owner@example.com"],
      ["Landlord notice address", "1 Example Road, Sydney NSW 2000"],
      ["Tenant names (one per line)", "E2E Example Tenant"],
      ["Tenant contact details", "tenant@example.com"],
      ["Lease start date", start],
      ["End date", end],
      ["Proposed bond (AUD)", String(agreedRent * 4)],
      ["Maximum agreed occupants", "1"],
      ["First rent payment date", start],
      ["Rent due day", "每周一"],
    ])
      await page.getByLabel(label, { exact: true }).fill(value);
    await choose(page, page, "Lease type", "Fixed term");
    await page
      .getByText("Landlord agent (if applicable)", { exact: true })
      .click();
    for (const [label, value] of [
      ["Landlord agent name / company", "E2E Agency"],
      [
        "Landlord agent contact details (must include phone)",
        "agent@example.com; Phone: 0400000001",
      ],
      ["Landlord agent notice address", "2 Example Road"],
      ["Landlord agent suburb", "Rhodes"],
      ["Landlord agent State", "NSW"],
      ["Landlord agent postcode", "2138"],
    ])
      await page.getByLabel(label, { exact: true }).fill(value);
    await page
      .getByRole("button", { name: "Check and fill contract", exact: true })
      .click();
    const confirm = page.getByRole("dialog", {
      name: "Confirm lease draft save",
      exact: true,
    });
    expect(
      (await (await request.get(`${root}/lease-drafts`)).json()).items,
    ).toHaveLength(0);
    await expect(
      confirm.getByRole("button", {
        name: "Confirm and save unsigned draft",
        exact: true,
      }),
    ).toBeDisabled();
    await confirm.getByRole("checkbox").check();
    await confirm
      .getByRole("button", {
        name: "Confirm and save unsigned draft",
        exact: true,
      })
      .click();
    const preview = page.getByRole("dialog", {
      name: "Contract preview · v1",
      exact: true,
    });
    await expect(preview.locator("iframe")).toHaveAttribute("src", /^blob:/);
    await preview
      .getByRole("button", { name: "Return to form", exact: true })
      .click();
    const pending = page.waitForEvent("download");
    await page
      .getByRole("link", { name: "Download saved v1 PDF", exact: true })
      .click();
    const file = info.outputPath("unsigned-lease-v1.pdf");
    await (await pending).saveAs(file);
    expect((await readFile(file)).subarray(0, 4).toString()).toBe("%PDF");
    const pdf = JSON.parse(
      execFileSync(
        process.env.FULL_JOURNEY_PYTHON!,
        [
          "-c",
          "import json,sys; from pypdf import PdfReader; r=PdfReader(sys.argv[1]); f=r.get_fields(); print(json.dumps({'values':{k:str(v.get('/V','')) for k,v in f.items()}, 'signed':any(v.get('/V') for v in f.values() if v.get('/FT')=='/Sig')}))",
          file,
        ],
        { encoding: "utf8" },
      ),
    );
    // Assert the pinned official template's actual field identities, including
    // the separate landlord-agent and tenant-representative sections.
    expect(pdf.values).toMatchObject({
      "Text field 1.4": "E2E Example Owner",
      "Text field 2.6": "E2E Example Tenant",
      "Text field 2.15": "E2E Agency",
      "Text field 2.16": "2 Example Road",
      "Text field 2.17": "Rhodes",
      "Text field 2.18": "NSW",
      "Text field 2.19": "2138",
      "Text field 2.20": "agent@example.com; Phone: 0400000001",
      "Text field 2.21": "",
      "Text field 3.13": String(agreedRent),
    });
    expect(pdf.signed).toBe(false);
    await info.attach("未签署合同 PDF", {
      path: file,
      contentType: "application/pdf",
    });
    expect((await state()).selection.contract_ready).toBe(false);
  });

  await test.step("05B 上传测试合同复核，查看通过与待确认项目", async () => {
    await page
      .getByRole("tab", { name: "Upload contract for review", exact: true })
      .click();
    const contractRent = agreedRent + 10;
    await page.locator("input[type=file]").setInputFiles({
      name: "e2e-example-lease.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        `Address: ${address}\nLandlord: E2E Example Owner\nTenant: E2E Example Tenant\nRent: AUD ${contractRent} per week whole property\nBond: AUD ${contractRent * 4}\nStart date: ${start}\nEnd date: ${end}\n`,
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
    const results = page.getByRole("region", {
      name: "Contract review results",
      exact: true,
    });
    await expect(
      results.getByRole("heading", {
        name: "Contract check results",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      results.getByRole("region", { name: "Passed checks", exact: true }),
    ).toContainText(address);
    await expect(results).toContainText(String(contractRent));
    expect((await state()).reviews).toHaveLength(1);
    await page.reload();
    await expect(
      results.getByRole("region", { name: "Passed checks", exact: true }),
    ).toContainText(address);
  });

  await test.step("06 Basic home information previews the selected property and saves only after explicit editing", async () => {
    await page
      .getByRole("menuitem", { name: "Aftercare services", exact: true })
      .click();
    expect((await living()).profile.address).toBe("");
    await page.getByRole("button", { name: "My home", exact: true }).click();
    const home = page.getByRole("dialog", { name: "My home", exact: true });
    await expect(home).toContainText(address);
    expect((await living()).profile.address).toBe("");
    await home
      .getByRole("button", { name: "Edit details", exact: true })
      .click();
    await home
      .getByRole("button", { name: "Save details", exact: true })
      .click();
    await expect(
      home.getByRole("button", { name: "Edit details", exact: true }),
    ).toBeVisible();
    expect((await living()).profile).toMatchObject({
      address,
      agent_name: "E2E Agency",
      agent_email: "agent@example.com",
    });
    await home.getByRole("button", { name: "Close", exact: true }).click();
  });

  await test.step("07 查看供应商详情并保存水电选择；搬运与清洁分组展示", async () => {
    await page.getByRole("tab", { name: "Utilities", exact: true }).click();
    const directory = await (
      await request.get("/api/v1/living-providers")
    ).json();
    const power = directory.providers.find(
      (p: { name: string }) => p.name === "AGL",
    );
    await page.locator(`[data-provider-id="${power.id}"]`).click();
    const details = page.getByRole("dialog", {
      name: "AGL · Provider details",
      exact: true,
    });
    await expect(details).toBeVisible();
    await screenshot("03-utility-details");
    await details
      .getByRole("button", { name: "Close details", exact: true })
      .click();
    await choose(page, page, "Electricity provider", "AGL");
    await page
      .getByRole("button", { name: "Save provider selection", exact: true })
      .click();
    expect((await living()).profile.utilities.electricity).toBeNull();
    await page
      .getByRole("button", { name: "Confirm selection", exact: true })
      .click();
    await expect
      .poll(async () => (await living()).profile.utilities.electricity)
      .toBe(power.id);
    await page
      .getByRole("tab", { name: "Moving and cleaning", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Removalists", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Cleaning companies", exact: true }),
    ).toBeVisible();
    const mover = directory.providers.find((p: { categories: string[] }) =>
      p.categories.includes("removalist"),
    );
    await page.locator(`[data-provider-id="${mover.id}"]`).click();
    const modal = page.getByRole("dialog", {
      name: `${mover.name} · Provider details`,
      exact: true,
    });
    await expect(
      modal.getByRole("link", { name: "Company website", exact: true }),
    ).toHaveAttribute("href", mover.website);
    await expect(modal).not.toContainText("Route");
    await modal
      .getByRole("button", { name: "Record quote or booking", exact: true })
      .click();
    const form = page.getByRole("dialog");
    await form.getByLabel("Quote received (AUD)", { exact: true }).fill("250");
    await form.getByLabel("Service date", { exact: true }).fill(start);
    await form
      .getByLabel("Service notes", { exact: true })
      .fill("测试电话报价，尚未向商家预约。");
    await form
      .getByRole("checkbox", {
        name: "I confirm this only saves a record and does not submit a booking to the provider.",
        exact: true,
      })
      .check();
    await form
      .getByRole("button", { name: "Confirm service record", exact: true })
      .click();
    await expect(form).toHaveCount(0);
    expect((await living()).bookings[0]).toMatchObject({
      provider_id: mover.id,
      quote_amount: 250,
      status: "considering",
    });
  });

  await test.step("08 AI 润色报修邮件，用户编辑确认保存，记录后续并在手机恢复", async () => {
    await page.getByRole("tab", { name: "Repairs", exact: true }).click();
    await page
      .getByLabel("Repair email recipient name", { exact: true })
      .fill("E2E Agency");
    await page
      .getByLabel("Issue description", { exact: true })
      .fill("厨房水龙头关闭后仍滴水，请安排维修。");
    await page
      .getByRole("button", { name: "Polish email with AI", exact: true })
      .click();
    await expect(
      page.getByLabel("Polished email body", { exact: true }),
    ).toContainText("Dear E2E Agency");
    expect((await living()).repairs).toHaveLength(0);
    await page
      .getByLabel("Polished email subject", { exact: true })
      .fill("E2E kitchen tap repair");
    await page
      .getByLabel("Polished email body", { exact: true })
      .fill(
        "Dear E2E Agency,\n\nThe kitchen tap is leaking. Please arrange a repair.\n\nThank you.",
      );
    await page
      .getByRole("button", { name: "Save polished repair draft", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Confirm repair draft", exact: true })
      .click();
    const card = page.locator(".living-repair-card");
    await expect(card).toContainText("E2E kitchen tap repair");
    await card
      .getByRole("button", { name: "Record follow-up", exact: true })
      .click();
    const modal = page.getByRole("dialog", {
      name: "Record repair follow-up",
      exact: true,
    });
    await modal
      .getByLabel("Reply or my notes", { exact: true })
      .fill("测试记录：已联系中介，等待安排维修。");
    await modal
      .getByRole("button", { name: "Check and save follow-up", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Confirm repair follow-up", exact: true })
      .click();
    await expect(modal).toHaveCount(0);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    await expect(card).toContainText("测试记录：已联系中介，等待安排维修。");
    await expect(card).toContainText("Draft prepared · Not sent");
    const saved = await living();
    expect(saved.repairs).toHaveLength(1);
    expect(saved.repairs[0].email).toMatchObject({
      to: "agent@example.com",
      subject: "E2E kitchen tap repair",
      delivery_status: "prepared_not_sent",
    });
    expect(saved.bookings).toHaveLength(1);
    expect(saved.profile.address).toBe(address);
    expect((await state()).selection.listing_snapshot.address).toBe(address);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await screenshot("04-aftercare-mobile");
    await info.attach("final-state", {
      body: JSON.stringify({ case: await state(), living: saved }, null, 2),
      contentType: "application/json",
    });
  });

  await test.step("09 Report an issue, review the evidence and return advice to History", async () => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole("tab", { name: "Issue report", exact: true }).click();
    expect((await state()).aftercare_case_id).toBeNull();
    const form = page.getByRole("region", {
      name: "Report issue",
      exact: true,
    });
    await choose(page, form, "Issue type", "Furniture");
    await form
      .getByLabel("Issue description", { exact: true })
      .fill("Fictional broken chair, reported for review.");
    await form
      .getByRole("button", { name: "Submit report", exact: true })
      .click();
    const history = page.getByRole("region", {
      name: "Issue report history",
      exact: true,
    });
    await expect(history).toContainText("Fictional broken chair");
    await page
      .getByRole("menuitem", { name: "Human review", exact: true })
      .click();
    const review = page.locator(
      `[data-testid="operator-review"][data-case-id="${caseId}"]`,
    );
    await review
      .getByLabel("Review advice", { exact: true })
      .fill(
        "Ask the agent to inspect the chair and retain a dated photograph.",
      );
    await review
      .getByRole("button", {
        name: "Save advice and complete review",
        exact: true,
      })
      .click();
    await expect(
      page.getByRole("region", { name: "Review history", exact: true }),
    ).toContainText("Ask the agent to inspect the chair");
    await page
      .locator(`[data-testid="operator-review"][data-case-id="${caseId}"]`)
      .getByRole("button", { name: "View report", exact: true })
      .click();
    await expect(history).toContainText("Ask the agent to inspect the chair");
    const finalCase = await state(),
      finalLiving = await living();
    expect(finalCase.aftercare_case_id).toBeNull();
    expect(finalLiving.profile.address).toBe(address);
    expect(finalLiving.repairs).toHaveLength(1);
    expect(finalLiving.bookings).toHaveLength(1);
    await info.attach("completed-journey-state", {
      body: JSON.stringify({ case: finalCase, living: finalLiving }, null, 2),
      contentType: "application/json",
    });
    await screenshot("05-issue-history");
    expect(errors).toEqual([]);
  });
});
