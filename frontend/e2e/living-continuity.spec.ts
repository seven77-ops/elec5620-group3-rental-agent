import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

async function isolatedCase(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  const record = await (await request.get(root)).json();
  return { c, root, record };
}

test("lease source preview is read only, selected import needs actual-tenancy confirmation and survives reload", async ({
  page,
  request,
}) => {
  const { c, root, record: initial } = await isolatedCase(request);
  let record = {
    ...initial,
    profile: { ...initial.profile, agent_phone: "0400000000" },
  };
  const imports: Record<string, unknown>[] = [];
  const source = {
    kind: "lease_draft",
    id: "lease-test",
    version: 2,
    label: "租约草稿",
    token: "source-token-test",
    current: true,
    warning: "草稿不代表实际租约，请先确认。",
  };
  const values = {
    address: "23 Test Road, Sydney NSW",
    agent_name: "Test Agent",
    lease_start_date: "2026-11-01",
    lease_end_date: "2027-10-31",
  };
  await page.route(`**${root}`, (route) => route.fulfill({ json: record }));
  await page.route(`**${root}/tenancy-source`, (route) =>
    route.fulfill({
      json: {
        expected_version: record.version,
        source,
        values,
        previous: record.profile,
        linked_source: null,
        changed: true,
      },
    }),
  );
  await page.route(`**${root}/tenancy-import`, async (route) => {
    const body = route.request().postDataJSON();
    imports.push(body);
    const chosen = Object.fromEntries(
      body.fields.map((key: keyof typeof values) => [key, values[key]]),
    );
    record = {
      ...record,
      version: record.version + 1,
      profile: { ...record.profile, ...chosen },
      tenancy_source: source,
    };
    await route.fulfill({ json: record });
  });
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await page
    .getByRole("button", { name: "View lease source", exact: true })
    .click();
  const preview = page.getByRole("dialog", {
    name: "Check lease source",
    exact: true,
  });
  await expect(preview).toContainText("23 Test Road, Sydney NSW");
  await expect(preview).toContainText("v2");
  await expect(
    preview.getByRole("button", {
      name: "Import selected details",
      exact: true,
    }),
  ).toBeDisabled();
  await preview.getByRole("button", { name: "Cancel", exact: true }).click();
  expect(imports).toHaveLength(0);
  await page
    .getByRole("button", { name: "View lease source", exact: true })
    .click();
  await preview
    .getByRole("checkbox", {
      name: "Import Agent or landlord name",
      exact: true,
    })
    .uncheck();
  await preview
    .getByRole("checkbox", {
      name: "I confirm these details correspond to my actual lease.",
      exact: true,
    })
    .check();
  await preview
    .getByRole("button", { name: "Import selected details", exact: true })
    .click();
  expect(imports).toHaveLength(0);
  await page
    .getByRole("button", { name: "Confirm lease import", exact: true })
    .click();
  await expect(preview).toHaveCount(0);
  expect(imports).toHaveLength(1);
  expect(imports[0]).toMatchObject({
    confirmed: true,
    actual_tenancy_confirmed: true,
    expected_version: initial.version,
    source_token: source.token,
  });
  expect(imports[0].fields).toEqual([
    "address",
    "lease_start_date",
    "lease_end_date",
  ]);
  expect(record.profile.agent_phone).toBe("0400000000");
  expect(record.profile.agent_name).toBe("");
  await page.reload();
  await expect(page.getByText(values.address, { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Edit home and contacts", exact: true })
    .click();
  await expect(
    page.getByLabel("Lease start date", { exact: true }),
  ).toHaveValue(values.lease_start_date);
  await expect(page.getByLabel("Lease end date", { exact: true })).toHaveValue(
    values.lease_end_date,
  );
});

test("todo focuses a saved repair, manual followup updates it and contextual chat only prefills", async ({
  page,
  request,
}) => {
  const { c, root, record } = await isolatedCase(request);
  const created = await (
    await request.post(`${root}/repairs`, {
      data: {
        request_id: `test-${crypto.randomUUID()}`,
        expected_version: record.version,
        confirmed: true,
        values: {
          title: "厨房滴水",
          description: "水龙头关闭后仍滴水",
          location: "Kitchen",
          priority: "normal",
        },
      },
    })
  ).json();
  const repair = created.repairs[0];
  await page.goto(`/cases/${c.case_id}/aftercare?tab=utilities`);
  const todos = page.getByRole("region", { name: "To-do items", exact: true });
  await todos
    .getByRole("button", {
      name: `Handle repair: ${repair.title}`,
      exact: true,
    })
    .click();
  await expect(page).toHaveURL(
    new RegExp(`tab=repairs&repair=${repair.repair_id}`),
  );
  const card = page.locator(`[data-repair-id="${repair.repair_id}"]`);
  await expect(card).toBeFocused();
  await card
    .getByRole("button", { name: "Record follow-up", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "Record repair follow-up",
    exact: true,
  });
  await modal
    .getByRole("textbox", { name: "Reply or my notes", exact: true })
    .fill("中介说会安排师傅，时间尚未确定。");
  await modal
    .getByRole("button", { name: "Check and save follow-up", exact: true })
    .click();
  expect((await (await request.get(root)).json()).version).toBe(
    created.version,
  );
  await page
    .getByRole("button", { name: "Confirm repair follow-up", exact: true })
    .click();
  await expect(
    card.getByText("中介说会安排师傅，时间尚未确定。", { exact: true }),
  ).toBeVisible();
  const saved = await (await request.get(root)).json();
  expect(saved.repairs).toHaveLength(1);
  expect(saved.repairs[0].updates.at(-1).note).toBe(
    "中介说会安排师傅，时间尚未确定。",
  );
  const originalEmail = saved.repairs[0].email;
  await card
    .getByRole("button", { name: "Adjust email tone", exact: true })
    .click();
  await modal.getByLabel("Email tone", { exact: true }).click();
  await page
    .locator(".ant-select-dropdown .ant-select-item-option-content")
    .getByText("More polite", { exact: true })
    .click();
  await modal
    .getByRole("button", { name: "Check and save follow-up", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm repair follow-up", exact: true })
    .click();
  await expect(modal).toHaveCount(0);
  const rewritten = await (await request.get(root)).json();
  expect(rewritten.repairs).toHaveLength(1);
  expect(rewritten.repairs[0].email_tone).toBe("polite");
  expect(rewritten.repairs[0].email.to).toBe(originalEmail.to);
  expect(rewritten.repairs[0].description).toBe(repair.description);
  expect(rewritten.repairs[0].email.body).not.toBe(originalEmail.body);
  await card
    .getByRole("button", { name: "Discuss this repair", exact: true })
    .click();
  await expect(page).toHaveURL(/\/assistant\?message=/);
  const input = page.getByRole("textbox", {
    name: "Message to Rental Assistant",
    exact: true,
  });
  await expect(input).toHaveValue(new RegExp(repair.repair_id));
  await expect(input).toHaveValue(new RegExp(repair.title));
  expect((await (await request.get(root)).json()).repairs).toHaveLength(1);
});

test("mobile todo list is bounded and links to a specific service record", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const { c, root, record } = await isolatedCase(request);
  const directory = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const provider = directory.providers.find((p: { categories: string[] }) =>
    p.categories.includes("removalist"),
  );
  const base = {
    title: "滴水",
    description: "水龙头滴水",
    location: "Kitchen",
    priority: "normal",
    status: "prepared",
    created_at: "2026-10-22T00:00:00Z",
    email: {
      to: "",
      subject: "报修",
      body: "水龙头滴水",
      delivery_status: "prepared_not_sent",
    },
  };
  const repairs = Array.from({ length: 6 }, (_, i) => ({
    ...base,
    repair_id: `repair-test-${i}`,
    title: `滴水${i}`,
  }));
  const booking = {
    booking_id: "booking-test",
    provider_id: provider.id,
    service_date: null,
    quote_amount: null,
    status: "considering",
    notes: "等待报价",
    created_at: "2026-10-22T00:00:00Z",
  };
  await page.route(`**${root}`, (route) =>
    route.fulfill({ json: { ...record, repairs, bookings: [booking] } }),
  );
  await page.goto(`/cases/${c.case_id}/aftercare`);
  const todos = page.getByRole("region", { name: "To-do items", exact: true });
  await expect(todos.locator("li")).toHaveCount(5);
  await todos
    .getByRole("button", { name: "View all to-do items", exact: true })
    .click();
  await todos
    .getByRole("button", {
      name: `Handle service: ${provider.name}`,
      exact: true,
    })
    .click();
  const card = page.locator('[data-booking-id="booking-test"]');
  await expect(card).toBeFocused();
  await expect(
    card.getByRole("button", { name: "Update service record", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("confirmed aftercare source imports through real endpoints without changing saved services", async ({
  page,
  request,
}) => {
  const { c, root, record } = await isolatedCase(request);
  const config = await (await request.get("/api/v1/demo-config")).json();
  const seeded = await request.post("/api/v1/aftercare/commands", {
    data: {
      case_id: c.case_id,
      request_id: `test-${crypto.randomUUID()}`,
      expected_version: 0,
      operation: "create",
      payload: {
        tenancy: {
          ...config.tenancy_template,
          address: "Actual test tenancy, Sydney NSW",
          confirmed: true,
          source_ref: "user-entered:continuity-test",
          source_version: 1,
          rooms: null,
          inventory: null,
          carpeted: false,
          outdoor: null,
          furnished: null,
          inventory_confirmed: false,
          baseline_evidence_refs: [],
        },
        evidence: [],
      },
    },
  });
  expect(seeded.ok()).toBe(true);
  const updated = await request.post(`${root}/profile`, {
    data: {
      request_id: `test-${crypto.randomUUID()}`,
      expected_version: record.version,
      confirmed: true,
      values: {
        ...record.profile,
        agent_email: "keep@example.com",
        notes: "retain these user notes",
      },
    },
  });
  expect(updated.ok()).toBe(true);
  const before = await (await request.get(root)).json();
  const preview = await (await request.get(`${root}/tenancy-source`)).json();
  expect(preview.source.kind).toBe("aftercare");
  expect(preview.values).toEqual({
    address: "Actual test tenancy, Sydney NSW",
    carpeted: false,
  });
  expect((await (await request.get(root)).json()).version).toBe(before.version);
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await page
    .getByRole("button", { name: "View lease source", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "Check lease source",
    exact: true,
  });
  await modal
    .getByRole("checkbox", {
      name: "I confirm these details correspond to my actual lease.",
      exact: true,
    })
    .check();
  await modal
    .getByRole("button", { name: "Import selected details", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm lease import", exact: true })
    .click();
  await expect(modal).toHaveCount(0);
  const saved = await (await request.get(root)).json();
  expect(saved.profile).toMatchObject({
    address: "Actual test tenancy, Sydney NSW",
    carpeted: false,
    agent_email: "keep@example.com",
    notes: "retain these user notes",
  });
  expect(saved.repairs).toEqual(before.repairs);
  expect(saved.bookings).toEqual(before.bookings);
  expect(saved.profile.utilities).toEqual(before.profile.utilities);
  expect(saved.tenancy_source.kind).toBe("aftercare");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("failed stale import preserves choices and a refreshed stale source cannot be confirmed", async ({
  page,
  request,
}) => {
  const { c, root, record } = await isolatedCase(request);
  let current = true;
  let imports = 0;
  await page.route(`**${root}/tenancy-source`, (route) =>
    route.fulfill({
      json: {
        expected_version: record.version,
        source: {
          kind: "lease_draft",
          id: "stale-source",
          version: 1,
          label: "租约草稿",
          token: "stale-token",
          current,
          warning: current ? "请核实实际租约" : "此草稿来源已过期",
        },
        values: { address: "Test changed home" },
        previous: record.profile,
        linked_source: null,
        changed: true,
      },
    }),
  );
  await page.route(`**${root}/tenancy-import`, async (route) => {
    imports++;
    await route.fulfill({
      status: 409,
      json: {
        error: {
          code: "version_conflict",
          message: "资料版本已变化，请重新预览。",
        },
      },
    });
  });
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await page
    .getByRole("button", { name: "View lease source", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "Check lease source",
    exact: true,
  });
  const field = modal.getByRole("checkbox", {
    name: "Import Home address",
    exact: true,
  });
  await modal
    .getByRole("checkbox", {
      name: "I confirm these details correspond to my actual lease.",
      exact: true,
    })
    .check();
  await modal
    .getByRole("button", { name: "Import selected details", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm lease import", exact: true })
    .click();
  await expect(
    modal.getByText("Information has changed", { exact: true }),
  ).toBeVisible();
  await expect(field).toBeChecked();
  expect(imports).toBe(1);
  expect((await (await request.get(root)).json()).version).toBe(record.version);
  current = false;
  await modal
    .getByRole("button", { name: "Preview again", exact: true })
    .click();
  await expect(
    modal.getByText(
      "The source is outdated. Check the current lease or property details first.",
      {
        exact: true,
      },
    ),
  ).toBeVisible();
  await expect(
    modal.getByRole("checkbox", {
      name: "I confirm these details correspond to my actual lease.",
      exact: true,
    }),
  ).toBeDisabled();
  await expect(
    modal.getByRole("button", { name: "Import selected details", exact: true }),
  ).toBeDisabled();
  expect(imports).toBe(1);
});

test("composite tenancy labels preserve the actual aftercare and supplementary draft versions", async ({
  page,
  request,
}) => {
  const { c, root, record } = await isolatedCase(request);
  const label = "已确认租后租约资料 v1 + 同地址租约草稿 v2";
  const source = {
    kind: "aftercare",
    id: "aftercare-label-test",
    version: 1,
    label,
    token: "label-token",
    current: true,
    warning: "请核对实际资料。",
  };
  await page.route(`**${root}`, (route) =>
    route.fulfill({ json: { ...record, tenancy_source: source } }),
  );
  await page.route(`**${root}/tenancy-source`, (route) =>
    route.fulfill({
      json: {
        expected_version: record.version,
        source,
        values: { address: "Example Address" },
        previous: { address: "" },
        linked_source: source,
        changed: true,
      },
    }),
  );
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await expect(page.locator(".living-source-bar")).toContainText(label);
  await page
    .getByRole("button", { name: "View lease source", exact: true })
    .click();
  await expect(page.locator(".living-source-label")).toHaveText(label);
});
