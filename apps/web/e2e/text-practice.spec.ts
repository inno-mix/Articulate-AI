import { expect, test } from "@playwright/test";

test("complete a text practice session and see it in history", async ({ page }) => {
  await page.goto("/practice");

  await page.getByRole("combobox", { name: "Category" }).click();
  await page.getByRole("option", { name: "Code review" }).click();

  await page.getByRole("link", { name: /Give code review feedback/ }).click();
  await expect(page).toHaveURL(/\/practice\/code-review-give-feedback$/);

  await page.getByRole("button", { name: "Start text practice" }).click();
  await expect(page).toHaveURL(/\/sessions\/[0-9a-f-]{36}$/);

  const composer = page.getByRole("textbox", { name: "Message" });
  await composer.fill("Hi Sam, thanks for the PR.");
  await composer.press("Enter");

  await expect(page.getByText("Fake reply to: Hi Sam, thanks for the PR.")).toBeVisible();

  await composer.fill("Let's talk about the validation issue.");
  await composer.press("Enter");
  await expect(page.getByText("Turns left: 18")).toBeVisible();

  await page.getByRole("button", { name: "End session" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "End session" }).click();

  await expect(page.getByText(/Session ended/)).toBeVisible();

  await page.getByRole("button", { name: "View your report" }).first().click();
  await expect(page.getByText(/Goal/)).toBeVisible({ timeout: 10000 });

  await expect(page.getByText("/100")).toBeVisible();
  for (const label of [
    "Clarity",
    "Conciseness",
    "Structure",
    "Audience fit",
    "Tone",
    "Confidence",
    "Grammar & vocabulary",
  ]) {
    await expect(page.getByText(label, { exact: true })).toBeVisible();
  }
  await expect(page.getByText("You said")).toBeVisible();
  await expect(page.getByText(/thanks for the PR/).first()).toBeVisible();

  await page.goto("/sessions");
  await expect(page.getByText("Give code review feedback")).toBeVisible();
  await expect(page.getByText("Ended")).toBeVisible();
});

test("delete a session from history", async ({ page }) => {
  await page.goto("/practice/code-review-give-feedback");
  await page.getByRole("button", { name: "Start text practice" }).click();
  await page.waitForURL(/\/sessions\/[0-9a-f-]{36}$/);
  const sessionUrl = page.url();

  await page.goto("/sessions");
  // Other specs share this history (Q1 has a single local user), so scope to this session's row.
  const row = page.locator("li", {
    has: page.locator(`a[href="${new URL(sessionUrl).pathname}"]`),
  });
  await row.getByRole("button", { name: "Delete" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete" }).click();

  await expect(row).not.toBeVisible();

  await page.goto(sessionUrl);
  await expect(page.getByText("We couldn't find that.")).toBeVisible();
});
