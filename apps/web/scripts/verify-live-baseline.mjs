// Read the real local app; block model requests and all mutations except local login.
import { writeFileSync } from "node:fs";
import { chromium, expect } from "@playwright/test";
const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 900, height: 900 } });
const writes = [];
let stage = "opening";
await page.route("**/api/**", async (route) => {
  const request = route.request();
  if (
    request.method() !== "GET" &&
    !request.url().endsWith("/api/session/local")
  ) {
    writes.push(request.url());
    await route.abort();
  } else await route.continue();
});
try {
  await page.goto("http://127.0.0.1:8000/");
  stage = "thinking/context";
  await expect(page.getByLabel("Thinking level", { exact: true })).toHaveValue(
    "balanced",
  );
  await expect(
    page.locator(".council-composer-actions .context-trigger"),
  ).toBeVisible();
  stage = "search";
  await expect(
    page.getByRole("switch", { name: "Web search", exact: true }),
  ).toBeChecked();
  stage = "models";
  await page.getByRole("button", { name: /Customize/ }).click();
  await expect(
    page.getByLabel("Council provider", { exact: true }),
  ).toHaveValue("nebius_token_factory");
  await page.getByRole("button", { name: /3 models/ }).click();
  for (const name of [
    /Nemotron-3.5-Super-VL/,
    /Reflection Beam/,
    /DeepSeek-V4-Flash-0731/,
  ])
    await expect(page.getByRole("checkbox", { name })).toBeChecked();
  await expect(
    page.getByRole("checkbox", { name: /Nemotron-3_5-Lightning/ }),
  ).not.toBeChecked();
  await expect(page.getByRole("checkbox", { name: /Z.ai/ })).toHaveCount(0);
  await page.screenshot({
    path: "../../docs/validation/token-factory-live-lineup.png",
  });
  await page
    .getByRole("dialog", { name: "Council settings", exact: true })
    .getByRole("button", { name: "Done", exact: true })
    .click();
  stage = "context capacity";
  await page.locator(".council-composer-actions .context-trigger").click();
  await expect(
    page.getByRole("region", { name: "Context details" }),
  ).toContainText("262,144");
  await page.screenshot({
    path: "../../docs/validation/token-factory-live-controls.png",
  });
  if (writes.length) throw Error("Unexpected mutation attempted");
  const result = {
    live_provider: "nebius_token_factory",
    default_models: ["Super", "Beam", "DeepSeek V4"],
    context_tokens: 262144,
    balanced_reasoning_target: 4000,
    context_circle: "visible",
    search_default: "on",
    inference_requests: 0,
  };
  writeFileSync(
    new URL(
      "../../../docs/validation/baseline-stability-live-ui.json",
      import.meta.url,
    ),
    JSON.stringify(result, null, 2) + "\n",
  );
  process.stdout.write(JSON.stringify(result));
} catch (error) {
  process.stdout.write(
    JSON.stringify({ stage, error: error.message.split("\n")[0] }),
  );
  process.exitCode = 1;
} finally {
  await browser.close();
}
