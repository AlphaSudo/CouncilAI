import { expect, test } from "@playwright/test";

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "wait" });
});

async function council(page: any) {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Compare solar conversion mechanisms and their physical limits.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const cid = new URL(page.url()).searchParams.get("chat");
  const view = await page.evaluate(
    async (id: string) => (await fetch("/api/chats/" + id)).json(),
    cid,
  );
  view.collective_research = {
    id: "synthetic-collective",
    state: "ready",
    cycle: 1,
    extracted_pages: 2,
    source_count: 2,
    members: view.chat.participants.map((member: any, index: number) => ({
      ...member,
      member_id: member.id,
      angle: ["Foundations", "Approaches", "Challenges"][index],
      state: "searched",
      query: [
        "solar thermodynamic bounds primary papers",
        "nonreciprocal photonic conversion experimental evidence",
        "angular entropy reciprocity constraints counterexamples",
      ][index],
      query_origin: "model",
      search_finished: true,
      results: [{ url: "https://example.com/shared" }],
    })),
    pages: [
      {
        url: "https://example.com/shared",
        title: "Shared primary paper",
        contributors: view.chat.participants.map((m: any) => m.id),
        access: "extracted_page",
        version_id: "synthetic-version",
      },
      {
        url: "https://example.com/limits",
        title: "Practical limitations",
        contributors: [view.chat.participants[2].id],
        access: "extracted_page",
        version_id: "synthetic-limits",
      },
    ],
  };
  return { cid, view };
}

test("Parallel research progress precedes opening answers and does not show planning JSON as an answer", async ({
  page,
}) => {
  const { cid, view } = await council(page);
  view.chat.status = "running";
  view.chat.active_turn = {
    phase: "opening",
    name: view.chat.participants[0].name,
  };
  view.messages = view.messages.filter((m: any) => m.role === "user");
  view.collective_research.state = "searching";
  view.collective_research.members.forEach((m: any) => {
    m.state = "searching";
    m.search_finished = false;
  });
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/api/chats"))
      writes.push(request.url());
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  const research = page.getByRole("region", {
    name: "Collective web research",
  });
  await expect(research).toContainText("Searching the web in parallel");
  await expect(research.locator(".collective-members > li")).toHaveCount(3);
  await expect(
    page.locator(".council-message[data-phase=opening]"),
  ).toHaveCount(0);
  await expect(page.locator(".council-thinking")).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("The shared library exposes real contributor attribution, page access and chosen queries", async ({
  page,
}) => {
  const { cid, view } = await council(page);
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  const research = page.getByRole("region", {
    name: "Collective web research",
  });
  await expect(research).toContainText("3 researchers · 2 pages saved");
  await research.locator("summary").click();
  await expect(research).toContainText(
    "solar thermodynamic bounds primary papers",
  );
  await expect(research).toContainText("model-chosen query");
  const shared = research
    .getByRole("listitem")
    .filter({ hasText: "Shared primary paper" });
  await expect(shared).toContainText("Page saved");
  for (const member of view.chat.participants)
    await expect(shared).toContainText(member.name);
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(
    page
      .getByRole("dialog", { name: "Compare", exact: true })
      .getByRole("region", { name: "Collective web research" }),
  ).toContainText("3 researchers");
});

test("Partial research stays inspectable on a narrow screen and leaves completed answers available", async ({
  page,
}) => {
  const { cid, view } = await council(page);
  view.collective_research.state = "limited";
  view.collective_research.extracted_pages = 1;
  view.collective_research.pages[1].access = "search_snippet_only";
  delete view.collective_research.pages[1].version_id;
  view.collective_research.members[1].query_origin = "fallback";
  view.collective_research.members[1].planning_limitation =
    "Model query planning was unavailable; no automatic retry.";
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  await page.setViewportSize({ width: 390, height: 740 });
  await page.reload({ waitUntil: "domcontentloaded" });
  const research = page.getByRole("region", {
    name: "Collective web research",
  });
  await research.locator("summary").click();
  await expect(research).toContainText("partial coverage");
  await expect(research).toContainText("Search excerpt");
  await expect(research).toContainText("assigned-angle query");
  await expect(page.locator(".council-message.is-final")).toBeVisible();
  const box = await research.boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  await research.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: "test-results/collective-research-narrow.png",
  });
});
