import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

async function record(request: APIRequestContext, cid: string) {
  const c = await (await request.get(`/api/v1/cases/${cid}`)).json();
  return (
    await request.get(`/api/v1/aftercare/cases/${c.aftercare_case_id}`)
  ).json();
}
async function command(
  request: APIRequestContext,
  cid: string,
  operation: string,
  payload: unknown,
) {
  const c = await (await request.get(`/api/v1/cases/${cid}`)).json();
  const v = c.aftercare_case_id ? (await record(request, cid)).version : 0;
  const r = await request.post("/api/v1/aftercare/commands", {
    data: {
      case_id: cid,
      request_id: crypto.randomUUID(),
      expected_version: v,
      operation,
      payload,
    },
  });
  expect(r.ok(), await r.text()).toBeTruthy();
}
async function seeded(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await command(request, c.case_id, "create", {
    tenancy: {
      tenancy_id: "test-tenancy",
      tenant_id: "test-tenant",
      address: "1 Example Street, Sydney NSW (fictional test)",
      jurisdiction: "NSW",
      tenancy_type: "standard_residential",
      confirmed: true,
      source_ref: "user-entered:recovery-test",
      source_version: 1,
      rooms: [{ id: "room-1", name: "Bedroom" }],
      carpeted: false,
      outdoor: false,
      furnished: false,
      inventory: null,
      inventory_confirmed: false,
      baseline_evidence_refs: [],
    },
    evidence: [],
  });
  return c.case_id as string;
}
async function activate(page: Page) {
  await page
    .getByRole("button", { name: "确认事实并激活跟进", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "确认事实并激活跟进",
    exact: true,
  });
  await dialog
    .getByLabel("租客报告的事实", { exact: true })
    .fill("Fictional test: tenant reports deposit paid.");
  await dialog.getByRole("button", { name: "确认并记录", exact: true }).click();
  await expect(dialog).toBeHidden();
}

test("unknown tenancy can be completed in the same case before confirming a plan", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=moveout`);
  await page
    .getByLabel("租约地址", { exact: true })
    .fill("1 Example Street, Sydney NSW (fictional test)");
  await page
    .getByRole("checkbox", {
      name: "我已核对并确认上述租约、房间、家具及资料来源。",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "确认资料并创建租后案件", exact: true })
    .click();
  await expect(page.getByText("已确认租约资料", { exact: true })).toBeVisible();
  await command(request, c.case_id, "add_evidence", {
    evidence: {
      evidence_id: "preserved-evidence",
      kind: "photo",
      source_ref: "user-entered:existing-evidence",
      source_version: 1,
      recorded_at: new Date().toISOString(),
      summary: "Existing fictional photo metadata",
    },
  });
  await page.reload();
  const before = await record(request, c.case_id);
  await expect(page.getByText("先补齐房屋资料", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "补齐资料后生成计划", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "补充租约资料",
    exact: true,
  });
  await expect(dialog.getByLabel("租约地址", { exact: true })).toHaveValue(
    before.tenancy.address,
  );
  for (const label of ["有地毯", "有室外区域", "带家具"]) {
    await dialog.getByRole("combobox", { name: label, exact: true }).click();
    await page
      .locator(".ant-select-dropdown:visible")
      .getByText("否", { exact: true })
      .last()
      .click();
    await expect(page.locator(".ant-select-dropdown:visible")).toHaveCount(0);
  }
  await dialog.getByRole("button", { name: "添加房间", exact: true }).click();
  await dialog.getByLabel("房间名称", { exact: true }).fill("Bedroom");
  await expect(
    dialog.getByRole("button", { name: "确认并保存租约资料", exact: true }),
  ).toBeDisabled();
  await dialog
    .getByRole("checkbox", {
      name: "我已核对并确认上述租约、房间、家具及资料来源。",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("button", { name: "确认并保存租约资料", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  const saved = await record(request, c.case_id);
  expect(saved.case_id).toBe(before.case_id);
  expect(saved.tenancy.tenancy_id).toBe(before.tenancy.tenancy_id);
  expect(saved.tenancy.source_version).toBe(before.tenancy.source_version + 1);
  expect(saved.evidence).toEqual(before.evidence);
  expect(saved.tenancy.carpeted).toBe(false);
  await page
    .getByRole("button", { name: "生成并确认计划", exact: true })
    .click();
  await page.getByRole("button", { name: "确认计划", exact: true }).click();
  await expect
    .poll(async () => (await record(request, c.case_id)).plan?.state)
    .toBe("Active");
  await expect(
    page.getByRole("button", { name: "补充租约资料", exact: true }),
  ).toBeDisabled();
});

test("blank bond draft can receive a reference and activate once without duplicating history", async ({
  page,
  request,
}) => {
  const cid = await seeded(request);
  await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
  await page.getByRole("tab", { name: "押金跟进", exact: true }).click();
  await page.getByRole("button", { name: "建立押金跟进", exact: true }).click();
  await page
    .getByRole("button", { name: "确认事实并激活跟进", exact: true })
    .click();
  const blocked = page.getByRole("dialog", {
    name: "确认事实并激活跟进",
    exact: true,
  });
  await blocked
    .getByLabel("租客报告的事实", { exact: true })
    .fill("Fictional activation before reference provided");
  await blocked
    .getByRole("button", { name: "确认并记录", exact: true })
    .click();
  await expect(blocked.getByText(/请先补录押金编号/).first()).toBeVisible();
  await blocked
    .getByRole("button", { name: "取消本次编辑", exact: true })
    .click();
  expect((await record(request, cid)).bond.history).toHaveLength(0);
  await page.getByRole("button", { name: "补录押金资料", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "补录押金资料",
    exact: true,
  });
  await expect(
    dialog.getByRole("button", { name: "保存押金资料", exact: true }),
  ).toBeDisabled();
  await dialog
    .getByLabel("押金记录编号", { exact: true })
    .fill("FICTIONAL-BOND-RECOVERY");
  await dialog
    .getByRole("button", { name: "保存押金资料", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  expect((await record(request, cid)).bond.state).toBe("Draft");
  let sent: any;
  await page.route("**/api/v1/aftercare/commands", async (route) => {
    if (route.request().postDataJSON().operation === "activate_bond")
      sent = route.request().postDataJSON();
    await route.continue();
  });
  await activate(page);
  const saved = await record(request, cid);
  expect(saved.bond.state).toBe("AwaitingOutcome");
  expect(saved.bond.history).toHaveLength(1);
  const retry = await request.post("/api/v1/aftercare/commands", {
    data: sent,
  });
  expect(retry.ok()).toBeTruthy();
  expect((await record(request, cid)).bond.history).toHaveLength(1);
  await expect(
    page.getByRole("button", { name: "补录押金资料", exact: true }),
  ).toHaveCount(0);
});

test("a registered deposit record can activate the same blank bond draft", async ({
  page,
  request,
}) => {
  const cid = await seeded(request);
  await command(request, cid, "add_evidence", {
    evidence: {
      evidence_id: "deposit-recovery",
      kind: "deposit_record",
      source_ref: "user-entered:deposit-test",
      source_version: 1,
      recorded_at: new Date().toISOString(),
      summary: "Fictional deposit receipt",
    },
  });
  await command(request, cid, "add_evidence", {
    evidence: {
      evidence_id: "not-a-deposit",
      kind: "other",
      source_ref: "user-entered:other-test",
      source_version: 1,
      recorded_at: new Date().toISOString(),
      summary: "Other evidence",
    },
  });
  await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
  await page.getByRole("tab", { name: "押金跟进", exact: true }).click();
  await page.getByRole("button", { name: "建立押金跟进", exact: true }).click();
  const before = await record(request, cid);
  await page.getByRole("button", { name: "补录押金资料", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "补录押金资料",
    exact: true,
  });
  await dialog.getByRole("combobox", { name: "押金凭证", exact: true }).click();
  await expect(page.getByRole("option", { name: /not-a-deposit/ })).toHaveCount(
    0,
  );
  await page
    .locator(".ant-select-dropdown:visible")
    .getByText("deposit-recovery · Fictional deposit receipt", { exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "保存押金资料", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  const saved = await record(request, cid);
  expect(saved.case_id).toBe(before.case_id);
  expect(saved.evidence).toEqual(before.evidence);
  expect(saved.bond.bond_reference).toBeNull();
  expect(saved.bond.deposit_evidence_ref).toBe("deposit-recovery");
  await activate(page);
  expect((await record(request, cid)).bond.state).toBe("AwaitingOutcome");
});

for (const kind of ["tenancy", "bond"] as const) {
  test(`${kind} correction retries a lost response using the same request and preserves input`, async ({
    page,
    request,
  }) => {
    const cid = await seeded(request);
    if (kind === "bond")
      await command(request, cid, "open_bond", {
        bond_reference: null,
        deposit_evidence_ref: null,
      });
    const before = await record(request, cid);
    const operation = kind === "tenancy" ? "revise_tenancy" : "open_bond";
    const sent: unknown[] = [];
    await page.route("**/api/v1/aftercare/commands", async (route) => {
      const body = route.request().postDataJSON();
      if (body.operation !== operation) return route.continue();
      sent.push(body);
      if (sent.length === 1) {
        const committed = await route.fetch();
        expect(committed.ok()).toBeTruthy();
        return route.abort("failed");
      }
      await route.continue();
    });
    await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
    if (kind === "bond")
      await page.getByRole("tab", { name: "押金跟进", exact: true }).click();
    const title = kind === "tenancy" ? "补充租约资料" : "补录押金资料";
    await page.getByRole("button", { name: title, exact: true }).click();
    const dialog = page.getByRole("dialog", { name: title, exact: true });
    const field = dialog.getByLabel(
      kind === "tenancy" ? "租约地址" : "押金记录编号",
      { exact: true },
    );
    const value =
      kind === "tenancy"
        ? "2 Example Street, Sydney NSW (fictional test)"
        : "FICTIONAL-LOST-RESPONSE";
    await field.fill(value);
    if (kind === "tenancy")
      await dialog
        .getByRole("checkbox", {
          name: "我已核对并确认上述租约、房间、家具及资料来源。",
          exact: true,
        })
        .check();
    await dialog
      .getByRole("button", {
        name: kind === "tenancy" ? "确认并保存租约资料" : "保存押金资料",
        exact: true,
      })
      .click();
    await expect(
      dialog.getByRole("button", { name: "重试原操作", exact: true }),
    ).toBeVisible();
    await expect(field).toHaveValue(value);
    await dialog
      .getByRole("button", { name: "重试原操作", exact: true })
      .click();
    await expect(dialog).toBeHidden();
    expect(sent).toHaveLength(2);
    expect(sent[1]).toEqual(sent[0]);
    const saved = await record(request, cid);
    expect(saved.version).toBe(before.version + 1);
    expect(saved.case_id).toBe(before.case_id);
    expect(saved.evidence).toEqual(before.evidence);
    if (kind === "tenancy") {
      expect(saved.tenancy.address).toBe(value);
      expect(saved.tenancy.source_version).toBe(2);
    } else {
      expect(saved.bond.bond_reference).toBe(value);
      expect(saved.bond.history).toEqual(before.bond.history);
    }
  });
}

test("tenancy version conflict keeps input and refreshes the version before resaving", async ({
  page,
  request,
}) => {
  const cid = await seeded(request);
  await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
  await page.getByRole("button", { name: "补充租约资料", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "补充租约资料",
    exact: true,
  });
  await dialog
    .getByLabel("租约地址", { exact: true })
    .fill("3 Example Street, Sydney NSW (fictional test)");
  await dialog
    .getByRole("checkbox", {
      name: "我已核对并确认上述租约、房间、家具及资料来源。",
      exact: true,
    })
    .check();
  await command(request, cid, "add_evidence", {
    evidence: {
      evidence_id: "concurrent-photo",
      kind: "photo",
      source_ref: "user-entered:concurrent-test",
      source_version: 1,
      recorded_at: new Date().toISOString(),
      summary: "Fictional concurrent evidence",
    },
  });
  await dialog
    .getByRole("button", { name: "确认并保存租约资料", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "读取最新状态并保留输入", exact: true }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "读取最新状态并保留输入", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "读取最新状态并保留输入", exact: true }),
  ).toHaveCount(0);
  await expect(dialog.getByLabel("租约地址", { exact: true })).toHaveValue(
    "3 Example Street, Sydney NSW (fictional test)",
  );
  await dialog
    .getByRole("checkbox", {
      name: "我已核对并确认上述租约、房间、家具及资料来源。",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("button", { name: "确认并保存租约资料", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  const saved = await record(request, cid);
  expect(saved.tenancy.address).toBe(
    "3 Example Street, Sydney NSW (fictional test)",
  );
  expect(
    saved.evidence.some(
      (e: { evidence_id: string }) => e.evidence_id === "concurrent-photo",
    ),
  ).toBeTruthy();
});
