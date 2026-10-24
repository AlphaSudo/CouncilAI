import { test, expect } from "@playwright/test";

// Detailed workflow regression checks run in Explain; default Simple is covered separately.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("zerowall.council.view", "explain"),
  );
});

test("The normal entry point has one Council and runs the current claim review", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Council mode")).toHaveCount(0);
  await expect(page.getByLabel("Review method")).toHaveCount(0);
  await page
    .getByLabel("Message the council")
    .fill("Compare two generic designs under explicit constraints.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  await expect(page.getByLabel("Active council method")).toHaveText("Council");
  for (const phase of [
    "opening",
    "extraction",
    "scrutiny",
    "repair",
    "recheck",
    "synthesis",
  ]) {
    await expect(page.locator(`[data-phase="${phase}"]`).first()).toBeVisible();
  }
  await expect(page.locator('[data-phase="debate"]')).toHaveCount(0);
  await page
    .getByRole("button", { name: "Claims & evidence", exact: true })
    .click();
  await expect(
    page
      .getByRole("dialog", { name: "Council claim inspector" })
      .locator(".review-scoped-detail"),
  ).toBeVisible();
});

test("A current Council follow-up preserves an earlier discussion in the same conversation", async ({
  page,
}) => {
  await page.goto("/");
  // Historical creation is an API fixture; no old-mode menu is exposed.
  await expect(page.getByLabel("Message the council")).toBeFocused();
  const response = await page.request.post("/api/chats", {
    headers: {
      "X-ZeroWall-Director": "1",
      "Idempotency-Key": crypto.randomUUID(),
    },
    data: {
      prompt:
        "Compare generic engineering approaches without inventing evidence.",
      provider: "fixture",
      models: ["demo/analyst", "demo/critic", "demo/builder"],
      mode: "discussion",
      max_rounds: 1,
    },
  });
  expect(response.ok()).toBe(true);
  const initial = await response.json();
  await page.goto(`/?chat=${initial.chat.id}`);
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const url = page.url();
  await expect(page.getByLabel("Active council method")).toHaveText(
    "Earlier discussion",
  );
  const oldOpening = await page
    .locator('[data-phase="opening"]')
    .first()
    .getAttribute("id");
  await expect(
    page.getByText("Continue with the Council", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Message the council")
    .fill(
      "Now review the strongest distinct approaches under the same constraints.",
    );
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.locator('[data-phase="synthesis"]')).toHaveCount(2);
  await expect(page.getByLabel("Active council method")).toHaveText("Council");
  expect(page.url()).toBe(url);
  await expect(page.locator("#" + oldOpening)).toHaveCount(1);
  await expect(page.locator('[data-phase="opening"]')).toHaveCount(6);
  await expect(page.locator('[data-phase="protocol_transition"]')).toHaveCount(
    1,
  );
  await expect(page.locator('[data-phase="extraction"]')).toHaveCount(1);
  await expect(
    page
      .getByText("Earlier answers keep their original review status.", {
        exact: false,
      })
      .first(),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page
      .locator(".council-main")
      .evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
  ).toBe(true);
});

test("Council explains an answer and reviews a selected challenge without restarting the chat", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Compare generic design choices under explicit constraints.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const url = page.url();
  await expect(page.getByLabel("Council progress")).toBeVisible();
  await page
    .getByRole("button", { name: "Explain this answer", exact: true })
    .click();
  await expect(page.locator('[data-phase="synthesis"]')).toHaveCount(2);
  await expect(page.locator('[data-phase="repair"]')).toHaveCount(3);
  await expect(page.locator('[data-phase="synthesis"]').last()).toContainText(
    "No new checks were performed",
  );
  await page
    .getByRole("button", { name: "Claims & evidence", exact: true })
    .click();
  const drawer = page.getByRole("dialog", { name: "Council claim inspector" });
  await drawer.getByText("Challenge this claim", { exact: true }).click();
  await drawer
    .getByLabel("Challenge to selected claim")
    .fill("Does this assertion remain useful within the stated boundary?");
  await drawer
    .getByRole("button", { name: "Review this challenge", exact: true })
    .click();
  await expect(drawer).toHaveCount(0);
  await expect(page.locator('[data-phase="synthesis"]')).toHaveCount(3);
  await expect(page.locator('[data-phase="opening"]')).toHaveCount(3);
  await expect(page.locator('[data-phase="repair"]')).toHaveCount(4);
  expect(page.url()).toBe(url);
});
