import { test, expect, type Page } from "@playwright/test";

test("Missed status events recover from preparation through reasoning to completion", async ({ page }) => {
  await demo(page);
  let phase: "preparing" | "reasoning" | "completed" = "preparing";
  await page.route(/\/api\/missions\/[^/]+\/events(?:\?.*)?$/, (route) => route.abort());
  await page.route(/\/api\/chats\/chat_[^/?]+$/, async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.chat.provider = "nebius_token_factory";
    data.chat.status = phase === "completed" ? "completed" : "running";
    data.chat.active_turn = phase === "reasoning"
      ? { phase: "opening", name: "GLM Flash", model: "zai-org/GLM-5.3-Flash" }
      : null;
    data.active_request = phase === "reasoning"
      ? { call_id: "offline_poll_recovery", model: "zai-org/GLM-5.3-Flash", sent_at: new Date(Date.now() - 100000).toISOString(), stream_progress: { phase: "reasoning", last_activity_at: new Date().toISOString() } }
      : null;
    await route.fulfill({ response, json: data });
  });
  await page.reload();
  const indicator = page.locator(".council-thinking[role='status']");
  await expect(indicator).toContainText("is preparing the next request");
  await expect(indicator).not.toContainText("responding to the discussion");
  phase = "reasoning";
  await expect(indicator).toContainText("GLM Flash", { timeout: 6000 });
  await expect(indicator).toContainText("Reasoning activity received; no answer text yet");
  phase = "completed";
  await expect(indicator).toHaveCount(0, { timeout: 6000 });
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
});

async function demo(page: Page) {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Compare two generic engineering approaches.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
}

test("Replies show request timing and requested reasoning budgets; interrupted usage stays unknown", async ({
  page,
}) => {
  await demo(page);
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/api/chats"))
      writes.push(r.url());
  });
  await page.route(/\/api\/chats\/chat_[^/?]+$/, async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    const message = data.messages.find(
      (m: any) => m.id === data.chat.final_message_id,
    );
    message.source = "model_api";
    message.name = "Nemotron Super";
    const attempt = {
      call_id: "offline_timing_attempt",
      provider: "nebius_token_factory",
      model: "nvidia/Nemotron-3.5-Super-VL",
      state: "completed",
      generation: {
        profile: "raw_opening",
        reasoning: "medium",
        effective_output_tokens: 250000,
        control_status: "requested_not_live_verified",
        reasoning_budget_tokens: 4000,
        reasoning_budget_enforcement: "system_instruction_only",
        reasoning_budget_instruction:
          "Reasoning budget for this request: use at most 4,000 reasoning tokens before producing the final answer.",
      },
      reasoning_budget_observation: {
        requested_tokens: 4000,
        reported_tokens: 26528,
        over_requested_tokens: 22528,
        status: "above_requested_budget",
        enforcement: "system_instruction_only",
      },
      usage: {
        status: "reported",
        categories: {
          billable_output: 29736,
          output_reasoning: 26528,
          output_visible: 3208,
        },
        states: {
          billable_output: "known",
          output_reasoning: "known",
          output_visible: "known",
        },
        inclusion_rules: "Reasoning is included in output.",
      },
      cost: {
        lines: [],
        status: "complete_estimate",
        known_subtotal_usd: "0.0270957",
        provider_reported_amount_usd: null,
        view: "published_price_equivalent",
      },
      price_card: {
        id: "offline_test_card",
        checked_at: "2026-10-21",
        source_url: "https://tokenfactory.nebius.com/",
      },
      timing: {
        elapsed_seconds: 105.9373,
        first_stream_seconds: null,
        first_answer_seconds: null,
        output_tokens_per_second: 280.6944,
        visible_tokens_per_second: 30.2821,
        stream: null,
      },
    };
    const unknown = {
      ...attempt,
      call_id: "offline_unknown",
      model: "zai-org/GLM-5.3-Flash",
      state: "unknown",
      reasoning_budget_observation: {
        requested_tokens: 4000,
        reported_tokens: null,
        over_requested_tokens: null,
        status: "not_reported",
        enforcement: "system_instruction_only",
      },
      timing: {
        elapsed_seconds: 323.887,
        first_stream_seconds: null,
        first_answer_seconds: null,
        output_tokens_per_second: null,
        visible_tokens_per_second: null,
        stream: null,
      },
    };
    const total = {
      attempts: 1,
      usage_reported_attempts: 1,
      tokens: {},
      cost_state: "complete_estimate",
      known_reference_subtotal_usd: "0.0270957",
    };
    data.accounting.replies[message.id] = { attempts: [attempt], total };
    data.accounting.attempts = [attempt, unknown];
    data.accounting.total = {
      ...total,
      attempts: 2,
      timed_attempts: 2,
      known_request_seconds: 429.8243,
      unknown_outcomes: 1,
    };
    await route.fulfill({ response, json: data });
  });
  await page.reload();
  const usage = page.locator(".is-final .reply-usage").first();
  await expect(usage.locator("summary")).toContainText("105.94 s request time");
  await expect(usage.locator("summary")).toContainText(
    "280.7 tokens/s including reasoning",
  );
  await usage.locator("summary").first().click();
  await expect(usage).toContainText("Visible answer rate");
  await expect(usage).toContainText("30.3 tokens/s");
  await expect(usage).toContainText("not engine-only generation speed");
  await expect(usage).toContainText("Reasoning budget requested: 4,000 tokens");
  await expect(usage).toContainText("not a hard provider limit");
  await expect(usage).toContainText(
    "Exceeded the requested budget by 22,528 tokens",
  );
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  if ((await usage.getAttribute("open")) === null)
    await usage.locator("summary").first().click();
  await usage.getByText("Reasoning instruction sent", { exact: true }).click();
  await expect(usage).toContainText(
    "at most 4,000 reasoning tokens before producing the final answer",
  );
  await page.locator(".conversation-usage > summary").click();
  await page.getByText("Unfinished requests (1)", { exact: true }).click();
  const unfinished = page.locator(".unfinished-requests");
  await expect(unfinished).toContainText("323.89 s");
  await expect(unfinished).toContainText(
    "TPS is unavailable without final token usage",
  );
  expect(writes).toEqual([]);
});

test("Running replies show a ticking timer and reasoning activity without invented token counts", async ({
  page,
}) => {
  await demo(page);
  let started = new Date(Date.now() - 5000).toISOString();
  let status = "running";
  await page.route(/\/api\/chats\/chat_[^/?]+$/, async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.chat.status = status;
    data.chat.provider = "nebius_token_factory";
    data.chat.active_turn = {
      phase: "opening",
      name: "GLM Flash",
      model: "zai-org/GLM-5.3-Flash",
    };
    data.active_request = {
      call_id: "offline_live_timing",
      model: "zai-org/GLM-5.3-Flash",
      sent_at: started,
      stream_progress: {
        phase: "reasoning",
        events: 50,
        reasoning_chunks: 49,
        answer_characters: 0,
        last_activity_at: new Date().toISOString(),
      },
    };
    await route.fulfill({ response, json: data });
  });
  await page.setViewportSize({ width: 622, height: 800 });
  await page.reload();
  const active = page.locator(".active-response-timing");
  await expect(active).toContainText(
    "Reasoning activity received; no answer text yet",
  );
  const initial = await active.locator(".response-elapsed").innerText();
  await expect(active.locator(".response-elapsed")).not.toHaveText(initial, {
    timeout: 4000,
  });
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await expect(active).toContainText("49 reasoning chunks observed");
  await expect(active).toContainText("Chunks are not tokens");
  const bounds = await active.boundingBox();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(622);
  started = new Date(Date.now() - 100000).toISOString();
  await page.reload();
  await expect(active).toContainText("reasoning target is advisory");
  await expect(
    page.getByRole("button", { name: "Pause after reply", exact: true }),
  ).toBeVisible();
  status = "paused";
  await page.reload();
  await expect(
    page.getByText("is finishing this reply before pausing", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("The current reply and its usage will finish saving", {
      exact: false,
    }),
  ).toBeVisible();
  const pausedClock = await active.locator(".response-elapsed").innerText();
  await expect(active.locator(".response-elapsed")).not.toHaveText(
    pausedClock,
    { timeout: 4000 },
  );
});
