import { expect, test, type APIRequestContext } from "@playwright/test";

async function seed(
  request: APIRequestContext,
  message = "想找悉大步行20分钟以内的整租，每周1200，至少1卧1卫",
) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  const chat = await (
    await request.post(`${root}/assistant/conversations`, { data: {} })
  ).json();
  const sent = await request.post(
    `${root}/assistant/conversations/${chat.conversation_id}/messages`,
    {
      data: {
        request_id: `seed-${crypto.randomUUID()}`,
        expected_revision: 0,
        message,
        allow_external_ai: true,
        allow_external_data: true,
      },
    },
  );
  expect(sent.ok()).toBe(true);
  return {
    c,
    root,
    chat: await sent.json(),
    chatUrl: `${root}/assistant/conversations/${chat.conversation_id}`,
  };
}

test("推荐可直接选定，无需收藏或重复同步需求；取消不写入", async ({
  page,
  request,
}, info) => {
  const { c, root, chat, chatUrl } = await seed(request);
  await page.goto(`/cases/${c.case_id}/assistant`);
  const result = page.locator(".commute-results").last();
  const selected = chat.messages.at(-1).listings[0];
  await result
    .getByRole("button", { name: "Select and follow up", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Select this property and start follow-up?",
    exact: true,
  });
  await expect(dialog).toContainText(selected.address);
  await expect(dialog).toContainText("1200");
  await expect(
    page.getByRole("dialog", { name: "My rental needs", exact: true }),
  ).toHaveCount(0);
  await dialog
    .getByRole("button", { name: "Keep comparing", exact: true })
    .click();
  expect((await (await request.get(root)).json()).selection).toBeNull();
  expect((await (await request.get(root)).json()).confirmations).toHaveLength(
    0,
  );
  await result
    .getByRole("button", { name: "Select and follow up", exact: true })
    .first()
    .click();
  await dialog
    .getByRole("button", { name: "Confirm and start follow-up", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("candidate-next")).toContainText(
    selected.address,
  );
  await expect(
    page
      .getByTestId("candidate-next")
      .getByRole("button", {
        name: "Prepare inspection and enquiry",
        exact: true,
      }),
  ).toBeVisible();
  const saved = await (await request.get(root)).json();
  expect(saved.confirmations).toHaveLength(1);
  expect(saved.selection.listing_id).toBe(selected.listing_id);
  expect(
    (await (await request.get(`${root}/favorites`)).json()).items,
  ).toHaveLength(0);
  const current = await (await request.get(chatUrl)).json();
  expect(
    current.messages.filter((m: { listings: unknown[] }) => m.listings.length),
  ).toHaveLength(1);
  await page.reload();
  await expect(page.getByTestId("candidate-next")).toContainText(
    selected.address,
  );
  await page.screenshot({
    path: info.outputPath("direct-followup.png"),
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await result
    .getByRole("button", { name: "Select and follow up", exact: true })
    .first()
    .click();
  await expect(dialog).toContainText(
    "This will replace your current follow-up property:",
  );
  await dialog
    .getByRole("button", { name: "Keep comparing", exact: true })
    .hover();
  await page.screenshot({
    path: info.outputPath("selection-confirmation-mobile.png"),
    animations: "disabled",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await dialog
    .getByRole("button", { name: "Keep comparing", exact: true })
    .click();
});

test("房源推荐目录也可以直接选定，按当前筛选保存需求且不要求先收藏", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const root = `/api/v1/cases/${c.case_id}`;
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await page
    .getByLabel("Maximum weekly rent (AUD)", { exact: true })
    .fill("900");
  await page.getByLabel("Minimum bedrooms", { exact: true }).fill("2");
  await page.getByLabel("Minimum bathrooms", { exact: true }).fill("1");
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await page
    .getByTestId("real-catalog")
    .getByRole("button", { name: "Select and follow up", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Select this property and start follow-up?",
    exact: true,
  });
  await expect(dialog).toContainText("900");
  await dialog
    .getByRole("button", { name: "Confirm and start follow-up", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  const saved = await (await request.get(root)).json();
  expect(saved.selection).toBeTruthy();
  expect(saved.draft.profile.budget.maximum).toBe(900);
  expect(saved.draft.profile.housing_preferences.min_bedrooms).toBe(2);
  expect(
    (await (await request.get(`${root}/favorites`)).json()).items,
  ).toHaveLength(0);
});

test("收藏和比较不触发选定，确认时只补缺失的预算口径并继续跟进", async ({
  page,
  request,
}) => {
  const { c, root } = await seed(request, "我想住Burwood预算1200每周");
  const rows = (
    await (
      await request.get("/api/v1/listings?suburb=Burwood&max_weekly_rent=1200")
    ).json()
  ).items;
  for (const row of rows.slice(0, 2))
    await request.post(`${root}/favorites`, {
      data: {
        request_id: crypto.randomUUID(),
        listing_id: row.listing_id,
        saved: true,
      },
    });
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByRole("button", { name: "My favorites (2)", exact: true })
    .click();
  const drawer = page.getByRole("dialog", {
    name: "My favorites",
    exact: true,
  });
  await drawer.getByRole("checkbox").nth(0).check();
  await drawer.getByRole("checkbox").nth(1).check();
  await expect(
    drawer.getByRole("table", { name: "Saved listing comparison" }),
  ).toBeVisible();
  expect((await (await request.get(root)).json()).selection).toBeNull();
  await drawer
    .getByRole("button", { name: "Select and follow up", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Select this property and start follow-up?",
    exact: true,
  });
  await expect(dialog.getByRole("combobox")).toHaveCount(1);
  await dialog.getByLabel("Budget pricing basis", { exact: true }).click();
  await page
    .locator(".ant-select-dropdown:visible .ant-select-item-option-content")
    .getByText("Whole property", { exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "Confirm and start follow-up", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(drawer).not.toBeVisible();
  await expect(page.getByTestId("candidate-next")).toBeVisible();
  expect(
    (await (await request.get(`${root}/favorites`)).json()).items,
  ).toHaveLength(2);
});

test("需求保存只点击一次，同条件复用结果，修改预算只更新一遍", async ({
  page,
  request,
}) => {
  const { c, chatUrl } = await seed(request);
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByRole("button", { name: "My rental needs", exact: true })
    .click();
  const drawer = page.getByRole("dialog", {
    name: "My rental needs",
    exact: true,
  });
  await drawer
    .getByRole("button", { name: "Save rental needs", exact: true })
    .click();
  await expect(drawer).not.toBeVisible();
  let current = await (await request.get(chatUrl)).json();
  expect(
    current.messages.filter((m: { listings: unknown[] }) => m.listings.length),
  ).toHaveLength(1);
  await page
    .getByRole("button", { name: "My rental needs", exact: true })
    .click();
  await drawer.getByLabel("Maximum budget (AUD)", { exact: true }).fill("1100");
  await drawer
    .getByRole("button", { name: "Save rental needs", exact: true })
    .click();
  await expect(drawer).not.toBeVisible();
  current = await (await request.get(chatUrl)).json();
  expect(
    current.messages.filter((m: { listings: unknown[] }) => m.listings.length),
  ).toHaveLength(2);
  expect(current.messages.at(-1).recommendation_change).toBeTruthy();
  await expect(
    page.getByRole("dialog", {
      name: "Confirm sync of rental needs?",
      exact: true,
    }),
  ).toHaveCount(0);
});

test("历史卡片选定确认使用当前目录地址及租金", async ({ page, request }) => {
  const { c, chat, chatUrl } = await seed(request);
  const current = chat.messages.at(-1).listings[0];
  await page.route(`**${chatUrl}`, async (route) => {
    const response = await route.fetch();
    const value = await response.json();
    const result = value.messages.find(
      (m: { listings: unknown[] }) => m.listings.length,
    );
    result.listings[0] = {
      ...result.listings[0],
      address: "Fictional outdated preview address",
      weekly_rent: 1,
    };
    await route.fulfill({ response, json: value });
  });
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .locator(".commute-results")
    .last()
    .getByRole("button", { name: "Select and follow up", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Select this property and start follow-up?",
    exact: true,
  });
  await expect(dialog).toContainText(current.address);
  await expect(dialog).toContainText(`AUD ${current.weekly_rent}/week`);
  await expect(dialog).not.toContainText("Fictional outdated preview address");
  await expect(dialog).toContainText("Listing details changed");
});
