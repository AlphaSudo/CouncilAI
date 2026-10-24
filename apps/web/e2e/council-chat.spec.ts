import { test, expect } from "@playwright/test";
import fs from "node:fs";

// Detailed workflow regression checks run in Explain; default Simple is covered separately.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("zerowall.council.view", "explain"),
  );
});

test("Council front page shows independent answers, sequential debate, synthesis and follow-up", async ({
  page,
  context,
}) => {
  await context.clearCookies();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "New council", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Message the council")).toBeFocused();
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  await context.clearCookies();
  await page.reload();
  await expect(page.getByLabel("Message the council")).toBeFocused();
  await expect(page.getByLabel("Council provider")).toHaveValue("fixture");
  await expect(
    page.getByText("Scripted demo · no live models", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/chat-empty-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByLabel("Message the council")
    .fill(
      "How should a group of models compare conflicting engineering proposals?",
    );
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(
    page.locator('.council-message[data-phase="synthesis"]'),
  ).toHaveCount(1);
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  await expect(
    page.locator('.council-message[data-phase="opening"]'),
  ).toHaveCount(3);
  await expect(
    page.locator('.council-message[data-phase="repair"]'),
  ).toHaveCount(3);
  await expect(page.locator(".council-baseline summary")).toBeVisible();
  await page.locator(".council-baseline summary").click();
  await expect(page.locator(".council-baseline a")).toHaveCount(3);
  const openingModels = await page
    .locator('.council-message[data-phase="opening"]')
    .evaluateAll((elements) =>
      elements.map((element) => element.getAttribute("data-model")),
    );
  expect(new Set(openingModels).size).toBe(3);
  await page
    .getByLabel("Message the council")
    .fill("Now include an explicit test for reproducibility.");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.locator('.council-message[data-phase="synthesis"]'),
  ).toHaveCount(2);
  await expect(
    page.locator('.council-message[data-phase="intervention"]'),
  ).toHaveCount(1);
  await page
    .getByRole("button", { name: "Accept answer", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Accepted by you");
  const downloadEvent = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download transcript", exact: true })
    .click();
  const download = await downloadEvent;
  const output = "test-results/" + download.suggestedFilename();
  await download.saveAs(output);
  const transcript = fs.readFileSync(output, "utf8");
  expect(transcript).toContain("demo/analyst");
  expect(transcript).toContain("Final synthesis");
  await page.screenshot({
    path: "test-results/chat-transcript-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await expect(page.getByLabel("Message the council")).toBeVisible();
  await page.screenshot({
    path: "test-results/chat-transcript-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: /Research workspace/ }),
  ).toHaveCount(0);
  await page.goto("/?workspace=research");
  await expect(
    page.getByRole("navigation", { name: "Research views" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await page.getByRole("link", { name: "Council chat", exact: false }).click();
  await expect(
    page.getByRole("heading", { name: "New council", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("A connection retry goes straight to the prompt without token entry", async ({
  page,
}) => {
  let first = true;
  await page.route("**/api/session/local", async (route) => {
    if (first) {
      first = false;
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Temporary local connection failure" }),
      });
    } else {
      await route.continue();
    }
  });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Go to prompt", exact: true }),
  ).toBeVisible();
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  await page.getByRole("button", { name: "Go to prompt", exact: true }).click();
  await expect(page.getByLabel("Message the council")).toBeFocused();
  await expect(
    page.getByRole("heading", { name: "New council", exact: true }),
  ).toBeVisible();
});

test("Free quota is visible and insufficient allowance blocks a new council", async ({
  page,
}) => {
  let remaining = 0;
  // Explicitly exercise the retained legacy selector; production keeps it disabled.
  await page.route("**/api/chats/preview?**", (route) => {
    const params = new URL(route.request().url()).searchParams;
    const n = (params.get("models") || "").split(",").length;
    const planned = 2 * n + 4;
    return route.fulfill({
      json: {
        planned_calls: planned,
        required_start: planned + 3,
        blocked: false,
        role_names: {},
      },
    });
  });
  await page.route("**/api/chats/bootstrap", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.providers.openrouter_free.ready = true;
    body.providers.openrouter_free.enabled = true;
    body.providers.openrouter_free.configured = true;
    await route.fulfill({ response, json: body });
  });
  await page.route("**/api/chats/availability", (route) =>
    route.fulfill({
      json: {
        known: true,
        remaining,
        limit: 50,
        used: 50 - remaining,
      },
    }),
  );
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Compare two engineering proposals.");
  await expect(page.getByLabel("Council provider")).toHaveValue(
    "openrouter_free",
  );
  await expect(page.locator(".council-free-status")).toContainText("0 / 50");
  await expect(
    page.getByRole("button", { name: "Start council", exact: true }),
  ).toBeDisabled();
  remaining = 16;
  await page
    .getByRole("button", { name: "Refresh allowance", exact: true })
    .click();
  await expect(page.locator(".council-free-status")).toContainText("16 / 50");
  await expect(
    page.getByRole("button", { name: "Start council", exact: true }),
  ).toBeEnabled();
  remaining = 12;
  await page
    .getByRole("button", { name: "Refresh allowance", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Start council", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Use 2 models", exact: true }).click();
  await expect(page.getByLabel("Maximum discussion rounds")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Start council", exact: true }),
  ).toBeEnabled();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("Retry waits and reduced participation are visible rather than a generic stopped error", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Message the council")).toBeFocused();
  const response = await page.request.post("/api/chats", {
    headers: {
      "X-ZeroWall-Director": "1",
      "Idempotency-Key": crypto.randomUUID(),
    },
    data: {
      prompt: "Exercise visible waiting and participation states.",
      provider: "fixture",
      models: ["demo/analyst", "demo/critic", "demo/builder"],
      max_rounds: 1,
    },
  });
  const created = await response.json();
  const cid = created.chat.id;
  await expect
    .poll(
      async () =>
        (await page.request.get("/api/chats/" + cid).then((r) => r.json())).chat
          .status,
    )
    .toBe("completed");
  const saved = await page.request
    .get("/api/chats/" + cid)
    .then((r) => r.json());
  let state = "waiting";
  await page.route("**/api/chats/" + cid, async (route) => {
    const view = structuredClone(saved);
    if (state === "waiting") {
      view.chat.status = "waiting";
      view.chat.retry_wait = {
        name: "Demo Critic",
        model: "demo/critic",
        attempt: 1,
        maximum: 2,
        not_before: new Date(Date.now() + 90000).toISOString(),
      };
      view.chat.final_message_id = null;
    } else {
      view.chat.unavailable_members = {
        member_2: {
          name: "Demo Critic",
          model: "demo/critic",
          reason: "Simulated shared-pool outage",
        },
      };
      view.degraded = true;
      view.active_members = view.chat.participants.filter(
        (p) => p.id !== "member_2",
      );
      view.messages.at(-1).partial = true;
    }
    await route.fulfill({ json: view });
  });
  await page.goto("/?chat=" + cid);
  await expect(page.locator(".council-status")).toContainText("Retrying in");
  await expect(
    page.getByText(/Demo Critic is temporarily unavailable/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Pause", exact: true }),
  ).toBeVisible();
  state = "completed";
  await page.reload();
  await expect(page.locator(".council-status")).toHaveText("Partial answer");
  await expect(page.getByText(/2 of 3 members remain available/)).toBeVisible();
  // Participation can be partial while the saved public synthesis is complete.
  await expect(page.locator(`#${saved.chat.final_message_id}`)).toContainText(
    "Final synthesis",
  );
});
