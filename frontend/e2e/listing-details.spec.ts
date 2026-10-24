import { test, expect } from "@playwright/test";

test("property details surface available facts and omit extraction noise and advertising copy", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const catalog = await (
    await request.get("/api/v1/listings?page_size=100")
  ).json();
  const item = catalog.items.find(
    (x: { listing_id: string }) => x.listing_id === "domain:18363778",
  );
  expect(item).toBeTruthy();
  await page.route("**/api/v1/listings?*", (route) =>
    route.fulfill({
      json: {
        ...catalog,
        total: 1,
        items: [
          {
            ...item,
            photos: [],
            features: [
              ...item.features,
              "Unverified feature",
              "Apartments & units for rent in Bexley #### Domain",
            ],
          },
        ],
      },
    }),
  );
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(
    page.getByRole("heading", { name: "真实房源推荐", exact: true }),
  ).toBeVisible();
  await expect(page.locator("body")).not.toContainText("广告");
  await page.getByRole("button", { name: "查看房源详情", exact: true }).click();
  const d = page.getByRole("dialog");
  await expect(d.getByTestId("listing-detail-rent")).toContainText("540");
  await expect(d.getByTestId("listing-detail-facts")).toContainText("Studio");
  await expect(d.getByTestId("listing-detail-facts")).toContainText("2,160");
  await expect(d.getByTestId("listing-detail-facts")).toContainText(
    "2026/11/11",
  );
  await expect(d.getByTestId("listing-detail-facts")).toContainText("不带家具");
  await expect(
    d.getByRole("heading", { name: "房屋配置", exact: true }),
  ).toBeVisible();
  await expect(d.getByTestId("listing-detail-features")).toContainText("阳台");
  await expect(d.getByTestId("listing-detail-features")).toContainText(
    "燃气设施",
  );
  await expect(d.getByTestId("listing-detail-features")).not.toContainText(
    "Domain",
  );
  await expect(d).not.toContainText("Unverified");
  await expect(d).not.toContainText("未知 / 待核实");
  await expect(d).not.toContainText("today");
  await expect(
    d.getByRole("heading", { name: "待确认事项", exact: true }),
  ).toBeVisible();
  await expect(
    d.getByRole("link", { name: "查看 Domain 房源", exact: true }),
  ).toHaveAttribute("href", item.source_url);
  await expect(d).not.toContainText("广告");
});

test("missing property facts stay compact without invented deposit, furniture or facilities", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const catalog = await (await request.get("/api/v1/listings")).json();
  const item = {
    ...catalog.items[0],
    photos: [],
    property_type: null,
    bond: null,
    furnishing: null,
    available_from: null,
    available_from_raw: null,
    features: [],
  };
  await page.route("**/api/v1/listings?*", (route) =>
    route.fulfill({ json: { ...catalog, total: 1, items: [item] } }),
  );
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await page.getByRole("button", { name: "查看房源详情", exact: true }).click();
  const d = page.getByRole("dialog");
  await expect(d.getByTestId("listing-detail-summary")).toContainText("1");
  await expect(
    d.getByRole("heading", { name: "房屋配置", exact: true }),
  ).toHaveCount(0);
  await expect(d.getByTestId("listing-detail-pending")).toContainText("押金");
  await expect(d.getByTestId("listing-detail-pending")).toContainText("家具");
  await expect(d.getByTestId("listing-detail-pending")).toContainText(
    "可入住日期",
  );
  await expect(d).not.toContainText("未知 / 待核实");
  await expect(d).not.toContainText("不带家具");
  await expect(d).not.toContainText("today");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
