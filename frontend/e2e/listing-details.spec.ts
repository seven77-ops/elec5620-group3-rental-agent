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
  await expect(page.locator(".real-catalog-filters")).not.toContainText("到校时间");
  await expect(page.locator(".real-catalog-filters")).not.toContainText("最多换乘");
  await page.getByRole("button", { name: "查看房源详情", exact: true }).click();
  const d = page.getByRole("dialog");
  await expect(d).not.toContainText("在租状态待确认");
  await expect(d).not.toContainText("房源资料采集于");
  await expect(d.getByTestId("listing-detail-rent")).toContainText("540");
  await expect(d.getByTestId("listing-detail-facts")).toHaveCount(0);
  await expect(d.getByTestId("listing-detail-features")).toHaveCount(0);
  await expect(d).not.toContainText("Unverified");
  await expect(d).not.toContainText("未知 / 待核实");
  await expect(d).not.toContainText("today");
  await expect(
    d.getByRole("heading", { name: "待确认事项", exact: true }),
  ).toHaveCount(0);
  await expect(
    d.getByRole("link", { name: "查看 Domain 房源", exact: true }),
  ).toHaveAttribute("href", item.source_url);
  await expect(d).not.toContainText("广告");
  await page.screenshot({ path: "/tmp/rental-fields-cleanup-desktop.png" });
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
  await expect(d.getByTestId("listing-detail-pending")).toHaveCount(0);
  await expect(d.getByTestId("listing-detail-facts")).toHaveCount(0);
  await expect(d).not.toContainText("未知 / 待核实");
  await expect(d).not.toContainText("不带家具");
  await expect(d).not.toContainText("today");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "/tmp/rental-fields-cleanup-mobile.png" });
});
