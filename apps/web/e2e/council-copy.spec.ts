import { test, expect, type Page } from "@playwright/test";

const answer =
  "## A useful answer\n\nKeep $\\Omega_{\\mathrm{sun}}$ and **uncertainty** intact.\n\n```text\na < b\n```";

async function savedCouncil(page: Page, finalAnswer = answer) {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("Compare engineering approaches and preserve equations.");
  await page
    .getByRole("button", { name: "Start council", exact: true })
    .click();
  await expect(page.locator(".council-status")).toHaveText("Answer ready");
  const cid = new URL(page.url()).searchParams.get("chat")!;
  const saved = await (await page.request.get(`/api/chats/${cid}`)).json();
  saved.messages.find(
    (m: any) => m.id === saved.chat.final_message_id,
  ).content = finalAnswer;
  await page.route(`**/api/chats/${cid}`, (route) =>
    route.fulfill({ json: saved }),
  );
  await page.reload();
  await expect(
    page.locator(".is-final .council-message-content"),
  ).toContainText("A useful answer");
  return saved;
}

test("Copy one and all responses preserves source Markdown, equations, order and the draft in both views", async ({
  page,
}) => {
  // Keep QA off the user's OS clipboard while exercising the actual UI API call.
  await page.addInitScript(() => {
    (window as any).__copied = [];
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (text: string) => {
          (window as any).__copied.push(text);
        },
      },
    });
  });
  const saved = await savedCouncil(page);
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/api/chats"))
      writes.push(r.url());
  });
  const composer = page.getByLabel("Message the council");
  await composer.fill("Keep my unsent follow-up.");
  const copy = page
    .locator(".is-final")
    .getByRole("button", { name: /^Copy response from/ });
  await copy.click();
  await expect(copy).toHaveAttribute("title", "Copied");
  expect(await page.evaluate(() => (window as any).__copied.at(-1))).toBe(
    answer,
  );
  await page
    .getByRole("button", { name: "Copy all responses", exact: true })
    .click();
  const combined = await page.evaluate(() => (window as any).__copied.at(-1));
  let position = -1;
  for (const message of saved.messages) {
    const next = combined.indexOf(message.content, position + 1);
    expect(next).toBeGreaterThan(position);
    position = next;
  }
  expect(combined).toContain("Opening question");
  expect(combined).toContain("Model:");
  expect(combined).not.toContain("known rate estimate");
  await expect(composer).toHaveValue("Keep my unsent follow-up.");
  await page.getByRole("button", { name: "Explain", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /^Copy response from/ }),
  ).toHaveCount(
    saved.messages.filter((m: any) => m.role === "assistant").length,
  );
  await page.setViewportSize({ width: 622, height: 800 });
  const all = page.getByRole("button", {
    name: "Copy all responses",
    exact: true,
  });
  const bounds = await all.boundingBox();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(622);
  await all.focus();
  await page.keyboard.press("Enter");
  await expect(all).toBeFocused();
  expect(writes).toEqual([]);
});

test("Long replies scroll inside the council without exposing an outer page in either view", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const longAnswer = [
    answer,
    ...Array.from(
      { length: 50 },
      (_, index) =>
        `### Approach ${index + 1}\n\nA detailed engineering comparison keeps assumptions, evidence and uncertainty explicit. Review each alternative before deciding which approach fits the constraints.`,
    ),
  ].join("\n\n");
  await savedCouncil(page, longAnswer);
  const composer = page.getByLabel("Message the council");
  await composer.fill("Keep this unsent draft while scrolling.");
  for (const viewport of [
    { width: 622, height: 668 },
    { width: 390, height: 668 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    for (const view of ["Explain", "Simple"]) {
      await page.getByRole("button", { name: view, exact: true }).click();
      await expect(page.locator(".council-app")).toHaveAttribute(
        "data-view",
        view.toLowerCase(),
      );
      expect(
        await page.evaluate(() => document.documentElement.scrollHeight),
      ).toBeLessThanOrEqual(viewport.height);
      await page.evaluate(() => window.scrollTo(0, 100000));
      expect(await page.evaluate(() => window.scrollY)).toBe(0);
      const feed = page.locator(".council-feed");
      await feed.evaluate((el) => {
        el.scrollTop = 0;
      });
      expect(await feed.evaluate((el) => el.scrollTop)).toBe(0);
      await feed.evaluate((el) => {
        el.scrollTop = el.scrollHeight;
      });
      expect(await feed.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
      const bounds = await composer.boundingBox();
      await page.mouse.move(bounds!.x + 10, bounds!.y + bounds!.height - 5);
      await page.mouse.wheel(0, 1500);
      expect(await page.evaluate(() => window.scrollY)).toBe(0);
      await expect(composer).toHaveValue(
        "Keep this unsent draft while scrolling.",
      );
      expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(viewport.height);
      await expect(page.locator("html")).toHaveCSS(
        "background-color",
        "rgb(25, 27, 26)",
      );
    }
  }
  await page.goto("/?workspace=research");
  await expect(page.locator(".council-app")).toHaveCount(0);
  await expect(page.locator("html")).toHaveCSS(
    "background-color",
    "rgb(247, 248, 245)",
  );
});

test("Denied clipboard API uses the local browser fallback without losing the draft", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async () => {
          throw new Error("Denied");
        },
      },
    });
    document.execCommand = (command: string) => {
      if (command !== "copy") return false;
      (window as any).__fallbackText = (
        document.activeElement as HTMLTextAreaElement
      ).value;
      return true;
    };
  });
  await savedCouncil(page);
  await page.getByLabel("Message the council").fill("A preserved draft.");
  const copy = page
    .locator(".is-final")
    .getByRole("button", { name: /^Copy response from/ });
  await copy.click();
  await expect(copy).toHaveAttribute("title", "Copied");
  expect(await page.evaluate(() => (window as any).__fallbackText)).toBe(
    answer,
  );
  await expect(
    page.getByRole("dialog", { name: "Copy text manually" }),
  ).toHaveCount(0);
  await expect(page.getByLabel("Message the council")).toHaveValue(
    "A preserved draft.",
  );
});

test("If both clipboard methods are denied, selected text is available with Escape and focus recovery", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async () => {
          throw new Error("Denied");
        },
      },
    });
    document.execCommand = () => false;
  });
  await savedCouncil(page);
  await page.setViewportSize({ width: 390, height: 844 });
  const copy = page
    .locator(".is-final")
    .getByRole("button", { name: /^Copy response from/ });
  await copy.click();
  const dialog = page.getByRole("dialog", { name: "Copy text manually" });
  await expect(dialog).toBeVisible();
  const text = dialog.getByRole("textbox", { name: "Text to copy" });
  await expect(text).toHaveValue(answer);
  await expect(text).toBeFocused();
  expect(
    await text.evaluate(
      (element: HTMLTextAreaElement) =>
        element.selectionEnd - element.selectionStart,
    ),
  ).toBe(answer.length);
  await page.keyboard.press("Tab");
  await expect(
    dialog.getByRole("button", { name: "Close copy dialog" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(copy).toBeFocused();
});
