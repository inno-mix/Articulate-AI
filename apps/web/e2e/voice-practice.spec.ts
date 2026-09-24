import { expect, test } from "@playwright/test";

test("complete a voice practice session with two push-to-talk turns", async ({ page }) => {
  await page.goto("/practice/standup-update");

  await page.getByRole("button", { name: "Start voice practice" }).click();
  await expect(page).toHaveURL(/\/sessions\/[0-9a-f-]{36}$/);

  await page.getByRole("button", { name: "Start voice session" }).click();
  await expect(page.getByText("Ready — hold to talk")).toBeVisible();

  const talkButton = page.getByRole("button", { name: "Hold to talk" });
  async function pttTurn() {
    await talkButton.hover();
    await page.mouse.down();
    await page.waitForTimeout(1500);
    await page.mouse.up();
  }

  await pttTurn();
  await expect(page.getByText("hello um there", { exact: true })).toHaveCount(1);
  await expect(page.getByText(/Fake reply to: hello um there/)).toHaveCount(1);
  await expect(page.getByText("Ready — hold to talk")).toBeVisible();

  // A report needs at least 2 user turns.
  await pttTurn();
  await expect(page.getByText("hello um there", { exact: true })).toHaveCount(2);
  await expect(page.getByText(/Fake reply to: hello um there/)).toHaveCount(2);
  await expect(page.getByText("Ready — hold to talk")).toBeVisible();

  await page.getByRole("button", { name: "End session" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "End session" }).click();
  await expect(page.getByText(/Session ended/)).toBeVisible();

  await page.getByRole("button", { name: "View your report" }).click();

  await expect(page.getByText("Speaking stats")).toBeVisible({ timeout: 10000 });
  // Each turn's fake transcript has one filler word ("um") out of two non-filler words, so two
  // turns give a filler count of 2 and a rate of 2/(2+2) * 100 = 50.0 per 100 words.
  await expect(page.getByText("2 (50.0 per 100 words)")).toBeVisible();
  await expect(page.getByText("Not enough speech to measure pace yet")).toBeVisible();
});
