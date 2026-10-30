import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { readFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
const root = resolve(process.cwd(), "..");
const artifactDir = resolve(root, ".runtime/qa");
mkdirSync(artifactDir, { recursive: true });
async function seed(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  await request.post(`/api/v1/cases/${c.case_id}/profile-confirmations`, {
    data: {
      draft_revision: c.draft.revision,
      fingerprint: c.draft.fingerprint,
      review_token: c.agent1.review_token,
    },
  });
  const e = await (
    await request.post(`/api/v1/cases/${c.case_id}/evaluations`, {
      data: {
        request_id: `test-${crypto.randomUUID()}`,
        confirmation_version: 1,
      },
    })
  ).json();
  return { c, e };
}
async function navigate(page: Page, name: string) {
  await page.getByRole("menuitem", { name: new RegExp(name) }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}

test("tenant completes confirmed profile, true recommendation, selection, contract review and restoration", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto("/");
  await expect(page).toHaveTitle("Rental Assistant · ELEC5620");
  await page
    .getByRole("button", { name: "New demo case", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Generate recommendations", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText("Agent1 local preference service connected", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Confirm current preferences", exact: true })
    .click();
  await expect(
    page.getByText(
      "Listings are synthetic data at a fixed snapshot. Occupant count is recorded, but listing capacity is not currently checked.",
      { exact: true },
    ),
  ).toHaveCount(2);
  await page
    .getByRole("button", { name: "Confirm these criteria", exact: true })
    .click();
  await expect(
    page.getByText("Current draft confirmed · v1", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Generate recommendations", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Housing recommendations", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "All eligible 15", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "To confirm 9", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "Excluded 5", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "Duplicate records 1", exact: true }),
  ).toBeVisible();
  const first = page.locator("article.listing-row").first();
  await expect(first).toContainText("DEMO-006");
  await expect(first).toContainText("92.75");
  await page.screenshot({
    path: resolve(artifactDir, "recommendations-desktop.png"),
  });
  await first
    .getByRole("button", { name: "View recommendation evidence" })
    .click();
  await expect(
    page.getByText("fixture:DEMO-006#rent_amount", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("tab", { name: "To confirm 9", exact: true }).click();
  await expect(page.getByText("Unscored", { exact: true })).toHaveCount(9);
  await expect(
    page.getByRole("button", { name: "Select this listing", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("tab", { name: "Recommended listings 5", exact: true })
    .click();
  await first
    .getByRole("button", { name: "Select this listing", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm this listing", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Continue to contract review", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Contract review", exact: true }),
  ).toBeVisible();
  await expect(page.locator("input[type=file]")).toHaveCount(0);
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
  await page
    .locator("input[type=file]")
    .setInputFiles(
      resolve(root, "agent3/data/demo/agreements/selection-demo.txt"),
    );
  await page
    .getByRole("checkbox", {
      name: "I confirm this is a synthetic demo contract.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "Upload and review", exact: true })
    .click();
  await expect(
    page.getByText("Review complete", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "This review has no findings. No additional questions will be generated.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Prepare question list", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "View source text", exact: true })
    .first()
    .click();
  await expect(page.locator("blockquote")).toContainText("Address:");
  await page.getByRole("button", { name: "Close", exact: true }).click();
  const caseId = page.url().split("/")[4];
  const c = await (await request.get(`/api/v1/cases/${caseId}`)).json();
  const selection = await (
    await request.get(`/api/v1/cases/${caseId}/exports/selection`)
  ).json();
  expect(selection.listing_id).toBe("DEMO-006");
  expect(c.agent1.state).toBe("Confirmed");
  expect(c.confirmations[0].source).toBe("agent1");
  expect(c.evaluations[0].agent1_task_id).toMatch(/^task-/);
  expect(c.aftercare_case_id).toBeNull();
  await page.reload();
  await expect(
    page.getByText("Review complete", { exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: resolve(artifactDir, "contract-desktop.png") });
  await expect(page.locator("vite-error-overlay")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("edited preferences require reconfirmation and zero-match remains a valid report with history", async ({
  page,
  request,
}) => {
  const { c } = await seed(request);
  await page.goto(`/cases/${c.case_id}/preferences`);
  await page
    .getByRole("spinbutton", { name: "Preferred weekly budget (AUD)" })
    .fill("1");
  await page
    .getByRole("spinbutton", { name: "Maximum weekly budget (AUD)" })
    .fill("1");
  await expect(
    page.getByRole("button", { name: "Generate recommendations", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await expect(
    page.getByText("Current draft is not confirmed", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Confirm current preferences", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm these criteria", exact: true })
    .click();
  await expect(
    page.getByText("Current draft confirmed · v2", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Generate recommendations", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Housing recommendations", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "Recommended listings 0", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "No listings in this category. Try another category or adjust your preferences.",
      {
        exact: true,
      },
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Compare preference versions", exact: true })
    .click();
  await expect(
    page.getByText("Preference changes", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  expect(saved.confirmations).toHaveLength(2);
  expect(saved.evaluations).toHaveLength(2);
});

test("independent aftercare requires confirmation and supports tasks, dispute gate, operator and reminders", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "New demo case", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Rental preferences", exact: true }),
  ).toBeVisible();
  await navigate(page, "Aftercare services");
  await expect(
    page.getByRole("button", {
      name: "Confirm details and create aftercare case",
      exact: true,
    }),
  ).toBeDisabled();
  await page
    .getByRole("checkbox", {
      name: "I have checked and confirmed the lease, rooms, furniture, and sources above.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", {
      name: "Confirm details and create aftercare case",
      exact: true,
    })
    .click();
  await expect(
    page.getByText("Confirmed lease details", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Generate and confirm plan", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm plan", exact: true }).click();
  await expect(
    page.getByText("Clean Bedroom and record its condition", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Edit task", exact: true })
    .first()
    .click();
  await page
    .getByRole("combobox", { name: "Task status", exact: true })
    .click();
  await page.getByText("Completed", { exact: true }).last().click();
  await page.getByRole("button", { name: "Save task", exact: true }).click();
  await expect(
    page.getByText("Completed", { exact: true }).first(),
  ).toBeVisible();
  await page
    .getByLabel("Propose a new move-out date", { exact: true })
    .fill("2026-11-02");
  await page
    .getByRole("button", { name: "Submit date change proposal", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Submit proposal", exact: true })
    .click();
  await expect(
    page.getByText("A date change awaits confirmation", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Edit task", exact: true })
    .first()
    .click();
  await page
    .getByRole("dialog")
    .getByRole("textbox", { name: "Task details" })
    .fill("Synthetic completed task during pending proposal");
  await page.getByRole("button", { name: "Save task", exact: true }).click();
  await expect(
    page.getByText("Synthetic completed task during pending proposal", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("A date change awaits confirmation", { exact: true }),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Confirm date change", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Confirm date change", exact: true })
    .click();
  await expect(
    page.getByText("A date change awaits confirmation", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("tab", { name: "Bond follow-up", exact: true }).click();
  await page
    .getByRole("button", { name: "Create bond follow-up", exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "Confirm facts and activate follow-up",
      exact: true,
    })
    .click();
  await page
    .getByRole("textbox", { name: "Facts reported by the tenant" })
    .fill("Synthetic report: keys return arranged; no outcome yet.");
  await page
    .getByRole("button", { name: "Confirm and record", exact: true })
    .click();
  await expect(
    page.getByText("Awaiting outcome", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "Record new facts or deduction claims",
      exact: true,
    })
    .click();
  await page
    .getByRole("textbox", { name: "Facts reported by the tenant" })
    .fill("Synthetic tenant disputes a reported deduction.");
  await page
    .getByRole("checkbox", {
      name: "Include a reported deduction claim",
      exact: true,
    })
    .check();
  await page
    .getByRole("textbox", { name: "Reported deduction reason" })
    .fill("Synthetic wall mark");
  await page
    .getByRole("button", { name: "Confirm and record", exact: true })
    .click();
  await expect(
    page.getByText("Dispute or review restriction", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Prepare follow-up draft", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("link", { name: "Local demo operator", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Local demo operator", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Local operator key", { exact: true })
    .fill("qa-local-key");
  await page
    .getByLabel("Human review notes")
    .fill("Synthetic test evidence reviewed; no liability determination.");
  await page
    .getByRole("combobox", { name: "Bond review decision", exact: true })
    .click();
  await page
    .getByText("Checked and restrictions released", { exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "Record selected review decision",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Confirm record", exact: true })
    .click();
  await expect(
    page.getByText("This case has no unresolved bond review items.", {
      exact: true,
    }),
  ).toBeVisible();
  await navigate(page, "Aftercare services");
  await page.getByRole("tab", { name: "Bond follow-up", exact: true }).click();
  await page
    .getByRole("button", { name: "Prepare follow-up draft", exact: true })
    .click();
  await expect(
    page.getByText("Follow-up draft · Not sent", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Local reminders", exact: true }).click();
  await page
    .getByRole("switch", { name: "Enable local reminders", exact: true })
    .click();
  await expect(
    page.getByText("Reminders enabled", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Check due reminders", exact: true })
    .click();
  await expect(
    page.getByText("No delivered reminders.", { exact: true }),
  ).toHaveCount(0);
  await page.getByRole("tab", { name: "Bond follow-up", exact: true }).click();
  await page
    .getByLabel("Your confirmed outcome or reason for withdrawal", {
      exact: true,
    })
    .fill("Synthetic outcome explicitly confirmed by tenant.");
  await page
    .getByRole("button", {
      name: "Confirm outcome and close follow-up",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Confirm outcome and close", exact: true })
    .click();
  await expect(
    page.getByText("Outcome confirmed", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Confirmed lease details", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(artifactDir, "aftercare-desktop.png"),
  });
});

for (const width of [360, 768, 1440])
  test(`responsive recommendation and keyboard evidence drawer at ${width}px`, async ({
    page,
    request,
  }) => {
    const { c } = await seed(request);
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(`/cases/${c.case_id}/recommendations`);
    await expect(
      page.getByRole("heading", {
        name: "Housing recommendations",
        exact: true,
      }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    await page
      .locator("article.listing-row")
      .first()
      .getByRole("button", {
        name: "View recommendation evidence",
        exact: true,
      })
      .focus();
    await page.keyboard.press("Enter");
    await expect(
      page.getByText("Four-dimension scores and effective weights", {
        exact: true,
      }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await page.screenshot({
      path: resolve(artifactDir, `recommendations-${width}.png`),
    });
  });

test("contract conflict requires operator, prepares unsent questions and retains history after correction and revoke", async ({
  page,
  request,
}) => {
  const { c, e } = await seed(request);
  await request.post(`/api/v1/cases/${c.case_id}/selections`, {
    data: {
      request_id: `select-${crypto.randomUUID()}`,
      run_id: e.run_id,
      listing_id: "DEMO-006",
      confirmed: true,
    },
  });
  await page.goto(`/cases/${c.case_id}/contract`);
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
  const buffer = Buffer.from(
    readFileSync(
      resolve(root, "agent3/data/demo/agreements/selection-demo.txt"),
      "utf8",
    ).replace("$500", "$650"),
  );
  await page.locator("input[type=file]").setInputFiles({
    name: "rent-conflict.txt",
    mimeType: "text/plain",
    buffer,
  });
  await page
    .getByRole("checkbox", {
      name: "I confirm this is a synthetic demo contract.",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "Upload and review", exact: true })
    .click();
  await expect(
    page.getByText("Awaiting local demo operator", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Prepare question list", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("link", { name: "Local demo operator", exact: true })
    .click();
  await page
    .getByLabel("Local operator key", { exact: true })
    .fill("qa-local-key");
  await page
    .getByLabel("Human review notes")
    .fill("Synthetic rent difference reviewed; demonstration decision only.");
  await page
    .getByRole("button", { name: "Complete this human review", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Record human decision", exact: true })
    .click();
  await expect(
    page.getByText("This case has no contracts awaiting human review.", {
      exact: true,
    }),
  ).toBeVisible();
  await navigate(page, "Contract review");
  await page
    .getByRole("button", { name: "Prepare question list", exact: true })
    .click();
  await expect(
    page.getByText("Questions · Not sent", { exact: true }),
  ).toBeVisible();
  const saved = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  const reviewId = saved.reviews.at(-1).review_id;
  const packet = await (
    await request.get(`/api/v1/contract-reviews/${reviewId}/questions/export`)
  ).json();
  expect(packet.handoff_status).toBe("prepared_not_sent");
  expect(packet.questions.length).toBeGreaterThan(0);
  await page
    .getByRole("button", { name: "Correct extracted fields", exact: true })
    .click();
  await page
    .getByRole("spinbutton", { name: "Contract rent (AUD)" })
    .fill("500");
  await page
    .getByRole("button", { name: "Save as a new review version", exact: true })
    .click();
  await expect(
    page.getByText("Review version v2", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "This review has no findings. No additional questions will be generated.",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "View review history", exact: true })
    .click();
  await expect(
    page.getByText("Historical snapshots are read-only", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Revoke processing consent for this review",
      exact: true,
    })
    .click();
  await expect(
    page.getByText(
      "Review processing consent is inactive or the context has changed",
      { exact: true },
    ),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Correct extracted fields", exact: true }),
  ).toBeDisabled();
  await expect(page.locator("input[type=file]")).toHaveCount(0);
});

test("failed case navigation never exposes writes to the previous case", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "New demo case", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Rental preferences", exact: true }),
  ).toBeVisible();
  const caseA = page.url().split("/")[4];
  await page.getByRole("button", { name: "New case", exact: true }).click();
  await expect(page).not.toHaveURL(new RegExp(caseA));
  await expect(
    page.getByRole("heading", { name: "Rental preferences", exact: true }),
  ).toBeVisible();
  await page.route(`**/api/v1/cases/${caseA}`, (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "test_unavailable",
          message: "Temporary case read failure",
          request_id: "case-read-test",
        },
      }),
    }),
  );
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(caseA));
  await expect(
    page.getByText("Temporary case read failure", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save draft", exact: true }),
  ).toHaveCount(0);
});

test("failed report selection preserves clearly labeled prior data and disables mixed report actions", async ({
  page,
  request,
}) => {
  const { c, e } = await seed(request);
  let current = await (await request.get(`/api/v1/cases/${c.case_id}`)).json();
  const profile = structuredClone(current.draft.profile);
  profile.weights.cost = 0.9;
  current = await (
    await request.post(`/api/v1/cases/${c.case_id}/profile-drafts`, {
      data: { expected_revision: current.draft.revision, profile },
    })
  ).json();
  await request.post(`/api/v1/cases/${c.case_id}/profile-confirmations`, {
    data: {
      draft_revision: current.draft.revision,
      fingerprint: current.draft.fingerprint,
      review_token: current.agent1.review_token,
    },
  });
  await request.post(`/api/v1/cases/${c.case_id}/evaluations`, {
    data: {
      request_id: `evaluate-${crypto.randomUUID()}`,
      confirmation_version: 2,
    },
  });
  await page.goto(`/cases/${c.case_id}/recommendations`);
  await expect(page.locator("article.listing-row").first()).toBeVisible();
  await page.route(`**/api/v1/evaluations/${e.run_id}`, (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "test_unavailable",
          message: "Temporary report read failure",
          request_id: "report-read-test",
        },
      }),
    }),
  );
  await page
    .getByRole("combobox", {
      name: "Choose recommendation version",
      exact: true,
    })
    .click();
  await page.getByText("Preferences v1 · Report 1", { exact: true }).click();
  await expect(
    page.getByText("Could not load selected report", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("button", { name: "Select this listing", exact: true })
      .first(),
  ).toBeDisabled();
  await expect(
    page
      .getByRole("button", {
        name: "View recommendation evidence",
        exact: true,
      })
      .first(),
  ).toBeDisabled();
});

test("lost aftercare response preserves modal input and retry identity while reminder polling stays paused", async ({
  page,
  request,
}) => {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const config = await (await request.get("/api/v1/demo-config")).json();
  let version = 0;
  for (const [operation, payload] of [
    [
      "create",
      {
        tenancy: { ...config.tenancy_template, confirmed: true },
        evidence: config.capabilities.aftercare_evidence_template,
      },
    ],
    ["create_plan", { move_out_date: "2026-10-31", schedule_confirmed: true }],
    ["reminder_preferences", { enabled: true, follow_up_at: null }],
  ] as const) {
    const response = await request.post("/api/v1/aftercare/commands", {
      data: {
        case_id: c.case_id,
        request_id: `seed-${crypto.randomUUID()}`,
        expected_version: version,
        operation,
        payload,
      },
    });
    expect(response.ok()).toBeTruthy();
    version = (await response.json()).version;
  }
  const commands: Record<string, unknown>[] = [];
  let loseResponse = true;
  await page.route("**/api/v1/aftercare/commands", async (route) => {
    const body = route.request().postDataJSON();
    commands.push(body);
    if (body.operation === "edit_task" && loseResponse) {
      loseResponse = false;
      const result = await route.fetch();
      expect(result.ok()).toBeTruthy();
      await route.abort("failed");
    } else await route.continue();
  });
  await page.clock.install();
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await page
    .getByRole("button", { name: "Edit task", exact: true })
    .first()
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("textbox", { name: "Task details" })
    .fill("Synthetic task edited before response loss");
  await dialog.getByRole("button", { name: "Save task", exact: true }).click();
  await expect(
    dialog.getByText("Unable to complete this action", { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("textbox", { name: "Task details" }),
  ).toHaveValue("Synthetic task edited before response loss");
  await page.clock.fastForward(31_000);
  expect(commands.some((c) => c.operation === "poll_reminders")).toBeFalsy();
  await dialog
    .getByRole("button", { name: "Retry original action", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  await expect(
    page.getByText("Synthetic task edited before response loss", {
      exact: true,
    }),
  ).toBeVisible();
  const retries = commands.filter((c) => c.operation === "edit_task");
  expect(retries).toHaveLength(2);
  expect(retries[1]).toEqual(retries[0]);
});

async function seedAftercare(request: APIRequestContext) {
  const c = await (await request.post("/api/v1/cases", { data: {} })).json();
  const config = await (await request.get("/api/v1/demo-config")).json();
  let version = 0,
    m4id = "";
  for (const [operation, payload] of [
    [
      "create",
      {
        tenancy: { ...config.tenancy_template, confirmed: true },
        evidence: config.capabilities.aftercare_evidence_template,
      },
    ],
    ["create_plan", { move_out_date: "2026-10-31", schedule_confirmed: true }],
  ] as const) {
    const response = await request.post("/api/v1/aftercare/commands", {
      data: {
        case_id: c.case_id,
        request_id: `seed-${crypto.randomUUID()}`,
        expected_version: version,
        operation,
        payload,
      },
    });
    expect(response.ok()).toBeTruthy();
    const result = await response.json();
    version = result.version;
    m4id = result.case_id;
  }
  return { c, m4id };
}

test("cancelling a failed task edit cannot retry the previous task from a new edit session", async ({
  page,
  request,
}) => {
  const { c, m4id } = await seedAftercare(request);
  let fail = true;
  await page.route("**/api/v1/aftercare/commands", async (route) => {
    const body = route.request().postDataJSON();
    if (body.operation === "edit_task" && fail)
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "version_conflict",
            message: "Synthetic task conflict",
            request_id: body.request_id,
          },
        }),
      });
    else await route.continue();
  });
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await page
    .getByRole("button", { name: "Edit task", exact: true })
    .first()
    .click();
  let dialog = page.getByRole("dialog");
  await dialog
    .getByRole("textbox", { name: "Task details" })
    .fill("Unsubmitted first task edit");
  await dialog.getByRole("button", { name: "Save task", exact: true }).click();
  await expect(
    dialog.getByText("Synthetic task conflict", { exact: true }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "Cancel this edit", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  await page
    .getByRole("button", { name: "Edit task", exact: true })
    .nth(1)
    .click();
  dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("button", { name: "Retry original action", exact: true }),
  ).toHaveCount(0);
  await expect(
    dialog.getByRole("textbox", { name: "Task details" }),
  ).not.toHaveValue("Unsubmitted first task edit");
  fail = false;
  await dialog
    .getByRole("textbox", { name: "Task details" })
    .fill("Second task intentional edit");
  await dialog.getByRole("button", { name: "Save task", exact: true }).click();
  await expect(dialog).toBeHidden();
  const record = await (
    await request.get(`/api/v1/aftercare/cases/${m4id}`)
  ).json();
  expect(record.plan.tasks[0].title).not.toBe("Unsubmitted first task edit");
  expect(record.plan.tasks[1].title).toBe("Second task intentional edit");
});

test("an existing aftercare read failure offers recovery instead of creating a second tenancy", async ({
  page,
  request,
}) => {
  const { c, m4id } = await seedAftercare(request);
  const pattern = `**/api/v1/aftercare/cases/${m4id}`;
  await page.route(pattern, (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "service_failure",
          message: "Synthetic aftercare read unavailable",
          request_id: "read-existing",
        },
      }),
    }),
  );
  await page.goto(`/cases/${c.case_id}/aftercare`);
  await expect(
    page.getByText("Synthetic aftercare read unavailable", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Confirm details and create aftercare case",
      exact: true,
    }),
  ).toHaveCount(0);
  await page.unroute(pattern);
  await page
    .getByRole("button", { name: "Load latest state", exact: true })
    .click();
  await expect(
    page.getByText("Confirmed lease details", { exact: true }),
  ).toBeVisible();
});
