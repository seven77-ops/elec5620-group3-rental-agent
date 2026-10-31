import { expect, test } from "@playwright/test";

test("provider plan browser filters and paginates all official plans without saving", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const directory = await (
    await request.get("/api/v1/living-providers")
  ).json();
  const plans = directory.providers.find(
    (p: { id: string }) => p.id === "agl",
  ).plans;
  await page.goto(`/cases/${c.case_id}/aftercare?tab=utilities`);
  await page
    .getByRole("button", { name: "AGL, view provider details", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "AGL · Provider details",
    exact: true,
  });
  await expect(modal.getByRole("tab", { name: /^All/ })).toBeVisible();
  await expect(modal.locator(".utility-plan")).toHaveCount(4);
  const seen = new Set<string>();
  while (seen.size < plans.length) {
    const ids = await modal
      .locator(".utility-plan")
      .evaluateAll((nodes) =>
        nodes.map((n) => n.getAttribute("data-plan-id")!),
      );
    ids.forEach((id) => seen.add(id));
    if (seen.size === plans.length) break;
    await modal.locator(".ant-pagination-next button").click();
    await expect(modal.locator(".utility-plan").first()).not.toHaveAttribute(
      "data-plan-id",
      ids[0],
    );
  }
  expect([...seen].sort()).toEqual(
    plans.map((p: { id: string }) => p.id).sort(),
  );
  await modal.getByRole("tab", { name: /^Electricity/ }).click();
  const network = plans.find(
    (p: { category: string }) => p.category === "electricity",
  ).network_label;
  await modal
    .getByRole("combobox", { name: "Filter network", exact: true })
    .click();
  await page
    .locator(".ant-select-dropdown:visible .ant-select-item-option-content")
    .getByText(network, { exact: true })
    .click();
  const matched = plans.filter(
    (p: { category: string; network_label: string }) =>
      p.category === "electricity" && p.network_label === network,
  );
  await expect(modal.locator(".utility-plan")).toHaveCount(
    Math.min(4, matched.length),
  );
  for (const card of await modal.locator(".utility-plan").all())
    await expect(card).toContainText(network);
  await modal
    .getByRole("textbox", { name: "Search plans", exact: true })
    .fill("no-such-plan-123");
  await expect(
    modal.getByText("No plans match the filters", { exact: true }),
  ).toBeVisible();
  await modal
    .getByRole("button", { name: "Clear filters", exact: true })
    .click();
  await expect(modal.locator(".utility-plan")).toHaveCount(4);
  await modal
    .getByRole("button", { name: "Close details", exact: true })
    .focus();
  await page.screenshot({
    path: "/tmp/utility-plan-browser-desktop.png",
    animations: "disabled",
  });
  const state = await (
    await request.get(`/api/v1/cases/${c.case_id}/living-services`)
  ).json();
  expect(state.version).toBe(0);
});
