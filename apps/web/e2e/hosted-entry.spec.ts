import { test, expect } from "@playwright/test";

test("Hosted access uses an explicit code, keeps the session on reload, and never opens local entry", async ({
  page,
}) => {
  let localRequests = 0;
  let hasHostedSession = false;
  await page.route("**/api/session", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        json: { authenticated: hasHostedSession, local_entry: false },
      });
      return;
    }
    if (
      route.request().postDataJSON().token !== "offline-browser-access-code"
    ) {
      await route.fulfill({
        status: 401,
        json: { detail: "Invalid access code" },
      });
      return;
    }
    // Give this isolated fixture browser a real backend cookie. Public-mode
    // HTTP and cookie boundaries are exercised separately by backend tests.
    const response = await route.fetch({
      url: "http://127.0.0.1:8001/api/session/local",
      method: "POST",
      data: {},
    });
    hasHostedSession = true;
    await route.fulfill({ response });
  });
  await page.route("**/api/session/local", async (route) => {
    localRequests += 1;
    await route.abort();
  });
  await page.goto("/");
  await expect(page.getByLabel("Access code", { exact: true })).toBeFocused();
  await page.getByLabel("Access code", { exact: true }).fill("wrong");
  await page.getByRole("button", { name: "Open council", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("Invalid access code");
  await page
    .getByLabel("Access code", { exact: true })
    .fill("offline-browser-access-code");
  await page.getByRole("button", { name: "Open council", exact: true }).click();
  await expect(page.getByLabel("Message the council")).toBeFocused();
  await page.reload();
  await expect(page.getByLabel("Message the council")).toBeFocused();
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  expect(localRequests).toBe(0);
});
