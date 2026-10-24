import { test, expect } from "@playwright/test";

for (const hasDraft of [false, true]) {
  test(`Output limit recovery shows ${hasDraft ? "saved draft" : "reasoning-only usage"} and requires an explicit click`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 622, height: 768 });
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "New council", exact: true }),
    ).toBeVisible();
    const created = await page.request.post("/api/chats", {
      headers: {
        "X-ZeroWall-Director": "1",
        "Idempotency-Key": `recovery-ui-${hasDraft}-${Date.now()}`,
      },
      data: {
        prompt: "Inspect a saved partial answer without calling a provider.",
        provider: "fixture",
        models: ["demo/analyst", "demo/critic", "demo/builder"],
        defer_start: true,
      },
    });
    expect(created.ok()).toBeTruthy();
    const fixture = await created.json();
    const id = fixture.chat.id;
    fixture.chat.status = "failed";
    fixture.chat.error =
      "Model reached the output token limit; response may be truncated. No automatic retry.";
    fixture.unknown_paid_attempts = 1;
    fixture.output_recovery = {
      call_id: "call_saved_glm",
      name: "GLM Flash",
      model: "zai-org/GLM-5.3-Flash",
      phase: "opening",
      reasoning_tokens: hasDraft ? 11900 : 12000,
      answer_tokens: hasDraft ? 100 : 0,
      output_tokens: 12000,
      has_saved_answer: hasDraft,
      partial_answer: hasDraft
        ? "## Saved approach\nThis paragraph survives truncation."
        : "",
      preview_truncated: false,
      mode: "append_markdown",
      available: true,
      reason: null,
      action_label: hasDraft ? "Continue saved answer" : "Answer now",
      new_billed_request: true,
      internal_reasoning_resumable: false,
      attempts_used: 8,
      attempt_limit: 20,
      conversation_remaining_usd: 0.215295,
      global_remaining_usd: 23.965295,
    };
    if (!hasDraft)
      fixture.model_recovery = {
        call_id: "call_saved_glm",
        name: "GLM Flash",
        model: "zai-org/GLM-5.3-Flash",
        action_label: "Continue without GLM Flash",
        allowed: true,
        additional_allowance_usd: 0,
        unknown_charge_retained: false,
        failure_kind: "reasoning_only_output_limit",
      };
    await page.route(`**/api/chats/${id}`, (route) =>
      route.fulfill({ json: fixture }),
    );
    let submitted: any = null;
    await page.route(`**/api/chats/${id}/control`, async (route) => {
      submitted = route.request().postDataJSON();
      await route.fulfill({
        json: {
          ...fixture,
          output_recovery: null,
          chat: { ...fixture.chat, status: "paused", error: null },
        },
      });
    });
    await page.goto(`/?chat=${id}`);
    const panel = page.getByRole("alert", { name: "Saved response recovery" });
    await expect(panel).toBeVisible();
    await expect(
      panel.getByText(/8 of 20 request attempts used/),
    ).toBeVisible();
    await expect(
      panel.getByText(/23.9653 remains under the shared \$24 total cap/),
    ).toBeVisible();
    await expect(
      panel.getByText("Reasoning tokens", { exact: true }),
    ).toBeVisible();
    await expect(
      panel.getByText(hasDraft ? "11,900" : "12,000", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      panel.getByText("Answer tokens", { exact: true }),
    ).toBeVisible();
    await expect(
      panel.getByText(hasDraft ? "100" : "0", { exact: true }),
    ).toBeVisible();
    await expect(
      panel.getByText(/Internal reasoning cannot be resumed/),
    ).toBeVisible();
    const button = panel.getByRole("button", {
      name: hasDraft ? "Continue saved answer" : "Answer now",
      exact: true,
    });
    await expect(button).toBeDisabled();
    if (!hasDraft)
      await expect(
        panel.getByRole("button", {
          name: "Continue without GLM Flash",
          exact: true,
        }),
      ).toBeDisabled();
    expect(submitted).toBeNull();
    await page
      .getByRole("checkbox", {
        name: /Allow further model requests while the earlier charge remains unknown/,
      })
      .check();
    await expect(button).toBeEnabled();
    if (hasDraft) {
      await panel
        .getByText("View saved partial answer", { exact: true })
        .click();
      await expect(
        panel.getByText("This paragraph survives truncation.", { exact: true }),
      ).toBeVisible();
    }
    await panel.screenshot({
      path: `test-results/output-recovery-${hasDraft ? "draft" : "reasoning-only"}.png`,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    if (hasDraft) await button.click();
    else
      await panel
        .getByRole("button", {
          name: "Continue without GLM Flash",
          exact: true,
        })
        .click();
    expect(submitted.action).toBe(
      hasDraft ? "recover_output" : "continue_without_model",
    );
    expect(submitted.recovery_call_id).toBe("call_saved_glm");
    expect(submitted.authorize_retry_with_unknown_charge).toBe(true);
  });
}
