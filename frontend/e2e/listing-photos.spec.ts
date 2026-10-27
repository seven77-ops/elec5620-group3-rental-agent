import {
  expect,
  test,
  type Page,
  type APIRequestContext,
} from "@playwright/test";

async function photoFixture(page: Page, request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const catalog = await (
    await request.get("/api/v1/listings?page=1&page_size=40")
  ).json();
  expect(catalog.items.length).toBeGreaterThanOrEqual(21);
  const png = Buffer.from(
    await page.evaluate(() => {
      const canvas = document.createElement("canvas");
      canvas.width = 4;
      canvas.height = 3;
      const context = canvas.getContext("2d")!;
      context.fillStyle = "#174EA6";
      context.fillRect(0, 0, 4, 3);
      return canvas.toDataURL("image/png").split(",")[1];
    }),
    "base64",
  );
  const urls = [
    "https://rimh2.domainstatic.com.au/photo-fixture-one",
    "https://rimh2.domainstatic.com.au/photo-fixture-two",
    "https://rimh2.domainstatic.com.au/photo-fixture-broken",
    "https://rimh2.domainstatic.com.au/photo-fixture-other-listing",
  ];
  const items = catalog.items.map(
    (item: Record<string, unknown>, index: number) => ({
      ...item,
      photos: (index === 0
        ? [urls[0], urls[1]]
        : index === 1
          ? [urls[2]]
          : index === 20
            ? [urls[3]]
            : []
      ).map((url) => ({
        url,
        source_url: item.source_url,
        captured_at: "2026-10-22T00:00:00Z",
      })),
    }),
  );
  await page.route("https://rimh2.domainstatic.com.au/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/png",
      body:
        route.request().url() === urls[2] ? Buffer.from("not an image") : png,
    }),
  );
  await page.route("**/api/v1/listings?*", (route) => {
    const query = new URL(route.request().url()).searchParams;
    const number = Number(query.get("page") || 1);
    return route.fulfill({
      json: {
        ...catalog,
        total: 40,
        page: number,
        page_size: 20,
        items: items.slice((number - 1) * 20, number * 20),
      },
    });
  });
  await page.route("**/api/v1/listings/*", (route) => {
    const identifier = decodeURIComponent(new URL(route.request().url()).pathname.split("/").pop()!);
    const item = items.find((row: Record<string, unknown>) => row.listing_id === identifier);
    return item ? route.fulfill({ json: item }) : route.continue();
  });
  return { c, items, urls };
}

test("real-photo thumbnail opens details by keyboard, previews and retains observed source", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (entry) => {
    if (["warning", "error"].includes(entry.type())) errors.push(entry.text());
  });
  const { c, items, urls } = await photoFixture(page, request);
  await page.goto(`/cases/${c.case_id}/recommendations`);
  const thumb = page.getByRole("button", {
    name: `查看 ${items[0].address} 照片与详情`,
    exact: true,
  });
  await expect(thumb.getByRole("img")).toHaveAttribute("src", urls[0]);
  await expect
    .poll(() =>
      thumb
        .getByRole("img")
        .evaluate((img) => (img as HTMLImageElement).naturalWidth),
    )
    .toBeGreaterThan(0);
  await expect(page.getByTestId("real-catalog").locator("thead th")).toHaveText(
    ["房源", "卧室", "浴室", "车位", "周租", "到悉大", "操作"],
  );
  await thumb.focus();
  await page.keyboard.press("Enter");
  const drawer = page.getByRole("dialog");
  await expect(
    drawer.getByRole("heading", {
      name: String(items[0].address),
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    drawer.getByRole("link", { name: "照片来源", exact: true }).first(),
  ).toHaveAttribute("href", String(items[0].source_url));
  await expect(drawer.locator(".listing-photo-caption")).toContainText(
    "2026/10/22",
  );
  await drawer
    .getByRole("button", {
      name: `预览 ${items[0].address} 照片 1`,
      exact: true,
    })
    .click();
  await expect(page.locator(".ant-image-preview-img")).toHaveAttribute(
    "src",
    urls[0],
  );
  await page.keyboard.press("Escape");
  await expect(page.locator(".ant-image-preview-img")).toBeHidden();
  await expect(
    drawer.getByRole("heading", {
      name: String(items[0].address),
      exact: true,
    }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  await expect(page.locator("vite-error-overlay")).toHaveCount(0);
  await page.screenshot({
    path: "/tmp/listing-photos-desktop.png",
    fullPage: false,
  });
});

test("missing and broken images fall back without carrying photos to a different listing", async ({
  page,
  request,
}) => {
  const { c, items, urls } = await photoFixture(page, request);
  await page.goto(`/cases/${c.case_id}/recommendations`);
  const broken = page.getByRole("button", {
    name: `查看 ${items[1].address} 照片与详情`,
    exact: true,
  });
  await expect(broken).toContainText("暂无照片");
  await broken.click();
  await expect(
    page.getByRole("dialog").getByText("暂无照片", { exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  const missing = page.getByRole("button", {
    name: `查看 ${items[2].address} 照片与详情`,
    exact: true,
  });
  await expect(missing).toContainText("暂无照片");
  await missing.click();
  await expect(
    page.getByRole("dialog").getByText("暂无照片", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog").locator(`img[src="${urls[0]}"]`),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page.locator(".ant-pagination-item-2").click();
  const next = page.getByRole("button", {
    name: `查看 ${items[20].address} 照片与详情`,
    exact: true,
  });
  await next.click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("heading", { name: String(items[20].address), exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog").locator(`img[src="${urls[3]}"]`),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog").locator(`img[src="${urls[0]}"]`),
  ).toHaveCount(0);
});

test("photo rows and details fit a 360px viewport", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  const { c, items } = await photoFixture(page, request);
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await page
    .getByRole("button", {
      name: `查看 ${items[0].address} 照片与详情`,
      exact: true,
    })
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("link", { name: "照片来源", exact: true })
      .first(),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect
    .poll(async () => {
      const bounds = await page.getByRole("dialog").boundingBox();
      return Math.abs(bounds?.x ?? 1000);
    })
    .toBeLessThan(1);
  const bounds = await page.getByRole("dialog").boundingBox();
  expect(bounds!.width).toBeLessThanOrEqual(360);
  await page.screenshot({
    path: "/tmp/listing-photos-mobile.png",
    fullPage: false,
  });
});
