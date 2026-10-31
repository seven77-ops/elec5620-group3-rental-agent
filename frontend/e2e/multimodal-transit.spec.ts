import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";
async function seed(
  page: Page,
  request: APIRequestContext,
  estimate = false,
  constrained = false,
) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const conversation = await (
    await request.post(`/api/v1/cases/${c.case_id}/assistant/conversations`, {
      data: {},
    })
  ).json();
  const home = (
    await (await request.get("/api/v1/listings?page_size=1")).json()
  ).items[0];
  const stamp = new Date().toISOString();
  const base = {
    status: "planned",
    source_url: "https://opendata.transport.nsw.gov.au/",
    queried_at: stamp,
  };
  const mixed = {
    ...base,
    duration_minutes: 50,
    transit_modes: ["train", "bus"],
    transfers: 1,
    services: ["T2", "412"],
    legs: [
      { mode: "walk", duration_minutes: 5 },
      {
        mode: "train",
        service: "T2",
        from: "Burwood",
        to: "Central",
        duration_minutes: 25,
      },
      {
        mode: "bus",
        service: "412",
        from: "Central",
        to: "Campus",
        duration_minutes: 10,
      },
      { mode: "walk", duration_minutes: 5 },
    ],
  };
  const train = {
    ...base,
    duration_minutes: 45,
    transit_modes: ["train"],
    transfers: constrained ? 2 : 0,
    legs: [
      { mode: "train", duration_minutes: 35, service: "T9" },
      { mode: "walk", duration_minutes: 10 },
    ],
  };
  const bus = {
    ...base,
    duration_minutes: 58,
    transit_modes: ["bus"],
    transfers: 0,
    legs: [{ mode: "bus", duration_minutes: 58, service: "440" }],
  };
  home.usyd_commute = {
    ...home.usyd_commute,
    modes: estimate
      ? {}
      : {
          public_transport: mixed,
          train: mixed,
          bus: mixed,
          drive: { ...base, status: "routing_estimate", duration_minutes: 27 },
        },
    transit_options: estimate ? [] : [mixed, train, bus],
    ...(constrained
      ? { selected_transit_route: { ...bus, mode: "public_transport" } }
      : {}),
    estimates: estimate
      ? {
          public_transport: {
            lower_minutes: 40,
            upper_minutes: 65,
            queried_at: stamp,
          },
        }
      : {},
  };
  await page.route(
    `**/assistant/conversations/${conversation.conversation_id}`,
    (route) =>
      route.fulfill({
        json: {
          ...conversation,
          messages: [
            {
              message_id: "mixed-reference",
              role: "assistant",
              agent: "agent2",
              content: "Matching properties",
              created_at: stamp,
              listings: [home],
              actions: [],
            },
          ],
        },
      }),
  );
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByRole("button", { name: "Listing details", exact: true })
    .click();
  return page.getByTestId("usyd-commute");
}
for (const width of [360, 1440]) {
  test(`commute details show compact modes without a route-details section at ${width}px`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const details = await seed(page, request);
    await expect(details.locator(".usyd-transit")).toHaveCount(0);
    await expect(details.locator(".usyd-itinerary")).toHaveCount(0);
    await expect(
      details.getByText("Public transport route details", { exact: true }),
    ).toHaveCount(0);
    await expect(
      details.locator('[data-mode="public_transport"]'),
    ).toContainText("~45 min");
    await expect(details.locator('[data-mode="drive"]')).toContainText(
      "~27 min",
    );
    await expect(details.locator(".usyd-mode-grid > div")).toHaveCount(2);
    await expect(
      details.getByRole("link", {
        name: "Check public transport directions in Google Maps",
      }),
    ).toHaveAttribute("href", /travelmode=transit/);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await details.scrollIntoViewIfNeeded();
    await expect(details.locator(".usyd-commute-weighting")).toHaveCount(0);
    const notes = details.locator(".usyd-route-notes");
    await expect(notes).not.toHaveAttribute("open", "");
    await notes.locator("summary").click();
    await expect(notes.locator("p")).toContainText("Times are approximate");
    await notes.locator("summary").click();
    await expect(
      details.getByRole("link", { name: "TfNSW", exact: true }),
    ).toBeVisible();
    expect(errors).toEqual([]);
    await details.screenshot({
      path: `/tmp/rental-commute-clean-${width}.png`,
    });
    await page.screenshot({
      path: `/tmp/rental-multimodal-${width}.png`,
      fullPage: true,
    });
  });
}
test("coarse public transport estimates show a range without invented routes or transfers", async ({
  page,
  request,
}) => {
  const details = await seed(page, request, true);
  await expect(details).toContainText("Est. 40–65 min");
  await expect(details.locator(".usyd-itinerary")).toHaveCount(0);
  await expect(details.getByText("Route details", { exact: true })).toHaveCount(
    0,
  );
  await expect(details).not.toContainText("No transfers");
  await expect(details).toContainText("services and transfers unverified");
});
test("rental needs offer four umbrella travel choices", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByRole("button", { name: "My rental needs", exact: true })
    .click();
  const mode = page
    .getByRole("dialog", { name: "My rental needs", exact: true })
    .getByLabel("Commute mode", { exact: true });
  await mode.click();
  const dropdown = page.locator(".ant-select-dropdown:visible");
  await expect(dropdown.locator(".ant-select-item-option")).toHaveCount(4);
  await expect(dropdown).toContainText("Public transport (any combination)");
  await expect(dropdown).not.toContainText("Includes train");
});

test("details retain the qualifying no-transfer route instead of a faster invalid alternative", async ({
  page,
  request,
}) => {
  const details = await seed(page, request, false, true);
  await expect(details.locator(".usyd-commute-title")).toContainText(
    "Commute to USYD",
  );
  await expect(details.locator('[data-mode="public_transport"]')).toContainText(
    "~58 min",
  );
  await expect(
    details.locator('[data-mode="public_transport"]'),
  ).not.toContainText("~45 min");
});

test("public transport shares the compact travel grid instead of a full-width itinerary", async ({
  page,
  request,
}) => {
  const details = await seed(page, request);
  const grid = details.locator(".usyd-mode-grid");
  const transit = grid
    .locator(":scope > div")
    .filter({ has: page.getByText("Public transport", { exact: true }) });
  const drive = grid
    .locator(":scope > div")
    .filter({ has: page.getByText("Driving", { exact: true }) });
  await expect(transit).toBeVisible();
  await expect(drive).toBeVisible();
  await expect(transit).toContainText("~45 min");
  const [a, b] = await grid.evaluate((element) =>
    [...element.children].slice(0, 2).map((child) => {
      const { x, y, width, height } = child.getBoundingClientRect();
      return { x, y, width, height };
    }),
  );
  expect(Math.abs(a.y - b.y)).toBeLessThan(2);
  expect(Math.abs(a.width - b.width)).toBeLessThan(2);
  await expect(details.getByRole("heading", { name: /Walk.*→/ })).toHaveCount(
    0,
  );
  await expect(details.locator(".usyd-transit")).toHaveCount(0);
});

test("catalogue shows only the commute duration without changing filter mode", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const catalogue = await (
    await request.get("/api/v1/listings?page_size=1")
  ).json();
  const home = catalogue.items[0];
  const source = {
    status: "planned",
    queried_at: new Date().toISOString(),
    source_url: "https://opendata.transport.nsw.gov.au/",
  };
  home.usyd_commute = {
    ...home.usyd_commute,
    transit_options: [],
    selected_transit_route: undefined,
    estimates: {},
    modes: {
      public_transport: { ...source, duration_minutes: 50 },
      train: { ...source, duration_minutes: 50 },
      bus: { ...source, duration_minutes: 50 },
      drive: { ...source, duration_minutes: 14 },
      bike: { ...source, duration_minutes: 42 },
      walk: { ...source, duration_minutes: 180 },
    },
  };
  const requested: string[] = [];
  await page.route("**/api/v1/listings?*", (route) => {
    requested.push(route.request().url());
    return route.fulfill({ json: { ...catalogue, total: 1, items: [home] } });
  });
  await page.goto(`/cases/${c.case_id}/recommendations`);
  const cell = page.getByRole("cell").filter({
    has: page.getByLabel("Commute to USYD", { exact: true }),
  });
  await expect(cell).toContainText("37 min");
  await expect(cell.locator(".commute-time")).not.toContainText("Commute");
  await expect(cell.locator(".commute-time")).not.toHaveAttribute("title", /Weighted reference/);
  await expect(
    page.getByRole("columnheader", { name: "Commute to USYD", exact: true }),
  ).toBeVisible();
  await expect(cell.locator("details")).toHaveCount(0);
  await expect(cell).not.toContainText("Avg.");
  await expect(cell).not.toContainText("modes");
  await expect(cell).not.toContainText("Reference average");
  await page
    .getByRole("combobox", { name: "Commute mode to campus", exact: true })
    .click();
  await page
    .getByRole("option", {
      name: "Public transport (any combination)",
      exact: true,
    })
    .click();
  await page
    .getByRole("spinbutton", {
      name: "Maximum commute to USYD (minutes)",
      exact: true,
    })
    .fill("45");
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect
    .poll(() =>
      requested.some(
        (url) =>
          new URL(url).searchParams.get("usyd_mode") === "public_transport" &&
          new URL(url).searchParams.get("usyd_max_minutes") === "45",
      ),
    )
    .toBeTruthy();
  await page.screenshot({ path: "/tmp/rental-commute-average.png" });
});
