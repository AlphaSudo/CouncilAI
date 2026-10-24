import { test, expect } from "@playwright/test";

test("The home page keeps one workspace and caps long drafts inside the textbox", async ({
  page,
}, info) => {
  const writes: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      new URL(request.url()).pathname.startsWith("/api/chats")
    )
      writes.push(request.url());
  });
  await page.goto("/");
  const draft = Array.from(
    { length: 32 },
    (_, index) =>
      `${index + 1}. Compare engineering approaches with explicit assumptions and preserve the full original question.`,
  ).join("\n\n");
  const composer = page.getByLabel("Message the council");
  await composer.fill(draft);
  for (const width of [622, 390, 320]) {
    await page.setViewportSize({ width, height: 668 });
    for (const view of ["Simple", "Explain"]) {
      await page.getByRole("button", { name: view, exact: true }).click();
      await expect(composer).toHaveValue(draft);
      await expect(page.locator(".council-composer-area")).toHaveCSS(
        "overflow-y",
        "visible",
      );
      await expect(page.locator(".council-feed")).toHaveCSS(
        "overflow-y",
        "visible",
      );
      await expect
        .poll(() =>
          composer.evaluate(
            (element) => element.clientHeight <= 180 && element.scrollHeight > element.clientHeight,
          ),
        )
        .toBe(true);
      const surfaces = await page.locator(".council-main").evaluate((main) =>
        Array.from(main.querySelectorAll<HTMLElement>("*"))
          .filter(
            (element) =>
              element.clientHeight > 0 &&
              element.scrollHeight > element.clientHeight + 1 &&
              ["auto", "scroll"].includes(getComputedStyle(element).overflowY),
          )
          .map((element) => element.id || element.className),
      );
      expect(surfaces).toEqual(["council-workspace", "council-question"]);
      await expect(composer).toHaveCSS("overflow-y", "auto");
      const workspace = page.locator(".council-workspace");
      await workspace.evaluate((element) => {
        element.scrollTop = element.scrollHeight;
      });
      await expect(
        page.getByRole("button", { name: "Start council", exact: true }),
      ).toBeInViewport();
      if (view === "Simple") {
        await page
          .getByRole("button", { name: "Customize", exact: true })
          .click();
        const settings = page.getByRole("dialog", {
          name: "Council settings",
          exact: true,
        });
        await expect(settings).toBeVisible();
        const box = (await settings.boundingBox())!;
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.y).toBeGreaterThanOrEqual(0);
        expect(box.x + box.width).toBeLessThanOrEqual(width);
        expect(box.y + box.height).toBeLessThanOrEqual(668);
        await settings
          .getByText("Answer requirements", { exact: false })
          .click();
        await settings
          .getByLabel("Deliverable", { exact: true })
          .fill("Retain this answer requirement.");
        await page.screenshot({
          path: info.outputPath(`settings-${width}.png`),
        });
        await page.keyboard.press("Escape");
        await expect(settings).not.toBeVisible();
        await expect(
          page.getByRole("button", { name: "Customize", exact: true }),
        ).toBeFocused();
        await expect(composer).toHaveValue(draft);
        await page
          .getByRole("button", { name: "Customize", exact: true })
          .click();
        await expect(
          settings.getByLabel("Deliverable", { exact: true }),
        ).toHaveValue("Retain this answer requirement.");
        await settings
          .getByRole("button", { name: "Close settings", exact: true })
          .click();
        await expect(settings).not.toBeVisible();
        await workspace.evaluate((element) => {
          element.scrollTop = 0;
        });
        await page.screenshot({
          path: info.outputPath(`single-scroll-home-${width}.png`),
        });
      }
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
  }
  await composer.fill("A short question.");
  await expect.poll(() => composer.evaluate((element) => element.clientHeight)).toBeLessThan(100);
  await composer.fill(draft);
  await expect(composer).toHaveValue(draft);
  await expect.poll(() => composer.evaluate((element) => element.clientHeight)).toBeLessThanOrEqual(180);
  await composer.evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await expect.poll(() => composer.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});
