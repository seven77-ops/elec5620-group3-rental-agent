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
  await request.post(root + "/selections", {
    data: {
      request_id: "select",
      run_id: run.run_id,
      listing_id: run.report.pending_confirmation[0].listing_id,
      confirmed: true,
    },
  });
  const consent = await (
    await request.post(root + "/contract-consents", {
      data: { confirmed: true },
    })
  ).json();
  const raw =
    "Synthetic test contract\nAddress: 1 Example Street, Sydney NSW 2000\nWeekly rent: AUD 650 per week\nBond: AUD 2600\nStart date: 2026-11-01\nEnd date: 2027-11-01\n6. Cleaning\nThe tenant must leave the premises reasonably clean, except for fair wear and tear.\n7. Repairs\nNotify Example Agent promptly when repairs are needed.\n";
  const upload = await request.post(root + "/contract-reviews", {
    data: Buffer.from(raw),
    headers: {
      "Content-Type": "application/octet-stream",
      "X-Consent-Id": consent.consent_id,
      "X-Request-Id": "upload",
      "X-Filename": "synthetic-test-contract.txt",
    },
  });
  expect(upload.status()).toBe(200);
  return { c, root };
}

test("contract search needs separate consent and shows local page/section citations, then forgets derived data", async ({
  page,
  request,
}) => {
  const { c, root } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=review`);
  await page
    .getByRole("button", { name: "Ask more about this contract", exact: true })
    .click();
  const panel = page.getByRole("region", {
    name: "Private contract Q&A",
    exact: true,
  });
  const enable = panel.getByRole("button", {
    name: "Enable contract search",
    exact: true,
  });
  await expect(enable).toBeDisabled();
  await panel
    .getByRole("checkbox", {
      name: "I agree to enable private search for this contract on this device.",
      exact: true,
    })
    .check();
  await enable.click();
  await expect(panel).toContainText("Contract search ready");
  await panel
    .getByRole("textbox", { name: "Contract question", exact: true })
    .fill("What does the cleaning clause say?");
  await panel
    .getByRole("button", { name: "Find contract text", exact: true })
    .click();
  const evidence = panel.getByRole("region", {
    name: "Knowledge evidence",
    exact: true,
  });
  await expect(evidence).toContainText("Contract and reference sources");
  await evidence.getByText("Read source excerpts", { exact: true }).click();
  await expect(evidence).toContainText("Uploaded contract");
  await expect(evidence).toContainText("Page 1");
  await expect(evidence).toContainText("fair wear and tear");
  if (
    (await panel
      .getByRole("button", { name: "Search permissions", exact: true })
      .getAttribute("aria-expanded")) !== "true"
  ) {
    await panel
      .getByRole("button", { name: "Search permissions", exact: true })
      .click();
  }
  await panel
    .getByRole("button", { name: "Turn off contract search", exact: true })
    .click();
  await expect(
    panel.getByRole("region", { name: "Knowledge evidence" }),
  ).toHaveCount(0);
  await expect(enable).toBeDisabled();
  expect((await (await request.get(root)).json()).reviews).toHaveLength(1);
});

test("forgetting contract search during a question ignores a late private answer", async ({
  page,
  request,
}) => {
  const { c } = await seed(request);
  await page.goto(`/cases/${c.case_id}/contract?mode=review`);
  await page
    .getByRole("button", { name: "Ask more about this contract", exact: true })
    .click();
  const panel = page.getByRole("region", {
    name: "Private contract Q&A",
    exact: true,
  });
  await panel
    .getByRole("checkbox", {
      name: "I agree to enable private search for this contract on this device.",
      exact: true,
    })
    .check();
  await panel
    .getByRole("button", { name: "Enable contract search", exact: true })
    .click();
  await expect(panel).toContainText("Contract search ready");
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/rag/contracts/*/answers", async (route) => {
    await gate;
    await route.fulfill({
      json: {
        status: "answered",
        scope: "contract",
        knowledge_language: "original",
        language: "en",
        answer: "Synthetic late private answer must remain hidden",
        citations: [],
        unknowns: [],
        warnings: [],
        retrieval_methods: [],
      },
    });
  });
  await panel
    .getByRole("textbox", { name: "Contract question", exact: true })
    .fill("What does cleaning mean?");
  await panel
    .getByRole("button", { name: "Find contract text", exact: true })
    .click();
  await panel
    .getByRole("button", { name: "Search permissions", exact: true })
    .click();
  await expect(
    panel.getByRole("button", {
      name: "Turn off contract search",
      exact: true,
    }),
  ).toBeEnabled();
  if (
    (await panel
      .getByRole("button", { name: "Search permissions", exact: true })
      .getAttribute("aria-expanded")) !== "true"
  ) {
    await panel
      .getByRole("button", { name: "Search permissions", exact: true })
      .click();
  }
  await panel
    .getByRole("button", { name: "Turn off contract search", exact: true })
    .click();
  await expect(panel).toContainText("Revoked");
  const late = page.waitForResponse(
    (r) => r.url().includes("/rag/contracts/") && r.url().endsWith("/answers"),
  );
  release();
  await late;
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  );
  await expect(
    panel.getByRole("region", { name: "Knowledge evidence" }),
  ).toHaveCount(0);
  await expect(panel).not.toContainText("Synthetic late private answer");
});
