import { test, expect } from "@playwright/test";

test("old fictional review history uses an English address while original Chinese records remain intact", async ({
  page,
}) => {
  const address = "虚构示例楼 6 号房（不存在的地址）";
  const selection = {
    data_mode: "synthetic_demo",
    listing_id: "DEMO-006",
    listing_snapshot: {
      listing_id: "DEMO-006",
      source: "synthetic-fixture",
      data_kind: "synthetic",
      source_listing_id: "fixture-6",
      address,
    },
  };
  const base = {
    kind: "contract",
    case_id: "fictional-case",
    version: 2,
    status: "closed",
    reason: "High-risk contract review",
    created_at: "2026-10-17T12:37:00+11:00",
    decisions: [
      {
        note: "Synthetic rent difference reviewed; demonstration decision only.",
        decided_at: "2026-10-17T12:37:00+11:00",
      },
    ],
  };
  const items = [
    {
      ...base,
      review_id: "bundled-demo",
      address,
      review: {
        fields: {
          address: {
            value: address,
            evidence: { quote: "Address: " + address },
          },
        },
        findings: [],
        selection_evidence: selection,
      },
    },
    {
      ...base,
      review_id: "user-original",
      address: "用户原始地址：示例路六号",
      review: {
        fields: { address: { value: "用户原始地址：示例路六号" } },
        findings: [],
      },
    },
  ];
  await page.route("**/api/v1/operator/reviews", (route) =>
    route.fulfill({ json: { items, pending_count: 0 } }),
  );
  await page.goto("/operator");
  await page.getByRole("tab", { name: "History (2)", exact: true }).click();
  const cards = page
    .getByRole("region", { name: "Review history", exact: true })
    .getByTestId("operator-review");
  await expect(cards).toHaveCount(2);
  await expect(cards.first()).toContainText(
    "Fictional Example Building, Unit 6 (nonexistent demo address)",
  );
  await expect(cards.first()).not.toContainText(address);
  await expect(cards.nth(1)).toContainText("用户原始地址：示例路六号");
  await page
    .getByRole("button", { name: "Refresh reports", exact: true })
    .click();
  await expect(cards.first()).toContainText(
    "Fictional Example Building, Unit 6",
  );
  expect(items[0].review.fields.address.value).toBe(address);
  expect(items[0].review.fields.address.evidence?.quote).toBe(
    "Address: " + address,
  );
});
