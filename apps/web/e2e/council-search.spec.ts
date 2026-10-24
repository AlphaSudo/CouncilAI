import { expect, test } from "@playwright/test";

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "wait" });
});

async function existingChat(page: any) {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Compare practical engineering choices.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const cid = new URL(page.url()).searchParams.get("chat");
  const view = await page.evaluate(
    async (id: string) => (await fetch("/api/chats/" + id)).json(),
    cid,
  );
  view.chat.provider = "nebius_token_factory";
  view.chat.research_enabled = true;
  return { cid, view };
}

async function configured(page: any) {
  await page.route("**/api/chats/bootstrap", async (route: any) => {
    const response = await route.fetch();
    const body = await response.json();
    body.research.configured = true;
    await route.fulfill({ response, json: body });
  });
}

test("The main search switch can change upcoming replies during generation without a model request", async ({
  page,
}) => {
  const { cid, view } = await existingChat(page);
  await configured(page);
  view.chat.status = "running";
  view.chat.active_turn = {
    phase: "opening",
    name: "Demo Analyst",
    model: "demo/analyst",
  };
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  const changes: any[] = [];
  await page.route(
    "**/api/chats/" + cid + "/research/settings",
    async (route) => {
      changes.push(route.request().postDataJSON());
      view.chat.next_turn_research_enabled = false;
      await route.fulfill({ json: view });
    },
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  const toggle = page.getByRole("switch", { name: "Web search", exact: true });
  await expect(toggle).toBeChecked();
  await expect(toggle).toBeEnabled();
  await toggle.click();
  await expect(toggle).not.toBeChecked();
  expect(changes).toEqual([{ enabled: false }]);
  await expect(page.locator(".council-status")).toHaveText("Council working");
});

test("Replies distinguish fresh, cached and unavailable search and explain the actual query", async ({
  page,
}) => {
  const { cid, view } = await existingChat(page);
  await configured(page);
  const replies = view.messages.filter((m: any) => m.phase === "opening");
  replies[0].web_search = {
    status: "completed",
    query: "Official primary source query",
    result_count: 3,
    reused: false,
  };
  replies[1].web_search = {
    status: "completed",
    query: "Official primary source query",
    result_count: 3,
    reused: true,
  };
  replies[2].web_search = {
    status: "unavailable",
    query: "A limited query",
    reason: "Free search allowance unavailable",
  };
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await expect(
    page.getByText("Web searched · 3 results", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Cached search · 3 results", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Web search unavailable", { exact: true }),
  ).toBeVisible();
  await page
    .locator("#" + replies[0].id)
    .getByText("Search details", { exact: true })
    .click();
  await expect(page.locator("#" + replies[0].id)).toContainText(
    "Official primary source query",
  );
});

test("Search and thinking controls fit inside the narrow main composer", async ({
  page,
}) => {
  const { cid, view } = await existingChat(page);
  await configured(page);
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  await page.setViewportSize({ width: 390, height: 740 });
  await page.reload({ waitUntil: "domcontentloaded" });
  const toggle = page.getByRole("switch", { name: "Web search", exact: true });
  await expect(toggle).toBeVisible();
  const box = await toggle.boundingBox();
  const send = await page
    .getByRole("button", { name: "Send message", exact: true })
    .boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(send!.x + send!.width).toBeLessThanOrEqual(390);
  expect(Math.abs(box!.y - send!.y)).toBeLessThan(25);
  await page.screenshot({ path: "test-results/search-toggle-narrow.png" });
});
