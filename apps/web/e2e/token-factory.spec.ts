import { test, expect } from "@playwright/test";

test("expired prices preserve the full Token Factory baseline and reconnect without resetting controls", async ({
  page,
}) => {
  let bootstrap: any;
  const ids = [
    "nvidia/Nemotron-3.5-Super-VL",
    "reflection/beam",
    "nvidia/Nemotron-3_5-Lightning",
    "deepseek-ai/DeepSeek-V4-Flash-0731",
  ];
  const defaults = [ids[0], ids[1], ids[3]];
  await page.route("**/api/chats/bootstrap", async (route) => {
    const response = await route.fetch();
    bootstrap = await response.json();
    const tf = bootstrap.providers.nebius_token_factory;
    Object.assign(tf, {
      ready: false,
      preferred: true,
      configured: true,
      price_cache_days: 7,
      default_models: defaults,
      verified_models: [],
      models: ids.map((id) => ({
        id,
        name: id === "reflection/beam" ? "Reflection Beam" : id.split("/")[1],
      })),
      price_refresh: {
        state: "unavailable",
        message: "Metadata connection temporarily unavailable.",
      },
    });
    bootstrap.providers.direct_council.ready = true; // The old silent fallback is reproducible.
    bootstrap.research.configured = true;
    await route.fulfill({ json: bootstrap });
  });
  await page.route("**/api/chats/preview?**", (route) =>
    route.fulfill({
      json: { planned_calls: 10, required_start: 18, blocked: false },
    }),
  );
  let reconnects = 0;
  await page.route("**/api/chats/token-factory/refresh", async (route) => {
    reconnects++;
    bootstrap.providers.nebius_token_factory.ready = true;
    bootstrap.providers.nebius_token_factory.verified_models = ids;
    bootstrap.providers.nebius_token_factory.price_refresh = { state: "ready" };
    await route.fulfill({ json: bootstrap });
  });
  await page.goto("/");
  await expect(page.getByLabel("Thinking level", { exact: true })).toHaveValue(
    "balanced",
  );
  await expect(
    page.locator(".council-composer-actions .context-trigger"),
  ).toBeVisible();
  await expect(
    page.getByRole("switch", { name: "Web search", exact: true }),
  ).toBeChecked();
  await page
    .getByLabel("Message the council")
    .fill("Keep the complete agreed council baseline.");
  await expect(
    page.getByRole("button", { name: "Start council", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: /Customize/ }).click();
  await expect(
    page.getByLabel("Council provider", { exact: true }),
  ).toHaveValue("nebius_token_factory");
  await page.getByRole("button", { name: /3 models/ }).click();
  for (const name of [
    /Nemotron-3.5-Super-VL/,
    /Reflection Beam/,
    /DeepSeek-V4-Flash-0731/,
  ]) {
    await expect(page.getByRole("checkbox", { name })).toBeChecked();
  }
  await expect(
    page.getByRole("checkbox", { name: /Nemotron-3_5-Lightning/ }),
  ).not.toBeChecked();
  await expect(page.getByRole("checkbox", { name: /Z.ai/ })).toHaveCount(0);
  await page
    .getByRole("button", { name: "Reconnect Token Factory", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Reconnect Token Factory", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("dialog", { name: "Council settings", exact: true })
    .getByRole("button", { name: "Done", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Start council", exact: true }),
  ).toBeEnabled();
  await expect(page.getByLabel("Thinking level", { exact: true })).toHaveValue(
    "balanced",
  );
  await page.locator(".council-composer-actions .context-trigger").click();
  await expect(
    page.getByRole("region", { name: "Context details", exact: true }),
  ).toContainText("262,144");
  expect(reconnects).toBe(1);
  await page.screenshot({
    path: "test-results/token-factory-baseline-recovered.png",
  });
});

test("Token Factory defaults to three models, leaves Lightning optional and preserves credit and research settings", async ({
  page,
}) => {
  const models = [
    "nvidia/Nemotron-3.5-Super-VL",
    "reflection/beam",
    "nvidia/Nemotron-3_5-Lightning",
    "deepseek-ai/DeepSeek-V4-Flash-0731",
  ];
  const defaults = models.filter(
    (id) => !id.endsWith("Nemotron-3_5-Lightning"),
  );
  await page.route("**/api/chats/bootstrap", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.providers.nebius_token_factory.ready = true;
    data.research.configured = true;
    data.providers.nebius_token_factory.models = models.map((id) => ({
      id,
      name: id === "reflection/beam" ? "Reflection Beam" : id.split("/")[1],
      selection_notice: id.endsWith("Nemotron-3_5-Lightning")
        ? "Optional: observed startup waits exceeded one minute."
        : null,
    }));
    data.providers.nebius_token_factory.default_models = defaults;
    await route.fulfill({ json: data });
  });
  await page.route("**/api/chats/preview?**", (route) =>
    route.fulfill({
      json: {
        planned_calls: 10,
        research_calls: 5,
        required_start: 18,
        blocked: false,
        reason: null,
      },
    }),
  );
  let submitted: any = null;
  await page.route("**/api/chats", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    submitted = route.request().postDataJSON();
    await route.fulfill({
      status: 412,
      json: { detail: "Offline UI check: inference deliberately blocked" },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: /Customize/ }).click();
  await expect(
    page.getByText("Nemotron Super leads.", { exact: false }),
  ).toBeVisible();
  await page.getByLabel("Council provider").selectOption("fixture");
  await page
    .getByLabel("Council provider")
    .selectOption("nebius_token_factory");
  await page.getByRole("button", { name: /3 models/ }).click();
  await expect(
    page.getByRole("checkbox", { name: /Reflection Beam/ }),
  ).toBeChecked();
  await expect(page.getByRole("checkbox", { name: /GLM-5/ })).toHaveCount(0);
  const lightning = page.getByRole("checkbox", {
    name: /Nemotron-3_5-Lightning/,
  });
  await expect(lightning).not.toBeChecked();
  await expect(
    page.getByText("Optional: observed startup waits exceeded one minute."),
  ).toBeVisible();
  await lightning.check();
  await expect(lightning).toBeChecked();
  await lightning.uncheck();
  await page
    .getByLabel("Shared public search topic (optional)")
    .fill("Public engineering comparisons");
  await page
    .getByRole("dialog", { name: "Council settings", exact: true })
    .getByRole("button", { name: "Done", exact: true })
    .click();
  await expect(
    page.getByRole("switch", { name: "Web search", exact: true }),
  ).toBeChecked();
  await page
    .getByLabel("Message the council")
    .fill("Compare engineering approaches for a generic task.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(
    page.getByText("Offline UI check: inference deliberately blocked"),
  ).toBeVisible();
  expect(submitted.provider).toBe("nebius_token_factory");
  expect(submitted.models).toEqual(defaults);
  expect(submitted.budget_usd).toBe(24);
  expect(submitted.spending_scope).toBe("shared_existing_credit");
  expect(submitted.search_web).toBe(true);
  expect(submitted.search_query).toBe("Public engineering comparisons");
});

test("Saved chat recovery discloses its extra allowance and keeps the draft before any new request", async ({
  page,
}) => {
  await page.setViewportSize({ width: 622, height: 668 });
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Compare generic designs under explicit constraints.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const url = page.url();
  const cid = new URL(url).searchParams.get("chat");
  await page.route(`**/api/chats/${cid}`, async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.chat.status = "failed";
    data.chat.error =
      "Lightning sent no HTTP response before the read timeout.";
    data.unknown_paid_attempts = 1;
    data.model_recovery = {
      call_id: "saved_lightning_timeout",
      allowed: true,
      action_label: "Continue without Lightning",
      additional_allowance_usd: 0.25,
    };
    await route.fulfill({ json: data });
  });
  let submitted: any = null;
  await page.route(`**/api/chats/${cid}/control`, async (route) => {
    submitted = route.request().postDataJSON();
    await route.fulfill({
      status: 409,
      json: { detail: "Offline check: no paid continuation was dispatched." },
    });
  });
  await page.reload();
  const notice = page.getByRole("region", { name: "Continue saved council" });
  await expect(notice).toContainText("adds $0.25");
  const continuation = notice.getByRole("button", {
    name: /Continue without Lightning/,
  });
  await expect(continuation).toBeDisabled();
  for (const view of ["Simple", "Explain"]) {
    await page.getByRole("button", { name: view, exact: true }).click();
    await expect(notice).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollHeight),
    ).toBe(668);
  }
  await page
    .getByLabel("Message the council")
    .fill("Keep my unsent follow-up.");
  await page
    .getByRole("checkbox", { name: /Allow further model requests/ })
    .check();
  await continuation.click();
  await expect(
    page.getByText("Offline check: no paid continuation was dispatched."),
  ).toBeVisible();
  expect(submitted).toMatchObject({
    action: "continue_without_model",
    recovery_call_id: "saved_lightning_timeout",
    authorize_retry_with_unknown_charge: true,
    additional_allowance_usd: 0.25,
  });
  await expect(page.getByLabel("Message the council")).toHaveValue(
    "Keep my unsent follow-up.",
  );
  expect(page.url()).toBe(url);
});
