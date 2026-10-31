import { expect, test } from "@playwright/test";

test("living profile and utility choices require confirmation and restore after reload", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const directory = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const energy = directory.providers.find((p: { categories: string[] }) =>
    p.categories.includes("electricity"),
  );
  expect(energy).toBeTruthy();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=utilities`);
  await expect(
    page.getByRole("heading", {
      name: "Living and aftercare services",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Edit home and contacts", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("textbox", { name: "Home address", exact: true }),
  ).toBeEmpty();
  await dialog
    .getByRole("textbox", { name: "Home address", exact: true })
    .fill("Test unit, Sydney NSW");
  await dialog
    .getByRole("textbox", { name: "Agent or landlord name", exact: true })
    .fill("Test contact");
  await dialog
    .getByRole("textbox", { name: "Contact email", exact: true })
    .fill("agent@example.com");
  await expect(
    dialog.getByRole("button", {
      name: "Confirm and save details",
      exact: true,
    }),
  ).toBeDisabled();
  await dialog
    .getByRole("checkbox", {
      name: "I confirm saving these home and contact details.",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("button", { name: "Confirm and save details", exact: true })
    .click();
  await expect(
    page.getByText("agent@example.com", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Electricity provider", exact: true })
    .click();
  await page
    .locator(".ant-select-dropdown .ant-select-item-option-content")
    .getByText(energy.name, { exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save provider selection", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(energy.name);
  const before = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(before.profile.utilities.electricity).toBeNull();
  await page
    .getByRole("button", { name: "Confirm selection", exact: true })
    .click();
  await page.reload();
  await expect(
    page.getByText(energy.name, { exact: true }).first(),
  ).toBeVisible();
  const saved = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(saved.profile.utilities.electricity).toBe(energy.id);
  expect(saved.profile.agent_email).toBe("agent@example.com");
  await page.screenshot({
    path: "/tmp/living-services-utilities-desktop.png",
    fullPage: true,
  });
});

test("repairs preserve an unsent email draft and status without sending", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=repairs`);
  await expect(
    page.getByText(
      "No email address entered. You can save a repair draft or call the recorded number. Add an email to open it in your email app.",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Repair title", exact: true })
    .fill("厨房水龙头漏水");
  await page
    .getByRole("textbox", { name: "Issue description", exact: true })
    .fill("今天发现关闭后仍持续滴水，尚未联系维修人员。");
  await page
    .getByRole("textbox", { name: "Location", exact: true })
    .fill("Kitchen");
  await page
    .getByRole("button", { name: "Prepare repair email", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Save email draft only");
  await page
    .getByRole("button", { name: "Confirm repair draft", exact: true })
    .click();
  await expect(
    page.getByText("Draft prepared · Not sent", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open in email app", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Edit home and contacts", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("textbox", { name: "Contact email", exact: true })
    .fill("agent@example.com");
  await dialog
    .getByRole("textbox", { name: "Contact phone", exact: true })
    .fill("0400000000");
  await dialog
    .getByRole("checkbox", {
      name: "I confirm saving these home and contact details.",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("button", { name: "Confirm and save details", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "Call contact", exact: true }),
  ).toHaveAttribute("href", "tel:0400000000");
  await expect(
    page.getByRole("link", { name: "Open in email app", exact: true }),
  ).toHaveAttribute("href", /^mailto:agent%40example\.com\?subject=/);
  const saved = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(saved.repairs).toHaveLength(1);
  expect(saved.repairs[0].email.delivery_status).toBe("prepared_not_sent");
  expect(saved.repairs[0].email.to).toBe("");
  await page.reload();
  await expect(
    page.getByText("厨房水龙头漏水", { exact: true }).first(),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("provider cards use directory sources and save quote records on mobile", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const directory = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const provider = directory.providers.find(
    (p: { categories: string[] }) =>
      p.categories.includes("removalist") || p.categories.includes("cleaner"),
  );
  expect(provider).toBeTruthy();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=services`);
  const card = page.locator(`[data-provider-id="${provider.id}"]`);
  await card.click();
  const details = page.getByRole("dialog", {
    name: `${provider.name} · Provider details`,
    exact: true,
  });
  await expect(
    details.getByRole("link", { name: "Company website", exact: true }),
  ).toHaveAttribute("href", provider.website);
  await expect(details.getByRole("link")).toHaveCount(1);
  await expect(details).not.toContainText("Route");
  await details
    .getByRole("button", { name: "Record quote or booking", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("spinbutton", { name: "Quote received (AUD)", exact: true })
    .fill("250");
  await dialog
    .getByRole("textbox", { name: "Service date", exact: true })
    .fill("2026-12-15");
  await dialog
    .getByRole("textbox", { name: "Service notes", exact: true })
    .fill("仅记录电话报价，尚未确认预约。");
  await dialog
    .getByRole("checkbox", {
      name: "I confirm this only saves a record and does not submit a booking to the provider.",
      exact: true,
    })
    .check();
  await dialog
    .getByRole("button", { name: "Confirm service record", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("AUD 250", { exact: true })).toBeVisible();
  const saved = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(saved.bookings[0].provider_id).toBe(provider.id);
  expect(saved.bookings[0].quote_amount).toBe(250);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/tmp/living-services-mobile.png",
    fullPage: true,
  });
  await page
    .getByRole("tab", { name: "Move-out and bond", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Lease address", exact: true }),
  ).toBeEmpty();
  await expect(page.getByText("synthetic://", { exact: false })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Add room", exact: true }),
  ).toBeVisible();
});

test("real tenancy confirmation sends no sample rooms, inventory or evidence", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const payloads: Record<string, unknown>[] = [];
  await page.route("**/api/v1/aftercare/commands", async (route) => {
    payloads.push(route.request().postDataJSON());
    await route.continue();
  });
  await page.goto(`/cases/${c.case_id}/aftercare?tab=moveout`);
  const address = page.getByRole("textbox", {
    name: "Lease address",
    exact: true,
  });
  await expect(address).toBeEmpty();
  await expect(
    page.getByRole("textbox", { name: "Room name", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("textbox", { name: "Furniture name", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("textbox", {
      name: "Information source reference",
      exact: true,
    }),
  ).toHaveCount(0);
  await address.fill("User-confirmed test tenancy, Sydney NSW");
  await page
    .getByRole("checkbox", {
      name: "I have checked and confirmed the lease, rooms, furniture, and sources above.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", {
      name: "Confirm details and create aftercare case",
      exact: true,
    })
    .click();
  await expect(
    page.getByText("Confirmed lease details", { exact: true }),
  ).toBeVisible();
  expect(payloads).toHaveLength(1);
  expect(payloads[0]).toMatchObject({
    operation: "create",
    payload: {
      tenancy: {
        address: "User-confirmed test tenancy, Sydney NSW",
        source_ref: "user-entered:tenant-confirmation",
        confirmed: true,
        rooms: null,
        inventory: null,
        carpeted: null,
        outdoor: null,
        furnished: null,
        inventory_confirmed: false,
        baseline_evidence_refs: [],
      },
      evidence: [],
    },
  });
  expect(JSON.stringify(payloads[0])).not.toContain("synthetic://");
  await page.getByRole("tab", { name: "Bond follow-up", exact: true }).click();
  await expect(
    page.getByLabel("Bond reference (optional for now)", { exact: true }),
  ).toBeEmpty();
});

test("utility edits retain their base version across refresh and cannot erase a concurrent gas choice", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const directory = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const provider = directory.providers.find(
    (p: { categories: string[] }) =>
      p.categories.includes("electricity") && p.categories.includes("gas"),
  );
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  await page.goto(`/cases/${c.case_id}/aftercare?tab=utilities`);
  const chooseElectricity = async () => {
    await page
      .getByRole("combobox", { name: "Electricity provider", exact: true })
      .click();
    await page
      .locator(".ant-select-dropdown .ant-select-item-option-content")
      .getByText(provider.name, { exact: true })
      .click();
  };
  await chooseElectricity();
  const initial = await (await request.get(root)).json();
  const changed = await request.post(`${root}/profile`, {
    data: {
      request_id: `test-${crypto.randomUUID()}`,
      expected_version: initial.version,
      confirmed: true,
      values: {
        ...initial.profile,
        utilities: { ...initial.profile.utilities, gas: provider.id },
      },
    },
  });
  expect(changed.ok()).toBe(true);
  await page
    .getByRole("button", { name: "Load latest information", exact: true })
    .click();
  await expect(
    page.getByText(
      "A newer version is available. Your unsaved selection is preserved. Restore the latest selection before editing and saving.",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Save provider selection", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm selection", exact: true })
    .click();
  await expect(
    page.getByText(
      "Load the latest information, check your input, and save again.",
      { exact: true },
    ),
  ).toBeVisible();
  const protectedRecord = await (await request.get(root)).json();
  expect(protectedRecord.profile.utilities).toMatchObject({
    electricity: null,
    gas: provider.id,
  });
  await page
    .getByRole("button", { name: "Restore latest selection", exact: true })
    .click();
  await chooseElectricity();
  await page
    .getByRole("button", { name: "Save provider selection", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm selection", exact: true })
    .click();
  await expect(
    page.getByText(
      "Load the latest information, check your input, and save again.",
      { exact: true },
    ),
  ).toHaveCount(0);
  const saved = await (await request.get(root)).json();
  expect(saved.profile.utilities).toMatchObject({
    electricity: provider.id,
    gas: provider.id,
  });
});

test("living services hide standalone attachments and preserve saved file downloads", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  await page.goto(`/cases/${c.case_id}/aftercare?tab=repairs`);
  const png = Buffer.from(
    await page.evaluate(() => {
      const canvas = document.createElement("canvas");
      canvas.width = 1;
      canvas.height = 1;
      const context = canvas.getContext("2d")!;
      context.fillStyle = "#174EA6";
      context.fillRect(0, 0, 1, 1);
      return canvas.toDataURL("image/png").split(",")[1];
    }),
    "base64",
  );
  const upload = await request.post(`${root}/attachments?purpose=repair`, {
    headers: {
      "Content-Type": "image/png",
      "X-Request-Id": `test-${crypto.randomUUID()}`,
      "X-Filename": "repair-photo.png",
    },
    data: png,
  });
  expect(upload.ok()).toBe(true);
  const attachment = await upload.json();
  expect(attachment.verification_status).toBe("user_uploaded_unverified");
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "Living and aftercare services",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", {
      name: "Photo and receipt attachments",
      exact: true,
    }),
  ).toHaveCount(0);
  const saved = await (await request.get(`${root}/attachments`)).json();
  expect(saved.items).toHaveLength(1);
  expect(saved.items[0].attachment_id).toBe(attachment.attachment_id);
  const download = await request.get(attachment.download_url);
  expect(download.ok()).toBe(true);
  expect(download.headers()["content-type"]).toContain("image/png");
  expect(await download.body()).toEqual(png);
  const record = await (await request.get(root)).json();
  expect(record.version).toBe(0);
});
