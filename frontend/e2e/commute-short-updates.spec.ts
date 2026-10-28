import { expect, test } from "@playwright/test";

test("聊天短句将步行10分钟改为公共交通20分钟，并保留预算和户型", async ({
  page,
  request,
}, info) => {
  test.skip(
    process.env.FULL_JOURNEY_ISOLATED !== "1",
    "使用 scripts/test_full_journey.py 的隔离环境。",
  );
  const created = await request.post("/api/v1/cases", { data: {} });
  expect(created.ok()).toBe(true);
  const c = await created.json();
  const root = `/api/v1/cases/${c.case_id}`;
  const conversation = await (
    await request.post(`${root}/assistant/conversations`, { data: {} })
  ).json();
  const chat = `${root}/assistant/conversations/${conversation.conversation_id}`;
  const prepared = await request.post(`${chat}/proposals`, {
    data: {
      request_id: `prepare-${crypto.randomUUID()}`,
      expected_revision: 0,
      expected_profile_fingerprint: c.draft.fingerprint,
      brief: {
        recommend_areas: true,
        suburb: null,
        budget_amount: 900,
        budget_period: "week",
        budget_scope: "whole_property",
        rental_mode: "whole_property",
        min_bedrooms: 2,
        min_bathrooms: 1,
        min_car_spaces: 0,
        occupants: 2,
        commute_mode: "public_transport",
        commute_max_minutes: 50,
      },
    },
  });
  expect(prepared.ok()).toBe(true);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`/cases/${c.case_id}/assistant`);
  const input = page.getByRole("textbox", {
    name: "给租房助手的消息",
    exact: true,
  });
  const controls = page.getByRole("region", {
    name: "本次找房条件",
    exact: true,
  });
  await input.fill("我想步行十分钟到达的房子·");
  await input.press("Enter");
  await expect(controls).toContainText("步行 ≤10分钟");
  await expect(controls).toContainText("已筛选 0 套");
  await input.fill("公共交通20分钟");
  await input.press("Enter");
  await expect(controls).toContainText("公共交通 ≤20分钟");
  const reference = await (
    await request.get(
      "/api/v1/listings?max_weekly_rent=900&min_bedrooms=2&min_bathrooms=1&min_car_spaces=0&usyd_mode=public_transport&usyd_max_minutes=20",
    )
  ).json();
  expect(reference.total).toBeGreaterThan(0);
  await expect(controls).toContainText(`已筛选 ${reference.total} 套`);
  const result = page.locator(".commute-results").last();
  await expect(
    result.getByRole("list", { name: "推荐理由" }).first(),
  ).toContainText("公共交通");
  const updated = await (await request.get(chat)).json();
  expect(updated.rental_brief).toMatchObject({
    budget_amount: 900,
    min_bedrooms: 2,
    min_bathrooms: 1,
    occupants: 2,
    commute_mode: "public_transport",
    commute_max_minutes: 20,
  });
  expect(updated.messages.at(-1).listings).toHaveLength(reference.total);
  const path = info.outputPath("chat-commute-updated.png");
  await page.screenshot({ path, animations: "disabled" });
  await info.attach("聊天通勤修改已生效", { path, contentType: "image/png" });
  await page.reload();
  await expect(controls).toContainText("公共交通 ≤20分钟");
  expect((await (await request.get(root)).json()).draft.fingerprint).toBe(
    c.draft.fingerprint,
  );
  expect(errors).toEqual([]);
});
