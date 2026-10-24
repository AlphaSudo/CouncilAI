// Read-only UI verification of the actual local app; never submits a council question.
import { chromium } from "../apps/web/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";
const state = JSON.parse(
  await fs.readFile(
    new URL("../data/scoped-smoke.json", import.meta.url),
    "utf8",
  ),
);
const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
const errors = [],
  inferencePosts = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("request", (r) => {
  if (r.method() === "POST" && new URL(r.url()).pathname === "/api/chats")
    inferencePosts.push(r.url());
});
await page.goto("http://127.0.0.1:8000/?chat=" + state.chat_id);
await page.locator('[data-phase="synthesis"]').last().waitFor();
const text = await page.locator('[data-phase="synthesis"]').last().innerText();
await page.locator('[data-phase="synthesis"]').last().scrollIntoViewIfNeeded();
await page.screenshot({
  path: "docs/validation/scoped-main-final.png",
  fullPage: true,
});
await page
  .getByRole("button", { name: "Claims & evidence", exact: true })
  .click();
const drawer = page.getByRole("dialog", { name: "Council claim inspector" });
await drawer.locator(".review-scoped-detail").waitFor();
await drawer.evaluate((e) => (e.scrollTop = 0));
await page.screenshot({ path: "docs/validation/scoped-main-desktop.png" });
await page.setViewportSize({ width: 390, height: 844 });
await drawer.evaluate((e) => (e.scrollTop = 0));
await page.screenshot({ path: "docs/validation/scoped-main-mobile.png" });
const mobileFits = await drawer.evaluate(
  (e) => e.scrollWidth <= e.clientWidth + 1,
);
await page.keyboard.press("Escape");
await page.goto("http://127.0.0.1:8000/?chat=chat_667561af9fa14d34");
await page
  .getByRole("button", { name: "Claims & evidence", exact: true })
  .click();
const legacyWorks =
  (await page.locator(".review-claim-list button").count()) === 8;
await page.goto("http://127.0.0.1:8000/");
await page.getByLabel("Council mode").selectOption("reviewed");
await page.getByLabel("Review method").selectOption("reviewed_v2");
await page
  .getByLabel("Message the council")
  .fill("Read-only setup check; this question will not be sent.");
const startEnabled = await page
  .getByRole("button", { name: "Start council", exact: true })
  .isEnabled();
await page.screenshot({
  path: "docs/validation/scoped-main-setup.png",
  fullPage: true,
});
const summary = {
  chat_id: state.chat_id,
  mobileFits,
  legacyWorks,
  startEnabled,
  pageErrors: errors,
  inferencePosts: inferencePosts.length,
  finalHasDirectAnswer: text.includes("Direct answer"),
  qualityEvidence: false,
};
await fs.writeFile(
  "docs/validation/scoped-main-ui.json",
  JSON.stringify(summary, null, 2),
);
await browser.close();
if (
  !mobileFits ||
  !legacyWorks ||
  !startEnabled ||
  errors.length ||
  inferencePosts.length
)
  throw new Error(JSON.stringify(summary));
console.log(JSON.stringify(summary));
