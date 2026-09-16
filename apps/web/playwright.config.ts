import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

import { BACKEND_ENV, ROOT_DIR, WEB_ENV, WEB_URL } from "./e2e/env";

const FAKE_AUDIO = path.resolve(__dirname, "e2e/fixtures/hello.wav");

// Playwright starts web servers before globalSetup, so the database reset runs first in the API
// command: nothing can connect to the old schema.
const PREPARE_BACKEND = [
  "uv run python -m app.cli reset-db --force",
  "uv run python -m app.cli flush-redis",
].join(" && ");

export default defineConfig({
  testDir: "./e2e",
  // Q1 has a single local user, so specs share data and must run one at a time.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: WEB_URL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          args: [
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            `--use-file-for-fake-audio-capture=${FAKE_AUDIO}`,
          ],
        },
      },
    },
  ],
  // Playwright stops each server by killing its process group (SIGKILL). Don't switch the
  // worker to a SIGTERM graceful shutdown: taskiq can hang when `uv run` forwards a second SIGTERM.
  webServer: [
    {
      name: "api",
      command: `(cd apps/api && ${PREPARE_BACKEND}) && pnpm run dev:api`,
      cwd: ROOT_DIR,
      env: BACKEND_ENV,
      url: "http://127.0.0.1:8100/api/v1/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      name: "worker",
      command: "pnpm run dev:worker",
      cwd: ROOT_DIR,
      env: BACKEND_ENV,
      wait: { stderr: /Listening started/ },
      timeout: 60_000,
    },
    {
      name: "web",
      command: "pnpm --filter web dev --port 3100",
      cwd: ROOT_DIR,
      env: WEB_ENV,
      url: WEB_URL,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
