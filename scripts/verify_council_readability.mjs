// Inspect the actual app without submitting, resuming or retrying any model request.
import { chromium } from "../apps/web/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";

const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
const errors = [],
  inferencePosts = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("request", (r) => {
  if (
    r.method() === "POST" &&
    /^\/api\/chats(?:$|\/[^/]+\/(?:messages|control)$)/.test(
      new URL(r.url()).pathname,
    )
  )
    inferencePosts.push(r.url());
});
await page.goto("http://127.0.0.1:8000/?chat=chat_5d06a0522f694176");
await page.locator('[data-phase="opening"]').first().waitFor();
const gemini = page.locator(
  '[data-phase="opening"][data-model*="gemini"] .council-message-content',
);
await gemini.locator("p").first().scrollIntoViewIfNeeded();
await page.screenshot({
  path: "docs/validation/council-dark-desktop.png",
  animations: "disabled",
});
const summary = {
  checked_at: new Date().toISOString(),
  chat_id: "chat_5d06a0522f694176",
  theme: await page
    .locator(".council-app")
    .evaluate((el) => ({
      background: getComputedStyle(el).backgroundColor,
      colorScheme: getComputedStyle(el).colorScheme,
    })),
  header: await page
    .locator(".council-header h1")
    .evaluate((el) => ({
      letterSpacing: getComputedStyle(el).letterSpacing,
      wordSpacing: getComputedStyle(el).wordSpacing,
      title: el.textContent,
    })),
  renderedMath: await page.locator(".katex").count(),
  structuredReplies: await page.locator(".council-original").count(),
  formulaErrors: await page.locator(".katex-error").allTextContents(),
  responsive: [],
  errors,
  inferencePosts,
};
for (const width of [622, 390]) {
  await page.setViewportSize({ width, height: 844 });
  await gemini.locator("p").first().scrollIntoViewIfNeeded();
  await page.screenshot({
    path: `docs/validation/council-dark-${width}.png`,
    animations: "disabled",
  });
  summary.responsive.push({
    width,
    fits: await page
      .locator(".council-main")
      .evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
  });
}
if (
  errors.length ||
  inferencePosts.length ||
  summary.theme.colorScheme !== "dark" ||
  summary.header.letterSpacing !== "normal" ||
  summary.responsive.some((v) => !v.fits)
)
  throw Error(JSON.stringify(summary));
await fs.writeFile(
  "docs/validation/council-readability-ui.json",
  JSON.stringify(summary, null, 2),
);
console.log(JSON.stringify(summary, null, 2));
await browser.close();
