import { test, expect, type APIRequestContext } from "@playwright/test";
async function seed(request: APIRequestContext, complete = false) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const r = await request.post("/api/v1/aftercare/commands", {
    data: {
      case_id: c.case_id,
      request_id: crypto.randomUUID(),
      expected_version: 0,
      operation: "create",
      payload: {
        tenancy: {
          tenancy_id: "readable-test",
          tenant_id: "test-tenant",
          address: "1 Example Street, Sydney NSW (fictional test)",
          jurisdiction: "NSW",
          tenancy_type: "standard_residential",
          confirmed: true,
          source_ref: "user-entered:tenant-confirmation",
          source_version: 1,
          rooms: complete ? [{ id: "room-1", name: "卧室" }] : null,
          carpeted: true,
          outdoor: false,
          furnished: true,
          inventory: null,
          inventory_confirmed: true,
          baseline_evidence_refs: [],
        },
        evidence: [
          {
            evidence_id: "deposit-readable",
            kind: "deposit_record",
            source_ref: "user-entered:receipt-test",
            source_version: 1,
            recorded_at: new Date().toISOString(),
            summary: "测试押金凭证",
          },
        ],
      },
    },
  });
  expect(r.ok(), await r.text()).toBeTruthy();
  return c.case_id as string;
}
test("missing property details guide the user before sending a plan request", async ({
  page,
  request,
}) => {
  const cid = await seed(request);
  const commands: string[] = [];
  await page.route("**/api/v1/aftercare/commands", async (route) => {
    commands.push(route.request().postDataJSON().operation);
    await route.continue();
  });
  await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
  const plan = page.getByRole("region", { name: "退租计划", exact: true });
  await expect(plan).toContainText("先补齐房屋资料");
  await expect(plan).toContainText("房间");
  await expect(plan).toContainText("家具清单");
  await plan
    .getByRole("button", { name: "补齐资料后生成计划", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "补充租约资料", exact: true }),
  ).toBeVisible();
  expect(commands).not.toContain("create_plan");
  await expect(
    page.getByText("Room layout is unknown", { exact: false }),
  ).toHaveCount(0);
});
test("tenancy evidence drawer presents readable facts and keeps raw data collapsed", async ({
  page,
  request,
}) => {
  const cid = await seed(request);
  await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
  await page
    .getByRole("button", { name: "查看资料与证据", exact: true })
    .click();
  const d = page.getByRole("dialog", { name: "已确认资料与证据", exact: true });
  await expect(
    d.getByRole("heading", { name: "房屋概览", exact: true }),
  ).toBeVisible();
  await expect(d).toContainText("新南威尔士州");
  await expect(d).toContainText("标准住宅租约");
  await expect(d).toContainText("尚未添加房间");
  await expect(d).toContainText("尚未添加家具清单");
  await expect(d).toContainText("押金凭证");
  await expect(d).toContainText("测试押金凭证");
  await expect(d.locator("pre:visible")).toHaveCount(0);
  await expect(d).not.toContainText("user-entered:tenant-confirmation");
  await d.getByRole("button", { name: "查看原始资料", exact: true }).click();
  await expect(d.locator("pre:visible")).toContainText("tenancy_id");
  await d.getByRole("button", { name: "查看原始资料", exact: true }).click();
  await page.setViewportSize({ width: 360, height: 800 });
  await expect
    .poll(async () => (await d.boundingBox())?.width ?? 0)
    .toBeLessThanOrEqual(360);
  await d.getByRole("button", { name: "补充租约资料", exact: true }).click();
  await expect(d).toBeHidden();
  await expect(
    page.getByRole("dialog", { name: "补充租约资料", exact: true }),
  ).toBeVisible();
});
test("backend clarification is displayed in Chinese with diagnostics collapsed", async ({
  page,
  request,
}) => {
  const cid = await seed(request, true);
  // Simulate a complete UI snapshot while the authoritative command still
  // requires missing details: server validation must remain visible and actionable.
  await page.route("**/api/v1/aftercare/cases/*", async (route) => {
    const r = await route.fetch();
    const data = await r.json();
    data.tenancy.inventory = [{ id: "item-1", name: "床", room_id: "room-1" }];
    await route.fulfill({ json: data });
  });
  await page.goto(`/cases/${cid}/aftercare?tab=moveout`);
  await page
    .getByRole("button", { name: "生成并确认计划", exact: true })
    .click();
  await page.getByRole("button", { name: "确认计划", exact: true }).click();
  const guidance = page.getByRole("region", { name: "操作提示", exact: true });
  await expect(guidance).toContainText("资料还需补充");
  await expect(guidance).not.toContainText(
    "Furnished inventory is unavailable",
  );
  await expect(
    guidance.getByRole("button", { name: "查看错误详情", exact: true }),
  ).toBeVisible();
  await expect(guidance).not.toContainText("needs_clarification");
});
