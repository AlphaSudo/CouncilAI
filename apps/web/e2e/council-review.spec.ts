import { test, expect } from "@playwright/test";

// Detailed workflow regression checks run in Explain; default Simple is covered separately.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("zerowall.council.view", "explain"),
  );
});

test("Reported-observation warnings render beside their source and in the inspector", async ({
  page,
}) => {
  await page.route("**/api/chats/*", async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const response = await route.fetch();
    const body = await response.json();
    const opening = body.messages?.find((m: any) => m.phase === "opening");
    if (opening && ["reviewed_v3", "reviewed_v4"].includes(body.review?.contract.protocol_version)) {
      body.review.observations = [
        {
          id: "synthetic-ui-warning",
          source_message_id: opening.id,
          text: "I tested this in three seconds.",
          classification: "unsupported_self_report",
          origin: "synthetic_snapshot_fixture",
          reason: "Synthetic server-snapshot fixture for warning presentation.",
        },
      ];
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill(
      "Demonstrate the provenance warning renderer with scripted participants.",
    );
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(
    page.getByLabel("Reported observation warning").first(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Inspect provenance", exact: true })
    .first()
    .click();
  const drawer = page.getByRole("dialog", { name: "Council claim inspector" });
  await drawer
    .getByText("Reported observations & provenance", { exact: false })
    .click();
  await expect(
    drawer.getByText("I tested this in three seconds.", { exact: true }),
  ).toBeVisible();
  await expect(
    drawer.getByText("Synthetic server-snapshot fixture", { exact: false }),
  ).toBeVisible();
});

test("Reviewed council exposes claims, repairs, sources and portable evidence on desktop and mobile", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/");
  await expect(page.getByLabel("Message the council")).toBeFocused();
  await expect(
    page
      .getByLabel("Council provider")
      .locator('option[value="openrouter_free"]'),
  ).toHaveCount(0);
  await page.getByText("Answer requirements", { exact: false }).click();
  await page.getByLabel("Review hard constraints").fill("No paid services");
  await page
    .getByLabel("Message the council")
    .fill("Compare two software designs under a zero-spend constraint.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  for (const [phase, count] of [
    ["opening", 3],
    ["extraction", 1],
    ["scrutiny", 1],
    ["repair", 3],
    ["recheck", 1],
    ["synthesis", 1],
  ] as const) {
    await expect(
      page.locator(`.council-message[data-phase="${phase}"]`),
    ).toHaveCount(count);
  }
  await page.getByRole("button", { name: "Claims & evidence" }).click();
  const drawer = page.getByRole("dialog", { name: "Council claim inspector" });
  await expect(drawer).toBeVisible();
  await expect(drawer.locator(".review-claim-list button")).toHaveCount(3);
  await expect(drawer.locator(".review-state")).toContainText("Conditional");
  await drawer
    .getByText("Replies, repairs & earlier revisions", { exact: true })
    .click();
  await expect(drawer.getByText("Revision 1", { exact: true })).toBeVisible();
  await expect(drawer.getByText("Revision 2", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "test-results/review-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await drawer
    .getByText("Attach a source or existing tool result", { exact: true })
    .click();
  await drawer
    .getByLabel("Source excerpt", { exact: true })
    .fill(
      "A scripted workflow demonstration does not establish answer quality.",
    );
  await drawer
    .getByLabel("Source provenance", { exact: true })
    .fill("Director-authored scoped example");
  await drawer
    .getByLabel("Source assessment", { exact: true })
    .fill(
      "I checked that this example concerns only the narrow demonstration claim.",
    );
  await drawer
    .getByRole("button", { name: "Attach evidence", exact: true })
    .click();
  await expect(
    drawer.getByText("The published answer predates review changes.", {
      exact: false,
    }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await drawer
    .getByRole("button", { name: "Download review pack", exact: true })
    .click();
  expect((await download).suggestedFilename()).toMatch(
    /zerowall-review-.*\.zip/,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "test-results/review-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  expect(
    await drawer.evaluate((e) => e.scrollWidth <= e.clientWidth + 1),
  ).toBeTruthy();
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Claims & evidence" }),
  ).toBeFocused();
  expect(errors).toEqual([]);
});

test("Four-provider setup previews the reviewed call budget and keeps secrets server-side", async ({
  page,
}) => {
  await page.route("**/api/chats/bootstrap", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.providers.direct_council.ready = true;
    body.providers.direct_council.configured = true;
    body.providers.direct_council.free_access_confirmed = true;
    body.providers.direct_council.models.forEach(
      (model: any) => (model.configured = true),
    );
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await expect(page.getByLabel("Council provider")).toHaveValue(
    "direct_council",
  );
  await expect(page.locator(".council-direct-status")).toContainText(
    "12 planned calls + 3 shared retry attempts",
  );
  await page.getByRole("button", { name: "4 models" }).click();
  await expect(
    page.locator(".council-model-choices input:checked"),
  ).toHaveCount(4);
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("OPENROUTER_API_KEY");
});

test("Scoped review separates resolution, evidence and risk and preserves legacy inspection", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByLabel("Review method")).toHaveCount(0);
  await page
    .getByLabel("Message the council")
    .fill(
      "Compare two generic designs while keeping the conditions and evidence separate.",
    );
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const final = page.locator('[data-phase="synthesis"]');
  await expect(final).toContainText("This scripted council demonstrates");
  await expect(final).not.toContainText('"blocks"');
  await expect(final).not.toContainText("Unresolved or incomplete review");
  await page.getByRole("button", { name: "Claims & evidence" }).click();
  const drawer = page.getByRole("dialog", { name: "Council claim inspector" });
  await expect(
    drawer.getByText("complete as assessed", { exact: true }),
  ).toBeVisible();
  await expect(
    drawer.getByText("model reasoning only", { exact: true }),
  ).toBeVisible();
  await expect(
    drawer.getByText("Ordinary residual risks", { exact: true }),
  ).toBeVisible();
  await drawer
    .getByText("Original passages & normalized assertion", { exact: true })
    .click();
  await expect(
    drawer.getByText("Original characters", { exact: false }).first(),
  ).toBeVisible();
  await drawer.getByText("Claim groups", { exact: false }).click();
  await expect(
    drawer.getByText("split or stale after revision", { exact: false }),
  ).toBeVisible();
  await drawer
    .getByText("Attach a source or existing tool result", { exact: true })
    .click();
  await drawer
    .getByLabel("Source excerpt", { exact: true })
    .fill(
      "This example is a scripted workflow demonstration, not evidence of answer quality.",
    );
  await drawer
    .getByLabel("Source provenance", { exact: true })
    .fill("Synthetic browser-test source");
  await drawer
    .getByLabel("Source assessment", { exact: true })
    .fill(
      "I checked the narrow demonstration claim against the supplied example.",
    );
  await drawer
    .getByLabel("Supported evidence scope")
    .fill("Synthetic workflow demonstration only");
  await drawer.getByLabel("Evidence scope coverage").selectOption("partial");
  await drawer
    .getByRole("button", { name: "Attach evidence", exact: true })
    .click();
  await expect(
    drawer.getByText("partially assessed scope", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/scoped-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "test-results/scoped-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  expect(
    await drawer.evaluate((e) => e.scrollWidth <= e.clientWidth + 1),
  ).toBeTruthy();
  const download = page.waitForEvent("download");
  await drawer
    .getByRole("button", { name: "Download review pack", exact: true })
    .click();
  expect((await download).suggestedFilename()).toMatch(
    /zerowall-review-.*\.zip/,
  );
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Claims & evidence" }),
  ).toBeFocused();
  expect(errors).toEqual([]);
});
