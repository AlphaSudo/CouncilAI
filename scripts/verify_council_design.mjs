// Read-only inspection of the real local app. Provider inference routes are blocked.
import { chromium } from "../apps/web/node_modules/playwright/index.mjs";
import fs from "node:fs/promises";
import assert from "node:assert/strict";

const browser = await chromium.launch({ channel: "msedge", headless: true });
const errors = [],
  inferenceRequests = [],
  screenshots = [],
  layouts = [];
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 960 },
  });
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (
      request.method() === "POST" &&
      /^\/api\/chats(?:$|\/[^/]+\/(?:messages|control)$)/.test(path)
    )
      inferenceRequests.push(path);
  });
  await page.route("**/api/chats{,/**}", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      inferenceRequests.push(new URL(request.url()).pathname);
      await route.abort();
    } else await route.continue();
  });
  await page.goto("http://127.0.0.1:8000/");
  await page.getByLabel("Message the council").waitFor();
  await page
    .getByLabel("Message the council")
    .fill("Compare two approaches and help me choose.");
  for (const width of [1440, 622, 390]) {
    await page.setViewportSize({ width, height: width === 1440 ? 960 : 844 });
    for (const view of ["Simple", "Explain"]) {
      await page.getByRole("button", { name: view, exact: true }).click();
      assert.equal(
        await page.getByLabel("Message the council").inputValue(),
        "Compare two approaches and help me choose.",
      );
      const layout = await page.locator(".council-main").evaluate((main) => {
        const send = main
          .querySelector(".council-send")
          .getBoundingClientRect();
        return {
          fits: main.scrollWidth <= main.clientWidth + 1,
          composerOnscreen: send.top >= 0 && send.bottom <= innerHeight,
        };
      });
      assert.equal(layout.fits, true);
      assert.equal(
        layout.composerOnscreen,
        true,
        `${width}px ${view} composer must fit`,
      );
      layouts.push({ width, view, ...layout });
      const path = `docs/validation/council-design-${view.toLowerCase()}-${width}.png`;
      await page.screenshot({ path, animations: "disabled" });
      screenshots.push(path);
    }
  }
  const state = JSON.parse(
    await fs.readFile("data/unified-smoke.json", "utf8"),
  );
  await page.goto(`http://127.0.0.1:8000/?chat=${state.chat_id}`);
  await page.getByLabel("Message the council").waitFor();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 1440 ? 960 : 844 });
    for (const view of ["Simple", "Explain"]) {
      await page.getByRole("button", { name: view, exact: true }).click();
      const status = await page.locator(".council-status").innerText();
      assert.equal(status.toLowerCase(), "partial answer");
      await page
        .locator('[data-phase="synthesis"]')
        .last()
        .evaluate((element) => element.scrollIntoView({ block: "start" }));
      assert.equal(
        await page
          .locator(".council-main")
          .evaluate((main) => main.scrollWidth <= main.clientWidth + 1),
        true,
      );
      const path = `docs/validation/council-design-${view.toLowerCase()}-answer-${width}.png`;
      await page.screenshot({ path, animations: "disabled" });
      screenshots.push(path);
    }
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(inferenceRequests, []);
  const result = {
    checked_at: new Date().toISOString(),
    default_view: "simple",
    view_preference: "browser_local",
    layouts,
    same_chat: state.chat_id,
    partial_status_preserved: true,
    inference_requests: inferenceRequests,
    page_errors: errors,
    screenshots,
  };
  await fs.writeFile(
    "docs/validation/council-design-ui.json",
    JSON.stringify(result, null, 2) + "\n",
  );
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
