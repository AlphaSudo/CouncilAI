import { expect, test } from "@playwright/test";
import { writeFileSync, mkdirSync } from "node:fs";

test.afterEach(async ({ page }) => page.unrouteAll({ behavior: "wait" }));

test("Scrolling a long generating council stays put and still receives new answers", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Offline scrolling regression fixture.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const cid = new URL(page.url()).searchParams.get("chat");
  const snapshot = await page.evaluate(
    async (id) => (await fetch("/api/chats/" + id)).json(),
    cid,
  );
  const opening = snapshot.messages.find((m: any) => m.phase === "opening");
  const paragraph =
    "A reversible design preserves options while measuring a fixed baseline. " +
    "The relationship $\\eta = 1 - \\frac{T_c}{T_h}$ must retain its assumptions. " +
    "Compare latency, energy, memory and uncertainty before selecting an approach.\n\n";
  snapshot.messages = [
    snapshot.messages[0],
    ...Array.from({ length: 18 }, (_, i) => ({
      ...opening,
      id: `scrolling_${i}`,
      sequence: i + 2,
      round: Math.floor(i / 3) + 1,
      phase: i < 3 ? "opening" : "debate",
      content: `## Approach ${i + 1}\n\n${paragraph.repeat(12)}`,
    })),
  ];
  snapshot.chat.status = "running";
  snapshot.chat.final_message_id = null;
  snapshot.chat.active_turn = {
    phase: "opening",
    name: opening.name,
    model: opening.model,
  };
  snapshot.active_request = {
    call_id: "offline-scroll",
    sent_at: new Date().toISOString(),
    stream_progress: { phase: "answering" },
  };
  snapshot.public_streams = [];
  let reads = 0;
  await page.route(/\/api\/missions\/[^/]+\/events(?:\?.*)?$/, (route) =>
    route.abort(),
  );
  await page.route("**/api/chats/" + cid, (route) => {
    reads++;
    return route.fulfill({ json: snapshot });
  });
  await page.addInitScript(() =>
    localStorage.setItem("zerowall.council.view", "explain"),
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  const feed = page.locator(".council-feed");
  await expect(page.locator(".council-message")).toHaveCount(19);
  await expect(
    page.locator(".council-message-content .katex").first(),
  ).toBeAttached();
  await feed.evaluate((el) => {
    el.style.scrollBehavior = "auto";
    el.scrollTop = 600;
    el.dispatchEvent(new Event("scroll"));
  });
  await page.waitForTimeout(200);
  const before = await feed.evaluate((el) => el.scrollTop);
  // Fixed workload: repeated full snapshots, a ticking request timer and a reader
  // scrolling a math-heavy history. No provider requests or artificial CPU delay.
  const metrics = await page.evaluate(
    () =>
      new Promise<any>((resolve) => {
        const tasks: number[] = [],
          frames: number[] = [];
        const observer = new PerformanceObserver((list) =>
          list.getEntries().forEach((entry) => tasks.push(entry.duration)),
        );
        observer.observe({ type: "longtask", buffered: false });
        const start = performance.now();
        let previous = start;
        function frame(now: number) {
          frames.push(now - previous);
          previous = now;
          if (now - start < 6600) requestAnimationFrame(frame);
          else {
            observer.disconnect();
            frames.sort((a, b) => a - b);
            resolve({
              duration_ms: now - start,
              frames: frames.length,
              frame_p95_ms: frames[Math.floor(frames.length * 0.95)],
              max_frame_ms: Math.max(...frames),
              long_tasks: tasks.length,
              long_task_ms: tasks.reduce((a, b) => a + b, 0),
              max_long_task_ms: Math.max(0, ...tasks),
            });
          }
        }
        requestAnimationFrame(frame);
      }),
  );
  expect(reads).toBeGreaterThanOrEqual(3);
  expect(
    Math.abs((await feed.evaluate((el) => el.scrollTop)) - before),
  ).toBeLessThan(5);
  await expect(page.locator(".response-elapsed")).toContainText(
    /\d+ s elapsed/,
  );
  snapshot.messages.push({
    ...opening,
    id: "scrolling_new",
    sequence: 21,
    content:
      "A new saved answer must still arrive while reading earlier replies.",
  });
  await expect(page.locator("#scrolling_new")).toContainText(
    "must still arrive",
    { timeout: 6500 },
  );
  expect(
    Math.abs((await feed.evaluate((el) => el.scrollTop)) - before),
  ).toBeLessThan(5);
  snapshot.chat.status = "completed";
  snapshot.chat.active_turn = null;
  await expect(page.locator(".council-status")).toHaveText("Answer ready", {
    timeout: 6500,
  });
  if (process.env.COUNCIL_PERF_LABEL) {
    const folder = "../../docs/validation/council-compare";
    mkdirSync(folder, { recursive: true });
    writeFileSync(
      `${folder}/scroll-${process.env.COUNCIL_PERF_LABEL}.json`,
      JSON.stringify(
        {
          workload:
            "18 saved replies, 216 math paragraphs, 2-second full snapshot polling, 1-second elapsed timer; 6.6 seconds after initial render",
          ...metrics,
          snapshot_reads: reads,
          provider_calls: 0,
        },
        null,
        2,
      ),
    );
  }
});
