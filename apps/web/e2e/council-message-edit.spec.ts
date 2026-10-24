import { expect, test } from "@playwright/test";

async function savedCouncil(page: any) {
  await page.goto("/");
  await page
    .getByLabel("Message the council")
    .fill("ORIGINAL compare reversible engineering options.");
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

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "wait" });
});

test("Edit and cancel preserve the separate composer draft and never send a request", async ({
  page,
}) => {
  const { view } = await savedCouncil(page);
  await page.getByLabel("Message the council").fill("Unsent follow-up draft.");
  const posts: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") posts.push(request.url());
  });
  await page
    .getByRole("button", { name: "Edit message 1", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Edit message",
    exact: true,
  });
  await expect(dialog.getByLabel("Your message")).toHaveValue(
    view.messages[0].content,
  );
  await dialog.getByLabel("Your message").fill("An edit I have not submitted.");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByLabel("Message the council")).toHaveValue(
    "Unsent follow-up draft.",
  );
  expect(posts).toEqual([]);
});

test("Submitting a corrected question starts a full review in the same chat and preserves original replies", async ({
  page,
}) => {
  const { cid, view } = await savedCouncil(page);
  const originalFinal = view.messages.find(
    (m: any) => m.id === view.chat.final_message_id,
  );
  await page
    .getByLabel("Message the council")
    .fill("Keep this unrelated draft.");
  const edits: any[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/regenerate"))
      edits.push(request.postDataJSON());
  });
  await page
    .getByRole("button", { name: "Edit message 1", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Edit message",
    exact: true,
  });
  await dialog
    .getByLabel("Your message")
    .fill("CORRECTED compare memory transfer options.");
  await dialog
    .getByRole("button", { name: "Edit & regenerate", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect
    .poll(async () =>
      page.evaluate(
        async (id: string) =>
          (await (await fetch("/api/chats/" + id)).json()).chat.review_cycle,
        cid,
      ),
    )
    .toBe(2);
  await expect(page.locator(".council-status")).toHaveText("Answer ready", {
    timeout: 20000,
  });
  await expect(page.locator(".council-message.is-user").last()).toContainText(
    "CORRECTED compare memory transfer options.",
  );
  await expect(page.locator(".council-message.is-user").last()).toContainText(
    "Edited request",
  );
  await expect(page.locator("#" + originalFinal.id)).toContainText(
    "Earlier version",
  );
  await expect(
    page.locator("#" + originalFinal.id + " .council-message-content"),
  ).toContainText(originalFinal.content.split("\n")[0].replace(/\*\*/g, ""));
  await expect(page.getByLabel("Message the council")).toHaveValue(
    "Keep this unrelated draft.",
  );
  expect(new URL(page.url()).searchParams.get("chat")).toBe(cid);
  expect(edits).toHaveLength(1);
  expect(edits[0].authorize_retry_with_unknown_charge).toBe(true);
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Current question", exact: true }),
  ).toContainText("CORRECTED compare memory transfer options.");
  await expect(
    page.locator(`.council-compare [data-response-id="${originalFinal.id}"]`),
  ).toContainText("Earlier version");
});

test("A failed request can be edited; a server error preserves the edit and existing draft", async ({
  page,
}) => {
  const { cid, view } = await savedCouncil(page);
  view.chat.status = "paused";
  view.chat.active_turn = null;
  view.chat.final_message_id = null;
  view.unknown_paid_attempts = 1;
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  const writes: any[] = [];
  await page.route(
    "**/api/chats/" + cid + "/messages/*/regenerate",
    async (route) => {
      writes.push(route.request().postDataJSON());
      await route.fulfill({
        status: 409,
      json: { detail: "Revision changed. Refresh before acting." },
      });
    },
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  await page
    .getByLabel("Message the council")
    .fill("Unsent draft survives failure.");
  await page
    .getByRole("button", { name: "Edit message 1", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Edit message",
    exact: true,
  });
  await expect(dialog).toContainText("charge is unknown and stays reserved");
  await dialog.getByLabel("Your message").fill("Correct the failed request.");
  await expect(
    dialog.getByRole("button", { name: "Edit & regenerate", exact: true }),
  ).toBeEnabled();
  expect(writes).toEqual([]);
  await dialog
    .getByRole("button", { name: "Edit & regenerate", exact: true })
    .click();
  await expect(dialog.getByRole("alert")).toContainText("Revision changed");
  await expect(dialog.getByLabel("Your message")).toHaveValue(
    "Correct the failed request.",
  );
  expect(writes).toHaveLength(1);
  expect(writes[0].authorize_retry_with_unknown_charge).toBe(true);
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByLabel("Message the council")).toHaveValue(
    "Unsent draft survives failure.",
  );
});

test("The editor fits a narrow screen and waits for an active model without cancelling it", async ({
  page,
}) => {
  const { cid, view } = await savedCouncil(page);
  view.chat.status = "running";
  view.chat.active_turn = {
    phase: "opening",
    name: "Demo Analyst",
    model: "demo/analyst",
  };
  await page.route("**/api/chats/" + cid, (route) =>
    route.fulfill({ json: view }),
  );
  const writes: string[] = [];
  await page.route("**/api/chats/" + cid + "/control", async (route) => {
    writes.push(route.request().postDataJSON().action);
    view.chat.status = "paused";
    view.chat.active_turn = null;
    await route.fulfill({ json: view });
  });
  await page.setViewportSize({ width: 390, height: 740 });
  await page.reload({ waitUntil: "domcontentloaded" });
  await page
    .getByRole("button", { name: "Edit message 1", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Edit message",
    exact: true,
  });
  await dialog
    .getByLabel("Your message")
    .fill("Keep my edited draft while the active request finishes.");
  await expect(
    dialog.getByRole("button", { name: "Edit & regenerate", exact: true }),
  ).toBeDisabled();
  expect(writes).toEqual([]);
  await dialog
    .getByRole("button", { name: "Pause after this response", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "Edit & regenerate", exact: true }),
  ).toBeEnabled();
  await expect(dialog.getByLabel("Your message")).toHaveValue(
    "Keep my edited draft while the active request finishes.",
  );
  expect(writes).toEqual(["pause"]);
  const box = await dialog.boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(390);
  await page.screenshot({ path: "test-results/message-edit-narrow.png" });
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
});
