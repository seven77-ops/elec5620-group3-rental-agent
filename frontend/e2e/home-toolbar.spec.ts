import { test, expect, type APIRequestContext } from "@playwright/test";
async function fresh(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  return { c, root: `/api/v1/cases/${c.case_id}` };
}
async function selected(request: APIRequestContext) {
  const { c, root } = await fresh(request);
  const confirmation = await request.post(root + "/profile-confirmations", {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  expect(confirmation.ok()).toBeTruthy();
  const result = await (
    await request.post(root + "/evaluations", {
      data: { request_id: "run", confirmation_version: 1 },
    })
  ).json();
  const listing = result.report.pending_confirmation[0];
  const response = await request.post(root + "/selections", {
    data: {
      request_id: "select",
      run_id: result.run_id,
      listing_id: listing.listing_id,
      confirmed: true,
    },
  });
  expect(response.ok()).toBeTruthy();
  return { c, root, listing };
}

test("My home displays selected address without saving and basic edits preserve hidden information", async ({
  page,
  request,
}) => {
  const { c, root } = await selected(request);
  const living = await (await request.get(root + "/living-services")).json();
  living.profile.notes = "Fictional note to keep";
  living.profile.own_furniture = "Fictional desk";
  living.profile.lease_start_date = "2026-11-01";
  living.profile.lease_end_date = "2027-11-01";
  const seeded = await request.post(root + "/living-services/profile", {
    data: {
      request_id: "seed-profile",
      expected_version: 0,
      confirmed: true,
      values: living.profile,
    },
  });
  expect(seeded.ok()).toBeTruthy();
  const source = await (
    await request.get(root + "/living-services/home")
  ).json();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=repairs`);
  for (const title of [
    "To-do items",
    "Lease and living details",
    "Home and contacts",
  ]) {
    await expect(page.getByText(title, { exact: true })).toHaveCount(0);
  }
  await page.getByRole("button", { name: "My home", exact: true }).click();
  const home = page.getByRole("dialog", { name: "My home", exact: true });
  await expect(home).toContainText(source.values.address);
  await expect(home).toContainText(source.values.postcode);
  await expect(home).toContainText("Selected property");
  expect(
    (await (await request.get(root + "/living-services")).json()).profile
      .address,
  ).toBe("");
  await home.getByRole("button", { name: "Edit details", exact: true }).click();
  await home
    .getByLabel("Agent / landlord", { exact: true })
    .fill("Fictional Agent");
  await home.getByLabel("Email", { exact: true }).fill("agent@example.com");
  await home.getByLabel("Phone", { exact: true }).fill("0491 570 000");
  await expect(
    home.getByLabel("Lease start date", { exact: true }),
  ).toHaveCount(0);
  await home.getByRole("button", { name: "Save details", exact: true }).click();
  await expect(home).toContainText("agent@example.com");
  await expect(
    home.getByRole("button", { name: "Edit details", exact: true }),
  ).toBeVisible();
  const saved = await (await request.get(root + "/living-services")).json();
  expect(saved.profile.address).toBe(source.values.address);
  expect(saved.profile.notes).toBe("Fictional note to keep");
  expect(saved.profile.own_furniture).toBe("Fictional desk");
  expect(saved.profile.lease_start_date).toBe("2026-11-01");
  expect(saved.profile.lease_end_date).toBe("2027-11-01");
  await page.screenshot({
    path: "/tmp/aftercare-my-home.png",
    fullPage: true,
    animations: "disabled",
  });
  await home.getByRole("button", { name: "Close", exact: true }).click();
  await page.reload();
  await page.getByRole("button", { name: "My home", exact: true }).click();
  await expect(home).toContainText("Fictional Agent");
});

test("In progress collects actual pending records and opens the corresponding repair or booking", async ({
  page,
  request,
}) => {
  const { c, root } = await fresh(request);
  let version = 0;
  const write = async (path: string, values: unknown) => {
    const response = await request.post(root + "/living-services" + path, {
      data: {
        request_id: crypto.randomUUID(),
        expected_version: version,
        confirmed: true,
        values,
      },
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    const record = await response.json();
    version = record.version;
    return record;
  };
  let record = await write("/repairs", {
    title: "Fictional ongoing repair",
    description: "Fictional tap issue",
    location: "Kitchen",
    priority: "normal",
  });
  const repair = record.repairs[0];
  const directory = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const provider = directory.providers.find((p: { categories: string[] }) =>
    p.categories.includes("removalist"),
  );
  record = await write("/bookings", {
    provider_id: provider.id,
    service_date: "2020-01-01",
    quote_amount: null,
    status: "booked",
    notes: "Fictional old booking not yet completed",
  });
  const booking = record.bookings[0];
  await write("/bookings", {
    provider_id: provider.id,
    service_date: "2020-01-01",
    quote_amount: null,
    status: "completed",
    notes: "Fictional completed record",
  });
  await page.goto(`/cases/${c.case_id}/aftercare?tab=utilities`);
  await page
    .getByRole("button", { name: "In progress (2)", exact: true })
    .click();
  const progress = page.getByRole("dialog", {
    name: "In progress",
    exact: true,
  });
  await expect(progress).toContainText("Fictional ongoing repair");
  await expect(progress).toContainText(provider.name);
  await expect(progress).not.toContainText("Add agent");
  await progress
    .getByRole("button", { name: "Open Fictional ongoing repair", exact: true })
    .click();
  await expect(progress).toBeHidden();
  await expect(page).toHaveURL(
    new RegExp(`tab=repairs&repair=${repair.repair_id}`),
  );
  await expect(
    page.locator(`[data-repair-id="${repair.repair_id}"]`),
  ).toHaveClass(/is-targeted/);
  await page
    .getByRole("button", { name: "In progress (2)", exact: true })
    .click();
  await progress
    .getByRole("button", { name: `Open ${provider.name}`, exact: true })
    .click();
  await expect(page).toHaveURL(
    new RegExp(`tab=services&booking=${booking.booking_id}`),
  );
  await expect(
    page.locator(`[data-booking-id="${booking.booking_id}"]`),
  ).toHaveClass(/is-targeted/);
  await page.screenshot({
    path: "/tmp/aftercare-toolbar.png",
    fullPage: true,
    animations: "disabled",
  });
});

test("home toolbar remains compact on mobile and Issue report keeps its simple form", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { c, root } = await fresh(request);
  await page.goto(`/cases/${c.case_id}/aftercare?tab=issues`);
  await expect(
    page.getByRole("region", { name: "Report issue", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "My home", exact: true }).click();
  const home = page.getByRole("dialog", { name: "My home", exact: true });
  await expect(home).toContainText("Not provided");
  expect(Math.round((await home.boundingBox())!.width)).toBeLessThanOrEqual(
    390,
  );
  await home.getByRole("button", { name: "Edit details", exact: true }).click();
  await home
    .getByLabel("Address", { exact: true })
    .fill("Unsaved fictional address");
  await home
    .getByRole("button", { name: "Cancel editing", exact: true })
    .click();
  expect(
    (await (await request.get(root + "/living-services")).json()).profile
      .address,
  ).toBe("");
  await home.getByRole("button", { name: "Close", exact: true }).click();
  await page
    .getByRole("button", { name: "In progress (0)", exact: true })
    .click();
  const progress = page.getByRole("dialog", {
    name: "In progress",
    exact: true,
  });
  await expect(progress).toContainText("No items in progress");
  expect(Math.round((await progress.boundingBox())!.width)).toBeLessThanOrEqual(
    390,
  );
  await progress.getByRole("button", { name: "Close", exact: true }).click();
  await page.screenshot({
    path: "/tmp/aftercare-toolbar-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("reloading a home conflict keeps edited fields and refreshes untouched fields", async ({
  page,
  request,
}) => {
  const { c, root } = await fresh(request);
  const initial = await (await request.get(root + "/living-services")).json();
  initial.profile.address = "Initial fictional home";
  initial.profile.agent_email = "initial@example.com";
  initial.profile.agent_phone = "0491 570 000";
  const seeded = await request.post(root + "/living-services/profile", {
    data: {
      request_id: "initial",
      expected_version: 0,
      confirmed: true,
      values: initial.profile,
    },
  });
  expect(seeded.ok()).toBeTruthy();
  await page.goto(`/cases/${c.case_id}/aftercare?tab=repairs`);
  await page.getByRole("button", { name: "My home", exact: true }).click();
  const home = page.getByRole("dialog", { name: "My home", exact: true });
  await home.getByRole("button", { name: "Edit details", exact: true }).click();
  await home.getByLabel("Phone", { exact: true }).fill("0491 570 001");
  const latest = await (await request.get(root + "/living-services")).json();
  latest.profile.agent_email = "newer@example.com";
  latest.profile.address = "Updated fictional home";
  latest.profile.notes = "Newer hidden note";
  const updated = await request.post(root + "/living-services/profile", {
    data: {
      request_id: "other-update",
      expected_version: latest.version,
      confirmed: true,
      values: latest.profile,
    },
  });
  expect(updated.ok()).toBeTruthy();
  await home.getByRole("button", { name: "Save details", exact: true }).click();
  await expect(home.getByRole("alert")).toBeVisible();
  await home
    .getByRole("button", { name: "Load latest details", exact: true })
    .click();
  await expect(home.getByLabel("Email", { exact: true })).toHaveValue(
    "newer@example.com",
  );
  await expect(home.getByLabel("Address", { exact: true })).toHaveValue(
    "Updated fictional home",
  );
  await expect(home.getByLabel("Phone", { exact: true })).toHaveValue(
    "0491 570 001",
  );
  await home.getByRole("button", { name: "Save details", exact: true }).click();
  await expect(
    home.getByRole("button", { name: "Edit details", exact: true }),
  ).toBeVisible();
  const saved = await (await request.get(root + "/living-services")).json();
  expect(saved.profile.notes).toBe("Newer hidden note");
  expect(saved.profile.agent_email).toBe("newer@example.com");
  expect(saved.profile.agent_phone).toBe("0491 570 001");
});
