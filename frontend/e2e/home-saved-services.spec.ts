import { expect, test } from "@playwright/test";

test("saved utilities and chosen moving and cleaning companies are visible together in My home", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  const { providers } = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const gas = providers.find(
    (p: { name: string; categories: string[] }) =>
      p.name === "AGL" && p.categories.includes("gas"),
  );
  const internet = providers.find((p: { categories: string[] }) =>
    p.categories.includes("internet"),
  );
  const moving = providers.find((p: { categories: string[] }) =>
    p.categories.includes("removalist"),
  );
  const cleaning = providers.find((p: { categories: string[] }) =>
    p.categories.includes("cleaner"),
  );
  await page.goto(`/cases/${c.case_id}/aftercare?tab=utilities`);
  for (const [label, name] of [
    ["Gas provider", gas.name],
    ["Internet provider", internet.name],
  ]) {
    await page.getByRole("combobox", { name: label, exact: true }).click();
    await page
      .locator(".ant-select-dropdown .ant-select-item-option-content")
      .getByText(name, { exact: true })
      .click();
  }
  await page
    .getByRole("button", { name: "Save provider selection", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm selection", exact: true })
    .click();
  await page
    .getByRole("button", { name: "View in My home", exact: true })
    .click();
  const home = page.getByRole("dialog", { name: "My home", exact: true });
  const utilities = home.getByRole("region", {
    name: "Saved utility providers",
    exact: true,
  });
  await expect(utilities).toContainText(gas.name);
  await expect(utilities).toContainText(internet.name);
  await home
    .getByRole("button", { name: "Choose moving or cleaning", exact: true })
    .click();
  for (const provider of [moving, cleaning]) {
    await page.locator(`[data-provider-id="${provider.id}"]`).click();
    const details = page.getByRole("dialog", {
      name: `${provider.name} · Provider details`,
      exact: true,
    });
    await details
      .getByRole("button", { name: "Save to My home", exact: true })
      .click();
    const confirmation = page.getByRole("dialog", {
      name: "Save this service to My home?",
      exact: true,
    });
    await confirmation
      .getByRole("button", { name: "Confirm and save", exact: true })
      .click();
    await expect(details).toHaveCount(0);
  }
  await page
    .getByRole("button", { name: "View in My home", exact: true })
    .click();
  const services = home.getByRole("region", {
    name: "Saved moving and cleaning",
    exact: true,
  });
  await expect(services).toContainText(moving.name);
  await expect(services).toContainText(cleaning.name);
  await expect(services.getByText("Considering", { exact: true })).toHaveCount(
    2,
  );
  let record = await (await request.get(root)).json();
  expect(record.bookings).toHaveLength(2);
  expect(
    record.bookings.every(
      (b: {
        status: string;
        quote_amount: number | null;
        service_date: string | null;
      }) =>
        b.status === "considering" &&
        b.quote_amount === null &&
        b.service_date === null,
    ),
  ).toBeTruthy();
  await home.getByRole("button", { name: "Close", exact: true }).click();
  // Reopening a chosen company offers its saved record, not another quick-save.
  await page.locator(`[data-provider-id="${moving.id}"]`).click();
  await page
    .getByRole("dialog", {
      name: `${moving.name} · Provider details`,
      exact: true,
    })
    .getByRole("button", { name: "View in My home", exact: true })
    .click();
  await expect(services).toContainText(moving.name);
  await home
    .getByRole("button", { name: `View ${moving.name} record`, exact: true })
    .click();
  const card = page.locator(
    `[data-booking-id="${record.bookings[0].booking_id}"]`,
  );
  await expect(card).toBeFocused();
  await page.reload();
  await page.getByRole("button", { name: "My home", exact: true }).click();
  await expect(utilities).toContainText(gas.name);
  await expect(services).toContainText(cleaning.name);
  record = await (await request.get(root)).json();
  expect(record.bookings).toHaveLength(2);
});

test("My home retains completed service details and stays usable on mobile", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  const { providers } = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const cleaner = providers.find((p: { categories: string[] }) =>
    p.categories.includes("cleaner"),
  );
  const response = await request.post(root + "/bookings", {
    data: {
      request_id: "seed-completed",
      expected_version: 0,
      confirmed: true,
      values: {
        provider_id: cleaner.id,
        service_date: "2026-11-10",
        quote_amount: 275,
        status: "completed",
        notes: "Fictional receipt retained",
      },
    },
  });
  expect(response.ok()).toBeTruthy();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/cases/${c.case_id}/aftercare?tab=issues`);
  await page.getByRole("button", { name: "My home", exact: true }).click();
  const home = page.getByRole("dialog", { name: "My home", exact: true });
  const services = home.getByRole("region", {
    name: "Saved moving and cleaning",
    exact: true,
  });
  await expect(services).toContainText(cleaner.name);
  await expect(services).toContainText("Completed");
  await expect(services).toContainText("275");
  await expect(services).toContainText("10 Nov 2026");
  await expect(services).toContainText("Fictional receipt retained");
  expect(
    await home.evaluate((node) => node.scrollWidth <= node.clientWidth),
  ).toBeTruthy();
  await page.screenshot({
    path: "/tmp/my-home-saved-services-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
});

test("a lost quick-save response can be confirmed again without duplicating a service", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}/living-services`;
  const { providers } = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const mover = providers.find((p: { categories: string[] }) =>
    p.categories.includes("removalist"),
  );
  const calls: string[] = [];
  await page.route(`**${root}/bookings`, async (route) => {
    calls.push(route.request().postData()!);
    if (calls.length === 1) {
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await page.goto(`/cases/${c.case_id}/aftercare?tab=services`);
  await page.locator(`[data-provider-id="${mover.id}"]`).click();
  const details = page.getByRole("dialog", {
    name: `${mover.name} · Provider details`,
    exact: true,
  });
  await details
    .getByRole("button", { name: "Save to My home", exact: true })
    .click();
  const confirm = page.getByRole("dialog", {
    name: "Save this service to My home?",
    exact: true,
  });
  await confirm
    .getByRole("button", { name: "Confirm and save", exact: true })
    .click();
  await expect.poll(() => calls.length).toBe(1);
  await expect(
    confirm.getByRole("button", { name: "Confirm and save", exact: true }),
  ).toBeEnabled();
  await confirm
    .getByRole("button", { name: "Confirm and save", exact: true })
    .click();
  await expect(confirm).toHaveCount(0);
  expect(calls).toHaveLength(2);
  expect(calls[1]).toBe(calls[0]);
  const record = await (await request.get(root)).json();
  expect(record.bookings).toHaveLength(1);
  await page
    .getByRole("button", { name: "View in My home", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog", { name: "My home", exact: true })
      .getByRole("region", { name: "Saved moving and cleaning", exact: true }),
  ).toContainText(mover.name);
});

test("an unconfirmed company choice closes when navigating to another case", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const other = await (
    await request.post("/api/v1/cases", { data: {} })
  ).json();
  const { providers } = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const mover = providers.find((p: { categories: string[] }) =>
    p.categories.includes("removalist"),
  );
  await page.goto(`/cases/${c.case_id}/aftercare?tab=services`);
  await page.locator(`[data-provider-id="${mover.id}"]`).click();
  await page
    .getByRole("button", { name: "Save to My home", exact: true })
    .click();
  const confirm = page.getByRole("dialog", {
    name: "Save this service to My home?",
    exact: true,
  });
  await expect(confirm).toBeVisible();
  await page.evaluate((url) => {
    window.history.pushState(null, "", url);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, `/cases/${other.case_id}/aftercare?tab=repairs`);
  await expect(confirm).toHaveCount(0);
  for (const id of [c.case_id, other.case_id])
    expect(
      (await (await request.get(`/api/v1/cases/${id}/living-services`)).json())
        .bookings,
    ).toHaveLength(0);
});
