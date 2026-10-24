import { expect, test } from "@playwright/test";

async function savedCouncil(page: any) {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill(
      "Compare reversible engineering approaches with explicit assumptions.",
    );
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready", {
    timeout: 20000,
  });
  const cid = new URL(page.url()).searchParams.get("chat");
  const view = await page.evaluate(
    async (id: string) => (await fetch("/api/chats/" + id)).json(),
    cid,
  );
  return { cid, view };
}

test("Incomplete review remains a quiet note; views and copy keep the same answer", async ({
  page,
}) => {
  const { cid, view } = await savedCouncil(page);
  view.chat.review_state = "incomplete";
  view.chat.generation_state = "complete";
  view.review.delivery_degraded = true;
  view.review.delivery_warnings = [
    {
      phase: "recheck",
      reason: "Synthetic annotation fault for UI testing only",
    },
  ];
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator(".council-status")).toHaveText(
    "Answer ready · review partial",
  );
  await expect(
    page.getByText(
      "Some review details are unavailable. Received answers are saved.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Resume", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".council-state-note.is-error")).toHaveCount(0);
  const final = page.locator(
    ".council-message.is-final .council-message-content",
  );
  const text = await final.innerText();
  await page
    .getByLabel("Message the council")
    .fill("Keep my draft after switching views.");
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") posts.push(request.url());
  });
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await page
    .getByRole("button", { name: "Review details", exact: true })
    .click();
  await expect(page.getByLabel("Review delivery diagnostics")).toContainText(
    "Synthetic annotation fault",
  );
  await page.getByRole("button", { name: "Simple", exact: true }).click();
  await expect(page.getByLabel("Message the council")).toHaveValue(
    "Keep my draft after switching views.",
  );
  expect(await final.innerText()).toBe(text);
  expect(posts).toEqual([]);
});

test("Public stream replay is visible once and never exposes structured metadata", async ({
  page,
}) => {
  const { cid, view } = await savedCouncil(page);
  view.chat.status = "running";
  view.chat.active_turn = {
    phase: "opening",
    name: "Demo Analyst",
    model: "demo/analyst",
  };
  view.active_request = {
    call_id: "synthetic-stream",
    model: "demo/analyst",
    sent_at: new Date().toISOString(),
  };
  view.public_streams = [
    {
      call_id: "synthetic-stream",
      chunks: [
        { seq: 1, text: "A reversible pilot " },
        { seq: 2, text: "preserves alternatives." },
      ],
    },
  ];
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByLabel("Live answer from Demo Analyst")).toContainText(
    "A reversible pilot preserves alternatives.",
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByLabel("Live answer from Demo Analyst")).toHaveCount(1);
  view.public_streams[0].chunks = [
    { seq: 1, text: '{"findings":[{"objection":"internal metadata"}]}' },
  ];
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByLabel("Live answer from Demo Analyst")).toHaveCount(0);
});

test("Answer-first keeps a narrow dark workspace, capped composer and accessible controls", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 740 });
  await savedCouncil(page);
  await page
    .getByLabel("Message the council")
    .fill("A long user prompt. ".repeat(800));
  const geometry = await page
    .getByLabel("Message the council")
    .evaluate((element: HTMLTextAreaElement) => ({
      height: element.getBoundingClientRect().height,
      scroll: element.scrollHeight,
      overflow: getComputedStyle(element).overflowY,
    }));
  expect(geometry.height).toBeLessThanOrEqual(241);
  expect(geometry.scroll).toBeGreaterThan(geometry.height);
  expect(geometry.overflow).toBe("auto");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await expect(
    page.getByRole("button", { name: "Copy all responses" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/answer-first-narrow.png",
    fullPage: true,
  });
});

test("Incomplete formal labels do not mislabel a fully generated final answer as truncated", async ({
  page,
}) => {
  const { cid, view } = await savedCouncil(page);
  view.chat.review_state = "incomplete";
  view.chat.generation_state = "complete";
  view.review.delivery_degraded = true;
  view.review.discussion_continuity = {
    mode: "public_discussion",
    grants_authority: false,
  };
  const final = view.messages.find(
    (m: any) => m.id === view.chat.final_message_id,
  );
  final.partial = true;
  final.generation_state = "complete";
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(
    page.locator(".council-message.is-final .council-message-heading"),
  ).toContainText("Final synthesis");
  await expect(
    page.getByText(
      "Formal review labels are incomplete. The council continued with a discussion.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(
    page.locator(`.council-compare [data-response-id="${final.id}"]`),
  ).not.toContainText("Partial answer");
});

test("An interrupted opening offers an explicit retry, keeps its unknown charge visible and never retries on load", async ({
  page,
}) => {
  const { cid, view } = await savedCouncil(page);
  view.chat.status = "paused";
  view.chat.active_turn = null;
  view.chat.error =
    "Nemotron's connection failed before an HTTP response after 37.8 seconds.";
  view.chat.final_message_id = null;
  view.chat.pending_request_recovery = {
    turn_key: "review:2:opening:member_1",
    call_id: "offline-unknown",
    name: "Nemotron Super",
    phase: "opening",
  };
  view.unknown_paid_attempts = 1;
  const writes: any[] = [];
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  await page.route("**/api/chats/" + cid + "/control", async (route) => {
    writes.push(route.request().postDataJSON());
    await route.fulfill({ json: view });
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.locator(".council-status")).toHaveText("paused");
  await expect(page.getByText(/request was interrupted/)).toBeVisible();
  const retry = page.getByRole("button", {
    name: "Retry response",
    exact: true,
  });
  await expect(retry).toBeDisabled();
  expect(writes).toEqual([]);
  await page
    .getByRole("checkbox", {
      name: /earlier charge remains unknown and counted/,
    })
    .check();
  await expect(retry).toBeEnabled();
  await retry.click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0].action).toBe("resume");
  expect(writes[0].authorize_retry_with_unknown_charge).toBe(true);
});
