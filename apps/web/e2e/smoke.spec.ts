import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { expect, test } from "@playwright/test";

import { API_DIR, BACKEND_ENV } from "./env";

const run = promisify(execFile);

test("home shows the app shell and a healthy API", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto("/");

  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText("API: ok")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" }).getByText("Practice")).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test("worker is running", async () => {
  const { stdout } = await run("uv", ["run", "python", "-m", "app.cli", "ping-worker"], {
    cwd: API_DIR,
    env: { ...process.env, ...BACKEND_ENV },
    timeout: 20_000,
  });

  expect(stdout.trim().split("\n").at(-1)).toBe("pong:cli");
});
