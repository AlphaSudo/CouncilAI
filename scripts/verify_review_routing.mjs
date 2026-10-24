// Read-only verification against the running local application. No inference.
import { chromium } from "../apps/web/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";
import assert from "node:assert/strict";

const origin = "http://127.0.0.1:8000";
const chatId = "chat_5d06a0522f694176";
const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  const errors = [], inferencePosts = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => {
    if (request.method() === "POST" && /^\/api\/chats(?:$|\/[^/]+\/(?:messages|control)$)/.test(new URL(request.url()).pathname)) {
      inferencePosts.push(new URL(request.url()).pathname);
    }
  });
  await page.goto(origin);
  await page.getByLabel("Review method").waitFor();
  const defaults = {
    mode: await page.getByLabel("Council mode").inputValue(),
    review_protocol: await page.getByLabel("Review method").inputValue(),
  };
  assert.equal(defaults.mode, "reviewed");
  assert.equal(defaults.review_protocol, "reviewed_v2");
  await page.goto(`${origin}/?chat=${chatId}`);
  await page.getByLabel("Active council method").waitFor();
  const historicalMethod = await page.getByLabel("Active council method").innerText();
  assert.match(historicalMethod, /Discussion/);
  const pendingMethod = page.getByText("Next message: scoped review · 1.02", { exact: true });
  await pendingMethod.waitFor();
  const saved = await (await page.request.get(`${origin}/api/chats/${chatId}`)).json();
  assert.equal(saved.chat.protocol.version, "discussion_v1");
  assert.equal(saved.review_adoption.available, true);
  assert.equal(saved.review_adoption.required_start, 15);
  await page.screenshot({ path: "docs/validation/review-routing-desktop.png", animations: "disabled" });
  const responsive = [];
  for (const width of [622, 390]) {
    await page.setViewportSize({ width, height: 844 });
    const fits = await page.locator(".council-main").evaluate(element => element.scrollWidth <= element.clientWidth + 1);
    assert.equal(fits, true);
    responsive.push({ width, fits });
    await page.screenshot({ path: `docs/validation/review-routing-${width}.png`, animations: "disabled" });
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(inferencePosts, []);
  const health = await (await page.request.get(`${origin}/api/health`)).json();
  const summary = {
    checked_at: new Date().toISOString(),
    application_version: health.version,
    defaults,
    chat_id: chatId,
    historical_method: historicalMethod,
    saved_protocol: saved.chat.protocol.version,
    adoption_preflight: saved.review_adoption,
    next_message_method: await pendingMethod.innerText(),
    inference_posts: inferencePosts,
    page_errors: errors,
    responsive,
  };
  await fs.writeFile("docs/validation/review-routing-ui.json", JSON.stringify(summary, null, 2) + "\n");
  console.log(JSON.stringify(summary, null, 2));
} finally {
  await browser.close();
}
