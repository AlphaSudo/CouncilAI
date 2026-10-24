import { test, expect } from "@playwright/test";
import path from "node:path";

test("OpenRouter is removed from new missions and paid mode remains locked", async ({
  page,
}) => {
  await page.goto("/?workspace=research");
  await page.locator(".mission-switch").click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Create a mission", exact: true })
    .click();
  const mode = page.getByLabel("Execution mode");
  await expect(mode.locator('option[value="openrouter_free"]')).toHaveCount(0);
  await expect(
    mode.locator('option[value="nebius_token_factory"]'),
  ).toHaveAttribute("disabled", "");
  await expect(mode).toHaveValue("fixture");
});

test("Director completes the local research loop and visits all research views", async ({
  page,
  context,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const response = await request.post("/api/session/local", {
    headers: { "X-ZeroWall-Director": "1" },
    data: {},
  });
  expect(response.ok()).toBeTruthy();
  await context.addCookies(await request.storageState().then((s) => s.cookies));
  await page.goto("/?workspace=research");
  await page.locator(".mission-switch").click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Create a mission", exact: true })
    .click();
  await page
    .getByLabel("Mission title")
    .fill("Browser acceptance / Research workflow");
  await page.getByRole("button", { name: "Create draft mission" }).click();
  await page.getByRole("button", { name: "Freeze mission" }).click();
  await page.getByRole("button", { name: "New round", exact: true }).click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Council round" })
    .click();
  await expect(
    page.getByRole("button", { name: "Reveal all four" }),
  ).toBeEnabled();
  await expect(
    page.getByText("Content stays private until the four-seat reveal barrier."),
  ).toHaveCount(4);
  await page.getByRole("button", { name: "Reveal all four" }).click();
  await expect(
    page.getByRole("heading", { name: "Predicted signature", exact: true }),
  ).toHaveCount(4);
  await page
    .getByRole("button", { name: "Cross-examine", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Cross-examination", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Conflict map", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Group challenges", exact: true })
    .click();
  await page.getByRole("dialog").getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Save challenge group" }).click();
  await expect(
    page.getByText("Mechanism and control challenges", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Edit group" }).click();
  await page.getByLabel("Group title").fill("Physical control objections");
  await page.getByRole("button", { name: "Save challenge group" }).click();
  await expect(
    page.getByText("Physical control objections", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Experiment board" })
    .click();
  await page.getByRole("button", { name: "Plan experiment" }).click();
  await page.getByRole("button", { name: "Save plan for approval" }).click();
  await page.getByRole("button", { name: "Approve & run" }).click();
  await expect(
    page.getByRole("button", { name: "Inspect evidence" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Inspect evidence" }).click();
  await expect(page.getByText("20.00", { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: "Raw artifact" }).click();
  await expect(
    page.getByRole("dialog", { name: "Artifact inspector" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Bottleneck map" })
    .click();
  await page
    .getByRole("button", { name: "Record reframe", exact: true })
    .click();
  await page
    .getByLabel("reason", { exact: true })
    .fill("The calculation cannot establish provider hardware behavior.");
  await page
    .getByLabel("interpretation", { exact: true })
    .fill(
      "Separate analytical bounds from actual hosted workflow measurements.",
    );
  await page
    .getByLabel("prediction comparison", { exact: true })
    .fill(
      "The 20 ms arithmetic prediction was reproduced; no physical performance was measured.",
    );
  await page
    .getByLabel("changed assumptions", { exact: true })
    .fill("Restrict the interpretation to the declared hypothetical transfer.");
  await page
    .getByLabel("alternative explanations", { exact: true })
    .fill(
      "Application framing and routing may dominate hosted workflow latency.",
    );
  await page
    .getByLabel("next action", { exact: true })
    .fill(
      "After billing verification, collect paired API cost and quality evidence.",
    );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Record reframe" })
    .click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Decision ledger" })
    .click();
  await page
    .getByRole("button", { name: "Draft decision", exact: true })
    .click();
  await page
    .getByLabel("Bounded conclusion")
    .fill(
      "The declared transfer has a 20 ms lower bound; the hosted workflow remains inconclusive.",
    );
  await page
    .getByLabel("reasons · one per line", { exact: true })
    .fill(
      "A deterministic calculation supplies an arithmetic constraint only.",
    );
  await page
    .getByLabel("assumptions · one per line", { exact: true })
    .fill("Bandwidth and transfer size are supplied hypothetical inputs.");
  await page
    .getByLabel("reopen triggers · one per line", { exact: true })
    .fill("New measured workflow evidence or revised transfer assumptions.");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Draft decision", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Approve inconclusive report" })
    .click();
  await expect(page.getByText("approved · inconclusive")).toBeVisible();
  for (const view of [
    "Mission room",
    "Step graph",
    "Council round",
    "Conflict map",
    "Experiment board",
    "Evidence",
    "Bottleneck map",
    "Decision ledger",
    "Research report",
  ]) {
    await page
      .getByRole("navigation")
      .getByRole("button", { name: view, exact: true })
      .click();
    await expect(page.locator("main.workspace-content")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
  }
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download evidence pack" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/zerowall-.*\.zip/);
  await download.saveAs(path.resolve("test-results/browser-evidence.zip"));
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Mission room", exact: true })
    .click();
  await page.screenshot({
    path: "test-results/mission-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "Open navigation" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/mission-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Council round", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Four seats. One shared context." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/council-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
