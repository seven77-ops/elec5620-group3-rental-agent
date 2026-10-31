import { test, expect, type APIRequestContext } from "@playwright/test";
import { writeFile } from "node:fs/promises";

async function seed(request: APIRequestContext) {
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
  await request.post(root + "/selections", {
    data: {
      request_id: "choose",
      run_id: run.run_id,
      listing_id: run.report.pending_confirmation[0].listing_id,
      confirmed: true,
    },
  });
  return { c, root };
}

test("notice street fields preserve independent manual metadata and never search rental listings", async ({
  page,
  request,
}) => {
  const { c } = await seed(request);
  const listingQueries: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/v1/lease-addresses?"))
      listingQueries.push(r.url());
  });
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  const property = await page
    .getByLabel("Property address", { exact: true })
    .inputValue();
  await page
    .getByText("Landlord agent (if applicable)", { exact: true })
    .click();
  for (const prefix of ["Landlord", "Tenant", "Landlord agent"]) {
    await page
      .getByLabel(`${prefix} suburb`, { exact: true })
      .fill("West Footscray");
    await page.getByLabel(`${prefix} State`, { exact: true }).fill("VIC");
    await page.getByLabel(`${prefix} postcode`, { exact: true }).fill("3012");
    await page
      .getByLabel(`${prefix} notice address`, { exact: true })
      .fill("Unit 2001, 10 Example Street");
    await expect(
      page.getByLabel(`${prefix} suburb`, { exact: true }),
    ).toHaveValue("West Footscray");
    await expect(
      page.getByLabel(`${prefix} State`, { exact: true }),
    ).toHaveValue("VIC");
    await expect(
      page.getByLabel(`${prefix} postcode`, { exact: true }),
    ).toHaveValue("3012");
  }
  await expect(
    page.getByLabel("Property address", { exact: true }),
  ).toHaveValue(property);
  expect(listingQueries).toHaveLength(0);
});

test("independent postal choices handle same-name suburbs and leading zeros, then save and fill the PDF", async ({
  page,
  request,
}) => {
  const { c, root } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await page
    .getByText("Landlord agent (if applicable)", { exact: true })
    .click();
  const parties = [
    {
      prefix: "Landlord",
      field: "landlord",
      street: "Unit 6903, 10 Example Street",
      suburb: "West Footscray",
      state: "VIC",
      postcode: "3012",
    },
    {
      prefix: "Tenant",
      field: "tenant",
      street: "Unit 2001, 20 Example Road",
      suburb: "Darwin",
      state: "NT",
      postcode: "0800",
    },
    {
      prefix: "Landlord agent",
      field: "agent",
      street: "30 Example Avenue",
      suburb: "Burwood",
      state: "NSW",
      postcode: "2134",
    },
  ];
  for (const p of parties) {
    await page
      .getByLabel(`${p.prefix} notice address`, { exact: true })
      .fill(p.street);
    await page.getByLabel(`${p.prefix} State`, { exact: true }).click();
    await page.getByRole("option", { name: p.state, exact: true }).click();
    await page.getByLabel(`${p.prefix} suburb`, { exact: true }).fill(p.suburb);
    const options = page.locator(`#${p.field}_notice_suburb_list`);
    await expect(options).not.toContainText(p.state === "NSW" ? "VIC" : "NSW");
    await options
      .getByRole("option", {
        name: `${p.suburb} · ${p.state} ${p.postcode}`,
        exact: true,
      })
      .click();
    await expect(
      page.getByLabel(`${p.prefix} notice address`, { exact: true }),
    ).toHaveValue(p.street);
    await expect(
      page.getByLabel(`${p.prefix} postcode`, { exact: true }),
    ).toHaveValue(p.postcode);
  }
  // Selecting another same-name locality is explicit; street text remains the user's.
  await page.getByLabel("Landlord agent State", { exact: true }).fill("VIC");
  await page
    .getByLabel("Landlord agent suburb", { exact: true })
    .fill("Burwood");
  await page
    .locator("#agent_notice_suburb_list")
    .getByRole("option", { name: "Burwood · VIC 3125", exact: true })
    .click();
  await expect(
    page.getByLabel("Landlord agent postcode", { exact: true }),
  ).toHaveValue("3125");
  await expect(
    page.getByLabel("Landlord agent notice address", { exact: true }),
  ).toHaveValue("30 Example Avenue");
  // Postal lookup also permits explicit selection and retains NT's leading zero.
  await page.getByLabel("Tenant postcode", { exact: true }).fill("080");
  await page
    .locator("#tenant_notice_postcode_list")
    .getByRole("option", { name: "Darwin · NT 0800", exact: true })
    .click();
  await expect(page.getByLabel("Tenant postcode", { exact: true })).toHaveValue(
    "0800",
  );
  await page.getByLabel("Lease scope", { exact: true }).click();
  await page
    .getByRole("option", {
      name: "Standard NSW whole-property residential tenancy",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Check and fill contract", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Confirm lease draft save",
    exact: true,
  });
  await dialog.getByRole("checkbox").check();
  await dialog
    .getByRole("button", {
      name: "Confirm and save unsigned draft",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Contract preview · v1", exact: true }),
  ).toBeVisible();
  const list = await (await request.get(root + "/lease-drafts")).json();
  const saved = await (
    await request.get(root + `/lease-drafts/${list.items[0].draft_id}`)
  ).json();
  expect(saved.fields.landlord_notice_suburb).toBe("West Footscray");
  expect(saved.fields.tenant_notice_postcode).toBe("0800");
  expect(saved.fields.agent_notice_state).toBe("VIC");
  const pdf = await request.get(
    root + `/lease-drafts/${list.items[0].draft_id}/pdf?version=1`,
  );
  expect(pdf.ok()).toBe(true);
  await writeFile("/tmp/notice-addresses-browser.pdf", await pdf.body());
  await page.reload();
  await expect(
    page.getByLabel("Landlord notice address", { exact: true }),
  ).toHaveValue(parties[0].street);
  await expect(page.getByLabel("Tenant postcode", { exact: true })).toHaveValue(
    "0800",
  );
});

test("mobile notice lookup ignores late State responses and permits unmatched manual details", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 900 });
  const { c, root } = await seed(request);
  const darwin = await (
    await request.get("/api/v1/lease-localities?q=Darwin&state=NT")
  ).json();
  let releaseOld!: () => void;
  const gate = new Promise<void>((resolve) => {
    releaseOld = resolve;
  });
  let oldStarted = false;
  await page.route("**/api/v1/lease-localities?*", async (route) => {
    const params = new URL(route.request().url()).searchParams;
    if (params.get("q") === "Darwin" && params.get("state") === "NSW") {
      oldStarted = true;
      await gate;
      await route.fulfill({ json: { items: [], source: "au_postcodes" } });
    } else if (params.get("q") === "Darwin" && params.get("state") === "NT") {
      await route.fulfill({ json: darwin });
    } else
      await route.fulfill({
        status: 503,
        json: { error: { message: "Reference unavailable" } },
      });
  });
  await page.goto(`/cases/${c.case_id}/contract?mode=draft`);
  await page.getByLabel("Tenant State", { exact: true }).fill("NSW");
  await page.getByLabel("Tenant suburb", { exact: true }).fill("Darwin");
  await expect.poll(() => oldStarted).toBe(true);
  await page.getByLabel("Tenant State", { exact: true }).fill("NT");
  await page.getByLabel("Tenant suburb", { exact: true }).click();
  const options = page.locator("#tenant_notice_suburb_list");
  await expect(options).toContainText("Darwin · NT 0800");
  const response = page.waitForResponse((r) =>
    r.url().includes("/lease-localities?q=Darwin&state=NSW"),
  );
  releaseOld();
  await response;
  await expect(options).toContainText("Darwin · NT 0800");
  await options
    .getByRole("option", { name: "Darwin · NT 0800", exact: true })
    .click();
  await page
    .getByLabel("Tenant suburb", { exact: true })
    .fill("Unlisted Test Locality");
  const failed = page.waitForResponse((r) =>
    r.url().includes("/lease-localities?q=Unlisted"),
  );
  await failed;
  await page.getByLabel("Tenant postcode", { exact: true }).fill("0999");
  await page
    .getByLabel("Tenant notice address", { exact: true })
    .fill("Unit 2001, 40 Example Road");
  await expect(page.getByLabel("Tenant suburb", { exact: true })).toHaveValue(
    "Unlisted Test Locality",
  );
  await expect(page.getByLabel("Tenant postcode", { exact: true })).toHaveValue(
    "0999",
  );
  await page.getByLabel("Lease scope", { exact: true }).click();
  await page
    .getByRole("option", {
      name: "Standard NSW whole-property residential tenancy",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Check and fill contract", exact: true })
    .click();
  const confirm = page.getByRole("dialog", {
    name: "Confirm lease draft save",
    exact: true,
  });
  await confirm.getByRole("checkbox").check();
  await confirm
    .getByRole("button", {
      name: "Confirm and save unsigned draft",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Contract preview · v1", exact: true }),
  ).toBeVisible();
  const list = await (await request.get(root + "/lease-drafts")).json();
  const saved = await (
    await request.get(root + `/lease-drafts/${list.items[0].draft_id}`)
  ).json();
  expect(saved.fields.tenant_notice_suburb).toBe("Unlisted Test Locality");
  expect(saved.fields.tenant_notice_postcode).toBe("0999");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
