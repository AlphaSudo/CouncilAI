import { test, expect } from "@playwright/test";

// Detailed workflow regression checks run in Explain; default Simple is covered separately.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() =>
    localStorage.setItem("zerowall.council.view", "explain"),
  );
});

test("Saved JSON and equations read clearly; direct follow-up survives the old cap", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.locator(".council-app")).toHaveCSS("color-scheme", "dark");
  await page
    .getByLabel("Message the council")
    .fill("Compare five generic engineering approaches.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator('[data-phase="synthesis"]')).toHaveCount(1);
  const cid = new URL(page.url()).searchParams.get("chat")!;
  // Freeze the completed fixture before navigation; polling requests can be
  // cancelled by reload while route.fetch() is still reading its response.
  const saved = await (await page.request.get(`/api/chats/${cid}`)).json();
  let blocked = false;
  await page.route(`**/api/chats/${cid}`, async (route) => {
    if (route.request().method() !== "GET") return route.continue();
    const data = structuredClone(saved);
    data.chat.provider = "direct_council";
    data.budget.remaining_calls = 0;
    data.budget.attempts = 44;
    data.continuation = {
      allowed: !blocked,
      reason: blocked
        ? "Daily allowance exhausted. Continue here after the reset."
        : null,
    };
    data.direct_capacity = { daily_remaining: blocked ? 0 : 56 };
    data.review_adoption = {
      available: true,
      allowed: !blocked,
      required_start: 13,
      reason: data.continuation.reason,
    };
    data.lead = data.chat.participants[1];
    const reply = data.messages.find((m: any) => m.phase === "opening");
    reply.content = JSON.stringify({
      engineering_approach:
        "Use angular selectivity with $C \\to 46{,}200\\times$ and $\\Omega_{\\mathrm{sun}}$.",
      efficiency: "\\[\\eta = 1 - \\frac{4}{3}\\frac{T_c}{T_h}\\]",
      code_example: "`const cost = '$25';`",
      percent: "A proposed value of $93.3%$ is unverified.",
      legacy_formula: "[ \\dot S = \\frac{Q}{T} ]",
      nested_formula: "$$\n\\eta = \\left(\\frac{T_c}{T_h}\\right)^4\n$$",
      legacy_nested:
        "( \\Delta S_T = Q\\left(\\frac{1}{T_c} - \\frac{1}{T_h}\\right) )",
      mixed_text:
        'Peer answer:\n\n```json\n{"next_step":"Inspect the scope."}\n```\n\nStill uncertain.',
      malformed_math:
        '```json\n{"derivation":"$\\epsilon(\\theta, \\nu)$"}\n```',
      flat_legacy:
        '```json\n{\n"scope": "A "narrow" $\\mu$ proposal",\n"condition": "Check $\\alpha$ before use."\n}\n```',
      currency: "The budget is $25 and $10 remains.",
      untrusted:
        "<script>window.__injected = true</script> ![hidden](https://invalid.example/tracker.png) $\\href{javascript:alert(1)}{unsafe}$",
    });
    reply.actual_model = "openai/gpt-oss-20b";
    reply.replacement_for = "groq::openai/gpt-oss-120b";
    reply.replacement_name = "Groq GPT OSS 120B";
    await route.fulfill({ json: data });
  });
  await page.reload();
  const reply = page.locator('[data-phase="opening"]').first();
  await expect(page.locator(".council-header h1")).toHaveCSS(
    "letter-spacing",
    "normal",
  );
  await expect(reply.locator("h4").first()).toHaveText("engineering approach");
  await expect(reply.locator(".katex")).toHaveCount(10);
  await expect(reply.locator(".katex-display")).toHaveCount(3);
  for (const field of [
    "efficiency",
    "nested formula",
    "legacy nested",
    "legacy formula",
  ]) {
    await expect(
      reply
        .locator(".council-structured section")
        .filter({
          has: page.getByRole("heading", { name: field, exact: true }),
        })
        .locator(".katex-error"),
    ).toHaveCount(0);
  }
  await expect(reply.locator("code")).toHaveText("const cost = '$25';");
  await expect(reply.locator(".council-replacement")).toContainText(
    "Free model replacement",
  );
  await expect(reply.locator("img, script")).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).__injected)).toBeUndefined();
  await expect(reply.locator('a[href^="javascript:"]')).toHaveCount(0);
  await expect(
    reply.getByRole("heading", { name: "next step", exact: true }),
  ).toBeVisible();
  await reply.getByText("Original structured response").last().click();
  await expect(reply.locator(".council-original pre").last()).toContainText(
    '"engineering_approach"',
  );
  await page
    .getByLabel("Message the council")
    .fill("Now rank the best five engineering approaches.");
  await expect(
    page.getByRole("button", { name: "Send message", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByText("44 total attempts", { exact: false }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page
      .locator(".council-main")
      .evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
  ).toBe(true);
  await expect(page.locator(".council-header h1")).toHaveCSS(
    "font-size",
    "15px",
  );
  blocked = true;
  await page.reload();
  await page
    .getByLabel("Message the council")
    .fill("Continue after the daily reset.");
  await expect(
    page.getByRole("button", { name: "Send message", exact: true }),
  ).toBeDisabled();
  await expect(
    page
      .getByText("Daily allowance exhausted. Continue here after the reset.")
      .first(),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
