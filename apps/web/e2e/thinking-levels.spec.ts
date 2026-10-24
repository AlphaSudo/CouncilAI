import { test, expect, type Page } from "@playwright/test";

const models = [
  "nvidia/Nemotron-3.5-Super-VL",
  "zai-org/GLM-5.3-Flash",
  "deepseek-ai/DeepSeek-V4-Flash-0731",
];
const levels = [
  { id: "quick", label: "Quick", reasoning_tokens: 2000 },
  { id: "balanced", label: "Balanced", reasoning_tokens: 4000 },
  { id: "deep", label: "Deep", reasoning_tokens: 8000 },
  { id: "maximum", label: "Maximum", reasoning_tokens: 16000 },
];
function profile(level: string) {
  return {
    supported: true,
    level,
    levels,
    models: models.map((model) => ({
      model,
      reasoning: model.startsWith("zai-org/") ? "low" : level === "deep" ? "high" : "low",
      reasoning_budget_tokens: model.startsWith("zai-org/") ? 1000 : levels.find((x) => x.id === level)!.reasoning_tokens,
      model_reasoning_override: model.startsWith("zai-org/"),
      native_effort_available: true,
    })),
  };
}

async function existingCouncil(page: Page, ledger?: Record<string, number>) {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Compare engineering approaches with explicit conditions.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  let level = "balanced",
    cap = 0.25;
  const writes: Array<{ url: string; body: any }> = [];
  await page.route(
    /\/api\/chats\/chat_[^/?]+\/(thinking|allowance)$/,
    async (route) => {
      const request = route.request();
      writes.push({ url: request.url(), body: request.postDataJSON() });
      if (request.url().endsWith("/thinking"))
        level = request.postDataJSON().level;
      else cap += request.postDataJSON().add_usd;
      await route.fulfill({ json: { level, cap_usd: cap } });
    },
  );
  await page.route(/\/api\/chats\/chat_[^/?]+$/, async (route) => {
    const response = await route.fetch();
    const value = await response.json();
    value.chat.provider = "nebius_token_factory";
    value.chat.title =
      "### Physics Challenge: Overcoming the Thermodynamic & Geometric Efficiency Limits of Solar Energy Conversion";
    value.chat.thinking_level = level;
    value.context_status = {
      supported: true,
      capacity_tokens: 262144,
      automatic_threshold_percent: 80,
      mode: "adaptive",
      latest: null,
    };
    value.chat.participants.forEach((member: any, index: number) => {
      member.model = models[index];
    });
    value.thinking = profile(level);
    if (ledger) {
      value.budget = { ...value.budget, ...ledger };
      value.accounting.total = {
        ...value.accounting.total,
        attempts: 3,
        usage_reported_attempts: 2,
        complete_estimates: 2,
        known_reference_subtotal_usd: "0.0110526",
        cost_state: "partial_estimate",
        tokens: {
          input_total_reported: {
            known_subtotal: 2005,
            reported_attempts: 2,
            total_attempts: 3,
          },
          output_total_reported: {
            known_subtotal: 16928,
            reported_attempts: 2,
            total_attempts: 3,
          },
        },
      };
    }
    value.conversation_allowance = {
      cap_usd: cap,
      remaining_usd:
        cap -
        (ledger
          ? ledger.settled_usd + ledger.reserved_usd + ledger.unknown_usd
          : 0.05),
      maximum_addition_usd: 24 - cap,
      absolute_cap_usd: 24,
    };
    await route.fulfill({ response, json: value });
  });
  await page.reload();
  return writes;
}

test("An interrupted request's maximum hold is distinguished from recorded spending and sub-cent funds", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 760 });
  const writes = await existingCouncil(page, {
    settled_usd: 0.011053,
    reserved_usd: 0,
    unknown_usd: 0.2365,
  });
  const allowance = page.locator(".conversation-allowance");
  await expect(allowance).toHaveCount(0);
  const totals = page.getByRole("group", {
    name: "Conversation totals",
    exact: true,
  });
  await expect(totals).toContainText("Input ≥2,005");
  await expect(totals).toContainText("Output ≥16,928");
  await expect(totals).toContainText("Estimated cost ≥$0.011053");
  await expect(totals).toContainText("2/3 requests reported");
  await page.screenshot({
    path: info.outputPath("conversation-totals-mobile.png"),
  });
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await allowance.locator("summary").click();
  await expect(
    allowance
      .locator(".allowance-breakdown > div")
      .filter({ hasText: "Recorded request cost" }),
  ).toContainText("$0.011053");
  await expect(
    allowance
      .locator(".allowance-breakdown > div")
      .filter({ hasText: "Unknown charges" }),
  ).toContainText("$0.2365");
  await expect(
    allowance
      .locator(".allowance-breakdown > div")
      .filter({ hasText: "Available for new requests" }),
  ).toContainText("$0.002447");
  await expect(allowance).toContainText(
    "held amount is not confirmed spending",
  );
  await expect(allowance).toContainText(
    "All chats share the $24 application cap",
  );
  await page.screenshot({
    path: info.outputPath("chat-limit-breakdown-mobile.png"),
  });
  expect(writes).toEqual([]);
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("Composer controls stay aligned inside the form and the title stays on one line", async ({
  page,
}, info) => {
  const writes = await existingCouncil(page);
  const picker = page.getByLabel("Thinking level", { exact: true });
  const ring = page.getByRole("button", {
    name: "Context usage, not measured yet",
  });
  const send = page.getByRole("button", { name: "Send message", exact: true });
  await page
    .getByLabel("Message the council")
    .fill("Keep this draft while inspecting controls.");
  await picker.selectOption("maximum");
  await expect(picker).toHaveValue("maximum");

  for (const width of [622, 390, 320, 1280]) {
    await page.setViewportSize({ width, height: 668 });
    for (const view of ["Simple", "Explain"]) {
      await page.getByRole("button", { name: view, exact: true }).click();
      await expect(
        page.locator(".council-composer-actions select"),
      ).toHaveCount(1);
      await expect(
        page.locator(".council-composer-actions .context-trigger"),
      ).toHaveCount(1);
      await expect(
        page.getByText("Applies to upcoming requests", { exact: true }),
      ).toHaveCount(0);
      await expect(
        page.getByText(
          "Existing credit only · $24 total cap · $0 additional payment authorized",
          { exact: true },
        ),
      ).toHaveCount(0);
      await expect(page.locator(".council-header .council-mini")).toHaveCount(
        0,
      );
      const title = page.locator(".council-header h1");
      await expect(title).toHaveText(/^Physics Challenge:/);
      await expect(title).toHaveCSS("white-space", "nowrap");
      await expect(title).toHaveCSS("text-overflow", "ellipsis");
      expect(
        await title.evaluate(
          (element) =>
            element.clientHeight <=
            parseFloat(getComputedStyle(element).lineHeight) + 1,
        ),
      ).toBe(true);
      const form = (await page.locator(".council-composer").boundingBox())!;
      const boxes = await Promise.all([
        picker.boundingBox(),
        ring.boundingBox(),
        send.boundingBox(),
      ]);
      for (const box of boxes) {
        expect(box).not.toBeNull();
        expect(box!.x).toBeGreaterThanOrEqual(form.x);
        expect(box!.x + box!.width).toBeLessThanOrEqual(form.x + form.width);
        expect(box!.y).toBeGreaterThanOrEqual(form.y);
        expect(box!.y + box!.height).toBeLessThanOrEqual(form.y + form.height);
        expect(
          Math.abs(
            box!.y + box!.height / 2 - (boxes[2]!.y + boxes[2]!.height / 2),
          ),
        ).toBeLessThanOrEqual(1);
      }
      expect(boxes[0]!.x + boxes[0]!.width).toBeLessThanOrEqual(boxes[1]!.x);
      expect(boxes[1]!.x + boxes[1]!.width).toBeLessThanOrEqual(boxes[2]!.x);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: info.outputPath(`composer-${view.toLowerCase()}-${width}.png`),
      });
    }
  }
  await expect(page.getByLabel("Message the council")).toHaveValue(
    "Keep this draft while inspecting controls.",
  );
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  expect(writes).toHaveLength(1);
});

test("Thinking changes affect upcoming requests without clearing the draft or starting work", async ({
  page,
}) => {
  const writes = await existingCouncil(page);
  await page
    .getByLabel("Message the council")
    .fill("Keep this follow-up draft.");
  const selector = page.getByLabel("Thinking level", { exact: true });
  await expect(selector).toHaveValue("balanced");
  await selector.selectOption("deep");
  await expect(selector).toHaveValue("deep");
  await expect(
    page.getByRole("status").filter({ hasText: "Thinking level saved" }),
  ).toBeVisible();
  await expect(page.getByLabel("Message the council")).toHaveValue(
    "Keep this follow-up draft.",
  );
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  expect(writes).toHaveLength(1);
  expect(writes[0].body).toEqual({ level: "deep" });
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await page.getByText("Model controls", { exact: true }).click();
  await expect(page.locator(".thinking-mappings")).toContainText(
    "not hard provider caps",
  );
  await expect(page.locator(".thinking-mappings")).toContainText(
    "GLM-5.3-Flash",
  );
  const glm = page.locator(".thinking-model").filter({ hasText: "GLM-5.3-Flash" });
  await expect(glm).toContainText("1,000 reasoning tokens requested");
  await expect(glm).toContainText("low");
  await expect(glm).toContainText("Overruns continue without a client-side cutoff");
});

test("Conversation allowance can be extended explicitly in the same chat on mobile", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 760 });
  const writes = await existingCouncil(page);
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await page.locator(".conversation-allowance > summary").click();
  await page
    .getByLabel("Add existing-credit allowance ($)", { exact: true })
    .fill("0.50");
  await page
    .getByRole("button", { name: "Increase allowance", exact: true })
    .click();
  await expect(page.locator(".conversation-allowance")).toContainText(
    "$0.75",
  );
  await expect(page.locator(".conversation-allowance")).toContainText(
    "No model request was started",
  );
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  expect(writes).toHaveLength(1);
  expect(writes[0].body).toEqual({ add_usd: 0.5 });
  await page.screenshot({
    path: info.outputPath("thinking-and-allowance-mobile.png"),
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("A new council sends the selected thinking preset with its creation request", async ({
  page,
}) => {
  let creation: any;
  await page.route("**/api/chats/bootstrap", async (route) => {
    const response = await route.fetch();
    const value = await response.json();
    Object.assign(value.providers.nebius_token_factory, {
      ready: true,
      default_models: models,
      verified_models: models,
      models: models.map((id) => ({ id, name: id.split("/").pop() })),
      thinking_profiles: Object.fromEntries(
        levels.map((option) => [option.id, profile(option.id)]),
      ),
    });
    await route.fulfill({ response, json: value });
  });
  await page.route("**/api/chats/preview?**", (route) =>
    route.fulfill({
      json: { planned_calls: 10, required_start: 13, blocked: false },
    }),
  );
  await page.route(/\/api\/chats$/, async (route) => {
    creation = route.request().postDataJSON();
    const response = await route.fetch({
      postData: JSON.stringify({
        ...creation,
        provider: "fixture",
        spending_scope: "conversation",
        models: ["demo/analyst", "demo/critic", "demo/builder"],
        budget_usd: 0,
      }),
    });
    await route.fulfill({ response });
  });
  await page.goto("/");
  await page
    .getByLabel("Thinking level", { exact: true })
    .selectOption("maximum");
  await page
    .getByLabel("Message the council")
    .fill("Compare generic engineering ideas.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  expect(creation.thinking_level).toBe("maximum");
  expect(creation.provider).toBe("nebius_token_factory");
  expect(creation.budget_usd).toBe(24);
  expect(creation.spending_scope).toBe("shared_existing_credit");
});
