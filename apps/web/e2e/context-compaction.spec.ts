import { test, expect, type Page } from "@playwright/test";

async function contextDemo(page: Page, measured = true) {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Compare generic engineering approaches.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  let mode = "adaptive";
  const writes: string[] = [];
  await page.route(
    /\/api\/chats\/chat_[^/?]+\/context\/compact$/,
    async (route) => {
      writes.push(route.request().url());
      mode = route.request().postDataJSON().mode;
      await route.fulfill({ json: { mode, supported: true } });
    },
  );
  await page.route(/\/api\/chats\/chat_[^/?]+$/, async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.chat.provider = "nebius_token_factory";
    const latest = {
      call_id: "offline_context_receipt",
      model: "nvidia/Nemotron-3.5-Super-VL",
      state: "completed",
      input_tokens: 104858,
      capacity_tokens: 262144,
      remaining_tokens: 157286,
      percent: 40,
      reserved_output_tokens: 32768,
      provider_reported_input_tokens: 100000,
    };
    data.context_status = {
      supported: true,
      mode,
      capacity_tokens: 262144,
      automatic_threshold_percent: 80,
      latest: measured ? latest : null,
      models: measured
        ? [
            latest,
            {
              ...latest,
              model: "zai-org/GLM-5.3-Flash",
              input_tokens: 52429,
              percent: 20,
              provider_reported_input_tokens: null,
            },
          ]
        : [],
      last_compaction: measured
        ? { saved_input_tokens: 12000, model: latest.model }
        : null,
      compactions: measured ? 1 : 0,
    };
    await route.fulfill({ response, json: data });
  });
  await page.reload();
  return writes;
}

test("Context ring explains per-request usage and queues compaction without sending a council turn", async ({
  page,
}) => {
  const writes = await contextDemo(page);
  const ring = page.getByRole("button", { name: /Context usage, 40%/ });
  await expect(ring).toBeVisible();
  await ring.click();
  const panel = page.getByRole("region", { name: "Context details" });
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("104,858");
  await expect(panel).toContainText("262,144");
  await expect(panel).toContainText("32,768 tokens were reserved");
  await expect(panel).toContainText(
    "Last compaction saved 12,000 input tokens",
  );
  await expect(panel.getByText("Per-model measurements")).toHaveCount(0);
  await panel
    .getByRole("button", { name: "Compact context", exact: true })
    .click();
  await expect(panel.getByRole("status")).toContainText(
    "No extra model call was made",
  );
  await expect(
    panel.getByRole("button", { name: "Ready for next request" }),
  ).toBeDisabled();
  expect(writes).toHaveLength(1);
  await page.keyboard.press("Escape");
  await expect(panel).not.toBeVisible();
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await ring.click();
  await panel.getByText("Per-model measurements", { exact: true }).click();
  await expect(panel).toContainText("provider reported 100,000");
  await expect(panel).toContainText("provider input not reported");
  await expect(panel).toContainText("GLM-5.3-Flash");
  expect(writes).toHaveLength(1);
});

test("Context popover stays visible above the scrolling composer on a small viewport", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 668 });
  await contextDemo(page);
  await page.getByRole("button", { name: /Context usage, 40%/ }).click();
  const panel = page.getByRole("region", { name: "Context details" });
  await expect(panel).toBeVisible();
  const box = await panel.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  expect(box!.y + box!.height).toBeLessThanOrEqual(668);
  expect(
    await panel.evaluate((element) =>
      element.contains(
        document.elementFromPoint(
          element.getBoundingClientRect().left + 20,
          element.getBoundingClientRect().top + 20,
        ),
      ),
    ),
  ).toBe(true);
  await page.screenshot({ path: info.outputPath("context-ring-mobile.png") });
  await page.keyboard.press("Escape");
  await expect(panel).not.toBeVisible();
});

test("Unmeasured context is shown as unknown instead of a zero reading", async ({
  page,
}) => {
  await contextDemo(page, false);
  const ring = page.getByRole("button", {
    name: "Context usage, not measured yet",
  });
  await expect(ring).toBeVisible();
  await expect(ring).not.toContainText("0%");
  await ring.click();
  await expect(
    page.getByRole("region", { name: "Context details" }),
  ).toContainText("Usage will appear when the first request is prepared");
});
