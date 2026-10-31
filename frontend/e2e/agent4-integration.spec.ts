import { test, expect, type APIRequestContext } from "@playwright/test";

async function seed(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  let version = 0;
  const command = async (operation: string, payload: unknown) => {
    const r = await request.post("/api/v1/aftercare/commands", {
      data: {
        case_id: c.case_id,
        request_id: crypto.randomUUID(),
        expected_version: version,
        operation,
        payload,
      },
    });
    expect(r.ok(), await r.text()).toBe(true);
    const result = await r.json();
    version = result.version;
    return result;
  };
  const created = await command("create", {
    tenancy: {
      address: "30 Integration Test Street, Sydney NSW",
      jurisdiction: "NSW",
      tenancy_type: "standard_residential",
      confirmed: true,
      source_ref: "user-entered:integration-test",
      source_version: 1,
      rooms: [{ id: "bedroom", name: "Bedrooms" }],
      carpeted: false,
      outdoor: false,
      furnished: false,
      inventory: null,
      inventory_confirmed: false,
      baseline_evidence_refs: [],
    },
    evidence: [],
  });
  const date = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10);
  await command("create_plan", {
    move_out_date: date,
    schedule_confirmed: true,
  });
  return {
    cid: c.case_id as string,
    aftercareId: created.case_id as string,
    command,
  };
}

test("task submission appears in operator inbox and decisions survive reload and case switches", async ({
  page,
  request,
}) => {
  const { cid } = await seed(request);
  await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
  await page
    .getByRole("button", { name: "Edit task", exact: true })
    .first()
    .click();
  const edit = page.getByRole("dialog", {
    name: "Edit task and evidence",
    exact: true,
  });
  await edit.getByRole("checkbox", { name: /Human review needed/ }).check();
  await edit
    .getByLabel("Reason for review", { exact: true })
    .fill("入住时已有的墙面痕迹，请核对记录");
  await edit.getByRole("button", { name: "Save task", exact: true }).click();
  await expect(edit).toBeHidden();
  // Switch to a different tenant case: the operator inbox must still find the submission.
  const other = await (
    await request.post("/api/v1/cases", { data: {} })
  ).json();
  await page.goto(`/cases/${other.case_id}/assistant`);
  await page
    .getByRole("menuitem", { name: "Human review", exact: true })
    .click();
  await page
    .getByLabel("Local operator key", { exact: true })
    .fill("test-only-local");
  await page
    .getByRole("button", { name: "Load review records", exact: true })
    .click();
  const item = page.getByTestId("operator-review").filter({ hasText: cid });
  await expect(item).toContainText("入住时已有的墙面痕迹，请核对记录");
  await expect(item).toContainText("30 Integration Test Street");
  await page
    .getByLabel("Human review notes", { exact: true })
    .fill("请补充入住检查记录，暂缓处理");
  await page.getByLabel("Aftercare review decision", { exact: true }).click();
  await page.getByText("Defer · Retain restrictions", { exact: true }).click();
  await item
    .getByRole("button", {
      name: "Record selected review decision",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Confirm record", exact: true })
    .click();
  await expect(item).toContainText("请补充入住检查记录，暂缓处理");
  await page
    .getByLabel("Human review notes", { exact: true })
    .fill("已核对资料，可继续准备事实询问草稿");
  await page.getByLabel("Aftercare review decision", { exact: true }).click();
  await page
    .getByText("Checked · Allow draft preparation", { exact: true })
    .click();
  await item
    .getByRole("button", {
      name: "Record selected review decision",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Confirm record", exact: true })
    .click();
  const history = page.getByRole("region", {
    name: "Review history",
    exact: true,
  });
  await expect(history).toContainText("已核对资料，可继续准备事实询问草稿");
  await page.reload();
  await page
    .getByLabel("Local operator key", { exact: true })
    .fill("test-only-local");
  await page
    .getByRole("button", { name: "Load review records", exact: true })
    .click();
  await expect(history).toContainText("请补充入住检查记录，暂缓处理");
  await expect(history).toContainText("已核对资料，可继续准备事实询问草稿");
  await page.screenshot({
    path: "/tmp/agent4-operator-history.png",
    fullPage: true,
  });
  await history
    .getByRole("button", { name: "View aftercare record", exact: true })
    .click();
  await page.getByRole("tab", { name: /Review items/ }).click();
  await expect(
    page.getByRole("tabpanel", { name: /Review items/ }),
  ).toContainText("已核对资料，可继续准备事实询问草稿");
});

test("deduction helper, constrained AI draft, reminder and case progress share the saved case", async ({
  page,
  request,
}) => {
  const { cid, command } = await seed(request);
  await command("open_bond", {
    bond_reference: "TEST-RBO-30",
    deposit_evidence_ref: null,
  });
  await command("activate_bond", {
    entry: {
      text: "已交还钥匙，等待押金结果",
      occurred_at: new Date().toISOString(),
      tenant_confirmed: true,
      evidence_refs: [],
      claims: [],
      conflicting_evidence: false,
    },
  });
  await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
  await page.getByRole("tab", { name: "Bond follow-up", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Record new facts or deduction claims",
      exact: true,
    })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Record new facts or deduction claims",
    exact: true,
  });
  await dialog
    .getByText(
      "Optional: Use AI to extract deduction claims from the agent/landlord text",
      { exact: true },
    )
    .click();
  await dialog
    .getByPlaceholder("Paste the original agent or landlord email/message")
    .fill("We propose $180 for carpet cleaning.");
  await dialog
    .getByRole("checkbox", {
      name: /I agree to send only this text to the configured AI/,
    })
    .check();
  await dialog
    .getByRole("button", { name: "Extract deduction claims", exact: true })
    .click();
  await expect(dialog).toContainText("Added 1 candidate claims");
  await dialog
    .getByRole("button", { name: "Confirm and record", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  await page.getByRole("button", { name: /Prepare draft with AI/ }).click();
  const confirm = page.getByRole("dialog");
  await confirm
    .getByRole("button", { name: "Agree and generate", exact: true })
    .click();
  await expect(
    page.getByText("Reported deduction claim: AUD 180.00", { exact: false }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Local reminders", exact: true }).click();
  const next = new Date(Date.now() + 2 * 86400000).toISOString().slice(0, 10);
  await page
    .getByLabel("Bond follow-up reminder date", { exact: true })
    .fill(next);
  await page
    .getByRole("button", {
      name: "Save reminder time (Sydney time)",
      exact: true,
    })
    .click();
  await expect(
    page.getByText(new RegExp(`Current reminder time:\\s*${next}`)),
  ).toBeVisible();
  await page
    .getByRole("menuitem", { name: "Case progress", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Case progress", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Bond follow-up Awaiting outcome/)).toBeVisible();
});
