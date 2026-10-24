import { test, expect } from "@playwright/test";

test.afterEach(async ({ page }) => {
  // Drain mocked status fetches before the next test starts; the app polls active chats.
  await page.unrouteAll({ behavior: "wait" });
});

test("Simple is the default; switching views preserves the draft and makes no inference request", async ({
  page,
}) => {
  const inference: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /\/api\/chats(?:$|\/[^/]+\/(messages|control)$)/.test(
        new URL(request.url()).pathname,
      )
    )
      inference.push(request.url());
  });
  await page.goto("/");
  const composer = page.getByLabel("Message the council");
  await expect(composer).toBeFocused();
  await expect(
    page.getByRole("button", { name: "Simple", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("heading", { name: "Ask the council.", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Council provider")).toBeHidden();
  await expect(page.getByLabel("Council mode")).toHaveCount(0);
  await expect(page.getByLabel("Review method")).toHaveCount(0);
  await composer.fill("Keep this draft while I inspect the interface.");
  await page.getByRole("button", { name: "Customize", exact: true }).click();
  await expect(page.getByLabel("Council provider")).toBeVisible();
  await page.getByText("Answer requirements", { exact: false }).click();
  await page
    .getByLabel("Deliverable", { exact: true })
    .fill("A concise, qualified recommendation.");
  const settings = page.getByRole("dialog", {
    name: "Council settings",
    exact: true,
  });
  await expect(settings).toBeVisible();
  await settings.getByRole("button", { name: "Done", exact: true }).click();
  await expect(settings).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "Customize", exact: true }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await expect(page.locator(".council-app")).toHaveAttribute(
    "data-view",
    "explain",
  );
  await expect(composer).toHaveValue(
    "Keep this draft while I inspect the interface.",
  );
  await expect(page.getByLabel("Deliverable", { exact: true })).toHaveValue(
    "A concise, qualified recommendation.",
  );
  await expect(
    page.getByText("Think independently", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Simple", exact: true }).click();
  await expect(composer).toHaveValue(
    "Keep this draft while I inspect the interface.",
  );
  await page.getByRole("button", { name: "Customize", exact: true }).click();
  await expect(page.getByLabel("Deliverable", { exact: true })).toHaveValue(
    "A concise, qualified recommendation.",
  );
  await page.keyboard.press("Escape");
  await expect(settings).not.toBeVisible();
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Explain", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  expect(inference).toEqual([]);
});

test("The compact discussion and full inspection view share the same saved council", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Compare two generic software designs under explicit constraints.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const url = page.url();
  const count = await page.locator(".council-message").count();
  await expect(
    page.locator('.council-message[data-phase="synthesis"]'),
  ).toBeVisible();
  await expect(page.locator('[data-phase="opening"]').first()).toBeHidden();
  await expect(page.getByLabel("Council progress")).toHaveCount(0);
  await page.locator(".council-process-group > summary").first().click();
  await expect(page.locator('[data-phase="opening"]').first()).toBeVisible();
  await page.getByLabel("Message the council").fill("Keep my follow-up draft.");
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST")
      requests.push(new URL(request.url()).pathname);
  });
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await expect(page.getByLabel("Council progress")).toBeVisible();
  await expect(page.locator('[data-phase="repair"]').first()).toBeVisible();
  await expect(page.locator(".council-model-id").first()).toBeVisible();
  const diagnostic = page.locator(".council-desktop-diagnostics");
  await expect(
    diagnostic.getByText("Attempts so far", { exact: true }),
  ).toBeVisible();
  await diagnostic.getByText("Execution snapshot", { exact: true }).click();
  await expect(diagnostic.locator("pre")).toContainText(
    '"protocol": "reviewed_v4"',
  );
  await expect(diagnostic.locator("pre")).toContainText(
    new URL(url).searchParams.get("chat")!,
  );
  await page.screenshot({
    path: "test-results/council-explain-desktop.png",
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Simple", exact: true }).click();
  await expect(page.getByLabel("Message the council")).toHaveValue(
    "Keep my follow-up draft.",
  );
  expect(page.url()).toBe(url);
  await expect(page.locator(".council-message")).toHaveCount(count);
  await expect(page.locator(".review-toolbar")).toHaveCount(0);
  await expect(page.getByText("Answer details", { exact: true })).toHaveCount(
    0,
  );
  const why = page.getByRole("button", {
    name: "Why this answer?",
    exact: true,
  });
  for (const width of [622, 390, 320, 1440]) {
    await page.setViewportSize({ width, height: 668 });
    const strip = (await page
      .locator(".council-research-strip")
      .boundingBox())!;
    const source = (await page
      .locator(".council-sources-trigger")
      .boundingBox())!;
    const button = (await why.boundingBox())!;
    expect(
      Math.abs(source.y + source.height / 2 - button.y - button.height / 2),
    ).toBeLessThanOrEqual(1);
    expect(button.x).toBeGreaterThan(source.x + source.width);
    expect(button.x + button.width).toBeLessThanOrEqual(strip.x + strip.width);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.locator(".conversation-usage > summary").click();
  await expect(page.locator(".conversation-usage")).toHaveAttribute("open", "");
  const expanded = (await page.locator(".conversation-usage").boundingBox())!;
  const action = (await why.boundingBox())!;
  expect(expanded.y).toBeGreaterThanOrEqual(action.y + action.height);
  await page.locator(".conversation-usage > summary").click();
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.screenshot({
    path: "test-results/council-simple-answer-desktop.png",
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Why this answer?", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Council claim inspector" }),
  ).toBeVisible();
  expect(requests).toEqual([]);
});

test("A source link reveals its saved reply inside the compact discussion", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill(
      "Compare generic software approaches and preserve source references.",
    );
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const cid = new URL(page.url()).searchParams.get("chat");
  const sourceId = await page
    .locator('[data-phase="opening"]')
    .first()
    .getAttribute("id");
  await page.route(`**/api/chats/${cid}`, async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.messages.find(
      (message: { phase: string }) => message.phase === "synthesis",
    ).content = `Read the [original answer](#${sourceId}) for its assumptions.`;
    await route.fulfill({ response, json: data });
  });
  await page.reload();
  await expect(page.locator(`#${sourceId}`)).toBeHidden();
  await page
    .getByRole("link", { name: "original answer", exact: true })
    .click();
  await expect(page.locator(`#${sourceId}`)).toBeVisible();
  await expect(page.locator(".council-process-group").first()).toHaveAttribute(
    "open",
    "",
  );
});

test("Both views fit mobile and Explain keeps diagnostics keyboard accessible", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  for (const width of [390, 622, 1440]) {
    await page.setViewportSize({ width, height: 844 });
    for (const view of ["Simple", "Explain"]) {
      await page.getByRole("button", { name: view, exact: true }).click();
      await expect(page.getByLabel("Message the council")).toBeVisible();
      await page.locator(".council-send").scrollIntoViewIfNeeded();
      const sendBounds = await page.locator(".council-send").boundingBox();
      expect(sendBounds!.y + sendBounds!.height).toBeLessThanOrEqual(844);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      expect(
        await page
          .locator(".council-main")
          .evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
      ).toBe(true);
      if (width === 390 && view === "Explain") {
        const summary = page.locator(".council-mobile-diagnostics > summary");
        await summary.focus();
        await page.keyboard.press("Enter");
        await expect(
          page.locator(".council-mobile-diagnostics .council-diagnostics"),
        ).toBeVisible();
        await page
          .locator(
            ".council-mobile-diagnostics .council-execution-snapshot > summary",
          )
          .click();
        await expect(
          page.locator(".council-mobile-diagnostics pre"),
        ).toContainText('"status": "not_started"');
        await summary.click();
      }
      await page.screenshot({
        path: `test-results/council-${view.toLowerCase()}-home-${width}.png`,
        animations: "disabled",
      });
    }
  }
  await expect(page.locator(".council-empty")).toHaveCSS(
    "animation-name",
    "none",
  );
  expect(errors).toEqual([]);
});

test("Partial participation and stale-answer warnings survive Simple view", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Compare generic approaches without claiming measurements.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const cid = new URL(page.url()).searchParams.get("chat");
  await page.route(`**/api/chats/${cid}`, async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.chat.requested_finish = true;
    data.degraded = true;
    data.review.synthesis_stale = true;
    data.chat.unavailable_members = { member_2: { name: "Demo Critic" } };
    data.participation_notices = [
      {
        model: "demo/critic",
        name: "Demo Critic",
        phase: "repair",
        reason: "Provider limit reached.",
        kind: "provider_unavailable",
      },
    ];
    await route.fulfill({ response, json: data });
  });
  await page.reload();
  await expect(page.locator(".council-status")).toHaveText("Partial answer");
  await expect(
    page.getByText("Published answer needs updating", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Participation record:", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("Synthetic demo.", { exact: false }),
  ).toBeVisible();
});

test("A blocked allowance is visible without opening advanced setup", async ({
  page,
}) => {
  await page.route("**/api/chats/preview?**", (route) =>
    route.fulfill({
      json: {
        planned_calls: 10,
        required_start: 13,
        blocked: true,
        reason:
          "The daily allowance is exhausted. Your existing chats are saved.",
        role_names: {},
      },
    }),
  );
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("A question that must wait for allowance.");
  await expect(
    page.getByRole("button", { name: "Start council", exact: true }),
  ).toBeDisabled();
  await expect(page.getByRole("alert")).toContainText(
    "daily allowance is exhausted",
  );
  await page.getByRole("button", { name: "Review setup", exact: true }).click();
  await expect(page.getByLabel("Council provider")).toBeVisible();
});

test("A long conversation history leaves the home composer reachable within the page", async ({
  page,
}) => {
  await page.route("**/api/chats/bootstrap", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.chats = Array.from({ length: 100 }, (_, index) => ({
      id: `history_${index}`,
      title: `Saved conversation ${index}: compare a detailed project plan and its alternatives`,
      status: "completed",
    }));
    await route.fulfill({ response, json: data });
  });
  await page.goto("/");
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 844 });
    for (const view of ["Simple", "Explain"]) {
      await page.getByRole("button", { name: view, exact: true }).click();
      await page.locator(".council-send").scrollIntoViewIfNeeded();
      const bounds = await page.locator(".council-send").boundingBox();
      expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(844);
      expect(
        await page
          .locator(".council-main")
          .evaluate((element) => element.getBoundingClientRect().height),
      ).toBeLessThanOrEqual(844);
    }
  }
});

test("Unavailable browser storage does not prevent changing the view", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => {
      throw new Error("Storage unavailable");
    };
    Storage.prototype.setItem = () => {
      throw new Error("Storage unavailable");
    };
  });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Simple", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Explain", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Message the council")).toBeVisible();
});
