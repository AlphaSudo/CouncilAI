import { expect, test, type Page } from "@playwright/test";

test.afterEach(async ({ page }) => page.unrouteAll({ behavior: "wait" }));

test("shared review steps show their assigned author and retain the complete original reply", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.setViewportSize({ width: 1000, height: 850 });
  const { cid, data } = await council(page);
  const scrutiny = data.messages.find((m: any) => m.phase === "scrutiny");
  expect(scrutiny).toBeTruthy();
  const raw = JSON.stringify({
    findings: [
      {
        objection: "A matched baseline is needed.",
        minimum_resolution: "Keep this complete resolution.",
        candidate_test: "Keep the original test too.",
      },
    ],
    limitations: "No hardware was tested.",
  });
  await page.route(
    `**/api/chats/${cid}/messages/${scrutiny.id}/original`,
    (route) =>
      route.fulfill({
        json: {
          message_id: scrutiny.id,
          content: raw,
          readable:
            "### Full critique\n\nA matched baseline is needed.\n\nKeep this complete resolution.\n\nKeep the original test too.\n\nNo hardware was tested.",
          new_inference_calls: 0,
        },
      }),
  );
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET") writes.push(request.url());
  });
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  const board = page.getByRole("dialog", { name: "Compare", exact: true });
  for (const phase of ["extraction", "scrutiny", "recheck"]) {
    const stage = board.locator(`.compare-stage[data-phase="${phase}"]`);
    if (await stage.count()) {
      await expect(stage.locator(".compare-shared")).toHaveCount(1);
      await expect(stage.locator(".compare-missing")).toHaveCount(0);
    }
  }
  await expect(
    board.getByText("No saved reply at this stage.", { exact: true }),
  ).toHaveCount(0);
  await board
    .locator(`[data-response-id="${scrutiny.id}"]`)
    .getByRole("button", { name: /Inspect response/ })
    .click();
  const reader = page.locator(".compare-reader");
  await expect(reader).toContainText("Keep this complete resolution.");
  await expect(reader).toContainText("Keep the original test too.");
  await reader
    .getByRole("button", { name: "Original text", exact: true })
    .click();
  await expect(reader.locator(".original-model-reply-text")).toHaveText(raw);
  await reader.getByRole("button", { name: /Copy inspected response/ }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(raw);
  expect(
    await reader
      .locator(".original-model-reply-text")
      .evaluate((el) => getComputedStyle(el).whiteSpace),
  ).toBe("pre-wrap");
  expect(writes).toEqual([]);
  await page.screenshot({
    path: "test-results/response-preservation-original.png",
  });
});

async function council(page: Page) {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill(
      "Compare three reversible approaches with measured constraints. " +
        "Retain the full question. ".repeat(50),
    );
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const cid = new URL(page.url()).searchParams.get("chat");
  const data = await page.evaluate(
    async (id) => (await fetch("/api/chats/" + id)).json(),
    cid,
  );
  return { cid, data };
}

test("Compare aligns the whole saved flow, expands question/replies and preserves the conversation", async ({
  page,
  context,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const { data } = await council(page);
  await page.getByLabel("Message the council").fill("Keep my unsent draft.");
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST") writes.push(r.url());
  });
  const trigger = page.getByRole("button", { name: "Compare", exact: true });
  await trigger.click();
  const board = page.getByRole("dialog", { name: "Compare", exact: true });
  await expect(board).toBeVisible();
  await expect(board.locator(".compare-models > div")).toHaveCount(3);
  await expect(board.locator(".compare-response")).toHaveCount(
    data.messages.length - 1,
  );
  const openings = board.locator(
    '.compare-stage[data-phase="opening"] .compare-cell',
  );
  await expect(openings).toHaveCount(3);
  const boxes = await openings.evaluateAll((els) =>
    els.map((el) => ({
      x: el.getBoundingClientRect().x,
      y: el.getBoundingClientRect().y,
    })),
  );
  expect(new Set(boxes.map((b) => b.y)).size).toBe(1);
  expect(boxes[0].x).toBeLessThan(boxes[1].x);
  expect(boxes[1].x).toBeLessThan(boxes[2].x);
  await expect(board.locator(".compare-stage").nth(1)).toBeInViewport({
    ratio: 1,
  });
  // A long question is bounded, and its full text remains available in the reader.
  expect(
    await board
      .locator(".compare-question-body")
      .evaluate((el) => el.scrollHeight > el.clientHeight),
  ).toBe(true);
  await board
    .getByRole("button", { name: "Expand question", exact: true })
    .click();
  const reader = page.locator(".compare-reader");
  await expect(reader).toBeVisible();
  await expect(reader.locator(".compare-reader-content")).toHaveText(
    data.messages[0].content,
  );
  await reader.getByRole("button", { name: "Increase text size" }).click();
  await expect(reader.getByLabel("Text size", { exact: true })).toHaveText(
    "110%",
  );
  await page.keyboard.press("Escape");
  await expect(reader).toHaveCount(0);
  await expect(
    board.getByRole("button", { name: "Expand question", exact: true }),
  ).toBeFocused();
  const first = data.messages.find((m: any) => m.phase === "opening");
  const response = board.locator(`[data-response-id="${first.id}"]`);
  await response.getByRole("button", { name: /Inspect response/ }).click();
  await expect(reader.locator(".compare-reader-content")).toContainText(
    "small reference case",
  );
  await reader.getByRole("button", { name: /Copy inspected response/ }).click();
  // The Windows clipboard canonicalizes LF to CRLF; Markdown and math are intact.
  expect(
    (await page.evaluate(() => navigator.clipboard.readText())).replace(
      /\r\n/g,
      "\n",
    ),
  ).toBe(first.content.replace(/\r\n/g, "\n"));
  await page.keyboard.press("Escape");
  await expect(
    response.getByRole("button", { name: /Inspect response/ }),
  ).toBeFocused();
  await page.screenshot({ path: "test-results/council-compare-desktop.png" });
  await board
    .getByRole("button", { name: "Conversation", exact: true })
    .click();
  await expect(board).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await expect(page.getByLabel("Message the council")).toHaveValue(
    "Keep my unsent draft.",
  );
  expect(writes).toEqual([]);
});

test("Compare live updates replace the preview once, preserve cell scroll and retain actual authors", async ({
  page,
}) => {
  const { cid, data } = await council(page);
  const member = data.chat.participants[1];
  const original = data.messages.find(
    (m: any) => m.phase === "opening" && m.participant_id === member.id,
  );
  data.messages = data.messages.filter(
    (m: any) => m.role === "user" || m.phase === "opening",
  );
  data.messages = data.messages.filter((m: any) => m.id !== original.id);
  data.chat.status = "running";
  data.chat.active_turn = {
    phase: "opening",
    participant_id: member.id,
    name: member.name,
    model: member.model,
    round: data.messages[1].round,
  };
  data.chat.final_message_id = null;
  data.active_request = {
    call_id: "compare-live",
    sent_at: new Date().toISOString(),
    stream_progress: { phase: "answering" },
  };
  data.public_streams = [
    {
      call_id: "compare-live",
      chunks: [{ seq: 1, text: "Visible live answer. " }],
    },
  ];
  await page.route(/\/api\/missions\/[^/]+\/events(?:\?.*)?$/, (route) =>
    route.abort(),
  );
  let reads = 0;
  await page.route("**/api/chats/" + cid, (route) => {
    reads++;
    return route.fulfill({ json: data });
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  const board = page.locator(".council-compare");
  const cell = board.locator(
    `.compare-stage[data-phase="opening"] [data-member="${member.id}"]`,
  );
  await expect(cell).toContainText("Visible live answer.");
  await cell.getByRole("button", { name: /Inspect response/ }).click();
  await expect(page.locator(".compare-reader-content")).toHaveText(
    "Visible live answer.",
  );
  data.public_streams[0].chunks.push({
    seq: 2,
    text: "The second chunk remains visible.",
  });
  await expect(page.locator(".compare-reader-content")).toContainText(
    "second chunk",
    { timeout: 6500 },
  );
  await page
    .locator(".compare-reader")
    .getByRole("button", { name: "Increase text size" })
    .click();
  data.messages.push({
    ...original,
    call_id: "compare-live",
    content:
      "Saved final text with $\\eta = 1 - T_c/T_h$. " +
      "A measured baseline. ".repeat(120),
    actual_model: "synthetic/replacement-model",
    name: "Actual replacement author",
  });
  await expect(cell.locator(".compare-response")).toHaveCount(1, {
    timeout: 6500,
  });
  await expect(cell).toContainText("Actual replacement author");
  await expect(cell.locator(".katex")).toHaveCount(1);
  await expect(cell.locator(".compare-response")).toHaveAttribute(
    "data-model",
    "synthetic/replacement-model",
  );
  await expect(page.locator(".compare-reader")).toBeVisible();
  await expect(page.locator(".compare-reader-content")).toContainText(
    "Saved final text",
  );
  await expect(
    page.locator(".compare-reader").getByLabel("Text size", { exact: true }),
  ).toHaveText("110%");
  await page.keyboard.press("Escape");
  await cell.evaluate((el) => {
    el.scrollTop = 100;
    el.dispatchEvent(new Event("scroll"));
  });
  const top = await cell.evaluate((el) => el.scrollTop);
  const previousReads = reads;
  await expect
    .poll(() => reads, { timeout: 6500 })
    .toBeGreaterThan(previousReads + 1);
  expect(await cell.evaluate((el) => el.scrollTop)).toBe(top);
  expect(await board.locator('[data-response-id^="live-"]').count()).toBe(0);
});

test("Narrow Compare pans inside the board, handles extra seats and honestly shows skipped stages", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 780 });
  const { cid, data } = await council(page);
  const extra = {
    id: "optional-fourth",
    name: "Optional fourth model",
    model: "synthetic/fourth",
  };
  data.chat.participants.push(extra);
  data.effective_members = [...data.chat.participants];
  data.stage_results = [
    { phase: "recheck", review_cycle: 1, state: "skipped" },
  ];
  data.messages = data.messages.filter((m: any) => m.phase !== "recheck");
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: data }),
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  const board = page.locator(".council-compare");
  await expect(board.locator(".compare-models > div")).toHaveCount(4);
  await expect(
    board.locator('.compare-stage[data-phase="recheck"]'),
  ).toContainText("Skipped");
  await expect(
    board.locator('.compare-stage[data-phase="recheck"] .compare-response'),
  ).toHaveCount(0);
  const geometry = await board
    .locator(".compare-scroll")
    .evaluate((el) => ({ client: el.clientWidth, scroll: el.scrollWidth }));
  expect(geometry.scroll).toBeGreaterThan(geometry.client);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await board.locator(".compare-scroll").evaluate((el) => {
    el.scrollLeft = el.scrollWidth;
  });
  await expect(
    board.getByText("Optional fourth model", { exact: true }),
  ).toBeInViewport();
  await board
    .getByRole("button", { name: "Expand question", exact: true })
    .click();
  await expect(page.locator(".compare-reader")).toBeVisible();
  await page.screenshot({ path: "test-results/council-compare-narrow.png" });
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await expect(board).toHaveCount(0);
  await expect(page.getByLabel("Message the council")).toBeVisible();
});

test("Compare preserves successive cycles and historical authors after a model replacement", async ({
  page,
}) => {
  const { cid, data } = await council(page);
  const openings = data.messages.filter((m: any) => m.phase === "opening");
  const oldName = openings[0].name;
  data.effective_members = data.chat.participants.map((p: any, i: number) =>
    i
      ? p
      : {
          ...p,
          name: "Current replacement",
          model: "synthetic/current-model",
        },
  );
  data.messages.push({
    id: "compare-followup",
    role: "user",
    phase: "director",
    review_cycle: 2,
    content: "Now compare the same designs under a stricter latency target.",
    sequence: 40,
  });
  for (const [i, message] of openings.entries())
    data.messages.push({
      ...message,
      id: `compare-cycle2-${i}`,
      review_cycle: 2,
      sequence: 41 + i,
      name: i ? message.name : "Current replacement",
      actual_model: i ? message.model : "synthetic/current-model",
      content: `Cycle two: an attributed response from ${i ? message.name : "Current replacement"}.`,
    });
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: data }),
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  const board = page.locator(".council-compare");
  await expect(
    board.locator(
      '.compare-stage[data-phase="opening"][data-cycle="1"] .compare-response',
    ),
  ).toHaveCount(3);
  await expect(
    board.locator(
      '.compare-stage[data-phase="opening"][data-cycle="2"] .compare-response',
    ),
  ).toHaveCount(3);
  await expect(
    board.locator(`[data-response-id="${openings[0].id}"]`),
  ).toContainText(oldName);
  await expect(
    board.locator('[data-response-id="compare-cycle2-0"]'),
  ).toContainText("Current replacement");
  await expect(
    board.locator('[data-response-id="compare-followup"]'),
  ).toContainText("stricter latency target");
  await expect(board.locator(".compare-response")).toHaveCount(
    data.messages.length - 1,
  );
});

test("Denied clipboard in an expanded reader keeps manual copy accessible and closes one layer at a time", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async () => {
          throw new Error("Offline denied clipboard fixture");
        },
      },
    });
    document.execCommand = () => false;
  });
  const { data } = await council(page);
  const first = data.messages.find((m: any) => m.phase === "opening");
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await page
    .locator(`[data-response-id="${first.id}"]`)
    .getByRole("button", { name: /Inspect response/ })
    .click();
  const reader = page.locator(".compare-reader");
  await reader.getByRole("button", { name: /Copy inspected response/ }).click();
  const copy = page.getByRole("dialog", {
    name: "Copy text manually",
    exact: true,
  });
  await expect(copy).toBeVisible();
  await expect(
    copy.getByRole("textbox", { name: "Text to copy" }),
  ).toBeFocused();
  await expect(copy.getByRole("textbox", { name: "Text to copy" })).toHaveValue(
    first.content,
  );
  await page.keyboard.press("Escape");
  await expect(copy).toHaveCount(0);
  await expect(reader).toBeVisible();
  await expect(
    reader.getByRole("button", { name: /Copy inspected response/ }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(reader).toHaveCount(0);
  await expect(page.locator(".council-compare")).toBeVisible();
});
