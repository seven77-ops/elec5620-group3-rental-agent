import { test, expect, type APIRequestContext } from "@playwright/test";

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
      data: { request_id: "eval", confirmation_version: 1 },
    })
  ).json();
  const row = run.report.pending_confirmation[0];
  const response = await request.post(root + "/selections", {
    data: {
      request_id: "select",
      run_id: run.run_id,
      listing_id: row.listing_id,
      confirmed: true,
    },
  });
  expect(response.status()).toBe(200);
  return { c, root, row };
}

test("viewing checklist has no reply form; existing saved facts remain available to contract review", async ({
  page,
  request,
}) => {
  const { c, root, row } = await seed(request);
  // Existing saved records remain usable by contracts after the input UI is retired.
  const previous = await (
    await request.get(root + "/candidate-followup")
  ).json();
  const restored = await request.post(root + "/candidate-followup", {
    data: {
      request_id: "historical-record",
      expected_version: 0,
      selection_signature: previous.selection_signature,
      confirmed: true,
      facts: {
        ...previous.facts,
        rent_amount: 600,
        rent_period: "week",
        rent_scope: "whole_property",
        source_note: "10月22日中介邮件",
      },
    },
  });
  expect(restored.ok()).toBe(true);
  await page.goto(`/cases/${c.case_id}/recommendations`);
  const next = page.getByTestId("candidate-next");
  await expect(next).toContainText(row.address);
  await expect(
    next.getByRole("button", { name: "Record agent reply", exact: true }),
  ).toHaveCount(0);
  await next
    .getByRole("button", {
      name: "Prepare inspection and enquiry",
      exact: true,
    })
    .click();
  const drawer = page.getByRole("dialog", {
    name: "Inspection enquiry checklist",
    exact: true,
  });
  await expect(
    drawer.getByText(
      "Is the property still available, and when can I inspect it?",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(drawer.locator("input, textarea")).toHaveCount(0);
  await expect(drawer.getByRole("combobox")).toHaveCount(0);
  await drawer
    .getByRole("button", { name: "Review an existing contract", exact: true })
    .click();
  await expect(
    page.getByText("Review an existing contract directly", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Agree to process this contract",
      exact: true,
    }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", {
      name: "I agree to process this contract for this review and understand this consent is separate from property selection.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", {
      name: "Agree to process this contract",
      exact: true,
    })
    .click();
  const contract = `Address: ${row.address}\nLandlord: Example Owner\nTenant: Example Tenant\nRent: AUD 620 per week whole property\nBond: AUD 2480\nStart date: 2026-11-01\nEnd date: 2027-11-01\n`;
  await page.locator("input[type=file]").setInputFiles({
    name: "actual-lease.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(contract),
  });
  await page
    .getByRole("checkbox", {
      name: "I confirm I am authorised to submit this contract for review.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "Upload and review", exact: true })
    .click();
  const comparison = page.getByTestId("real-contract-comparison");
  await expect(comparison).toContainText("10月22日中介邮件");
  await expect(page.getByTestId("comparison-recorded_rent")).toContainText(
    "Review differences",
  );
  await expect(page.getByTestId("comparison-recorded_rent")).toContainText(
    "600",
  );
  await expect(page.getByTestId("comparison-recorded_rent")).toContainText(
    "620",
  );
  await expect(page.getByTestId("comparison-advertised_rent")).toContainText(
    "Confirm pricing basis",
  );
  await page.reload();
  await expect(comparison).toContainText(row.address);
});

test("chat follow-up intent routes to the saved candidate without inventing verification", async ({
  page,
  request,
}) => {
  const { c, root, row } = await seed(request);
  const conversation = await (
    await request.post(root + "/assistant/conversations", { data: {} })
  ).json();
  const r = await request.post(
    root + `/assistant/conversations/${conversation.conversation_id}/messages`,
    {
      data: {
        request_id: "follow",
        expected_revision: 0,
        message: "就这套，下一步问中介什么？",
        allow_external_ai: true,
      },
    },
  );
  expect(r.status()).toBe(200);
  await page.goto(`/cases/${c.case_id}/assistant`);
  await expect(
    page.getByText(new RegExp("For your saved listing")),
  ).toContainText(row.address);
  await page
    .getByRole("button", {
      name: "View inspection enquiry checklist",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("dialog", {
      name: "Inspection enquiry checklist",
      exact: true,
    }),
  ).toBeVisible();
  expect(
    (await (await request.get(root)).json()).selection.requires_verification,
  ).toBe(true);
});

test("mobile viewing checklist fits the viewport and never creates follow-up records", async ({
  page,
  request,
}, info) => {
  const { c, root } = await seed(request);
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(`/cases/${c.case_id}/assistant`);
  await page
    .getByTestId("candidate-next")
    .getByRole("button", {
      name: "Prepare inspection and enquiry",
      exact: true,
    })
    .click();
  const drawer = page.getByRole("dialog", {
    name: "Inspection enquiry checklist",
    exact: true,
  });
  await expect(drawer).toBeVisible();
  await expect(drawer.locator("input, textarea")).toHaveCount(0);
  await expect(
    drawer.getByRole("link", {
      name: "Download enquiry checklist",
      exact: true,
    }),
  ).toHaveAttribute("href", /candidate-followup\/questions$/);
  await expect(async () => {
    const rect = await drawer.boundingBox();
    expect(rect!.width).toBeLessThanOrEqual(360);
    expect(rect!.x).toBeGreaterThanOrEqual(0);
  }).toPass();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await drawer
    .getByRole("button", { name: "Enter lease details", exact: true })
    .hover();
  const image = info.outputPath("viewing-checklist-mobile.png");
  await page.screenshot({ path: image, animations: "disabled" });
  await info.attach("仅保留看房询问清单", {
    path: image,
    contentType: "image/png",
  });
  await drawer.getByRole("button", { name: "Close", exact: true }).click();
  expect(
    (await (await request.get(root + "/candidate-followup")).json()).version,
  ).toBe(0);
});
