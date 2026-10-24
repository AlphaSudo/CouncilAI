// Inspect the actual local app without creating, continuing or retrying inference.
import { chromium } from "../apps/web/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";
import assert from "node:assert/strict";

const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 }, baseURL: "http://127.0.0.1:8000" });
  const errors = [], inferencePosts = [];
  page.on("pageerror", e => errors.push(e.message));
  page.on("request", r => {
    if (r.method() === "POST" && /^\/api\/chats(?:$|\/[^/]+\/(?:messages|control)$)/.test(new URL(r.url()).pathname)) inferencePosts.push(new URL(r.url()).pathname);
  });
  await page.goto("http://127.0.0.1:8000/");
  await page.getByLabel("Message the council").waitFor();
  assert.equal(await page.getByLabel("Council mode").count(), 0);
  assert.equal(await page.getByLabel("Review method").count(), 0);
  const health = await (await page.request.get("/api/health")).json();
  const boot = await (await page.request.get("/api/chats/bootstrap")).json();
  const models = boot.providers.direct_council.models.filter(m => m.configured).map(m => m.id);
  const preview = await (await page.request.get(`/api/chats/preview?provider=direct_council&models=${encodeURIComponent(models.join(","))}`)).json();
  assert.equal(health.version, "1.3.0");
  assert.equal(preview.review_protocol, "reviewed_v3");
  await page.screenshot({ path: "docs/validation/council-1.03-home-desktop.png", animations: "disabled" });
  const responsive = [];
  for (const width of [622, 390]) {
    await page.setViewportSize({ width, height: 844 });
    const fits = await page.locator(".council-main").evaluate(e => e.scrollWidth <= e.clientWidth + 1);
    assert.equal(fits, true);
    responsive.push({width, fits});
    await page.screenshot({ path: `docs/validation/council-1.03-home-${width}.png`, animations: "disabled" });
  }
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await page.goto("http://127.0.0.1:8000/?chat=chat_5d06a0522f694176");
  await page.getByLabel("Active council method").waitFor();
  assert.equal(await page.getByLabel("Active council method").innerText(), "Earlier discussion");
  assert.equal(await page.getByRole("button", {name: "Keep current method", exact: true}).count(), 0);
  const legacyMethod = await page.getByLabel("Active council method").innerText();
  const state = JSON.parse(await fs.readFile("data/unified-smoke.json", "utf8"));
  await page.goto(`http://127.0.0.1:8000/?chat=${state.chat_id}`);
  await page.getByLabel("Active council method").waitFor();
  assert.equal(await page.getByLabel("Active council method").innerText(), "Council");
  const liveStatus = await page.locator(".council-status").innerText();
  assert.equal(liveStatus.toLowerCase(), "partial answer");
  await page.locator('[data-phase="synthesis"]').last().scrollIntoViewIfNeeded();
  await page.screenshot({path: "docs/validation/council-1.03-live-mobile.png", animations: "disabled"});
  const theme = await page.locator(".council-app").evaluate(e => getComputedStyle(e).colorScheme);
  assert.equal(theme, "dark");
  assert.deepEqual(errors, []);
  assert.deepEqual(inferencePosts, []);
  const summary = {checked_at: new Date().toISOString(), application_version: health.version, display_name: "Council", selectors_removed: true,
    default_protocol: preview.review_protocol, planned_calls: preview.planned_calls, required_start: preview.required_start,
    legacy_method: legacyMethod, live_status: liveStatus, theme, responsive, page_errors: errors, inference_posts: inferencePosts};
  await fs.writeFile("docs/validation/council-1.03-ui.json", JSON.stringify(summary, null, 2) + "\n");
  console.log(JSON.stringify(summary, null, 2));
} finally { await browser.close(); }
