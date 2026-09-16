import path from "node:path";

// E2E runs its own API (8100), web (3100), worker, Redis db 2 and database, so it never touches
// your dev servers or data (docs/guides/testing-strategy.md §4).
export const ROOT_DIR = path.resolve(__dirname, "../../..");
export const API_DIR = path.join(ROOT_DIR, "apps/api");
export const WEB_URL = "http://localhost:3100";
export const API_URL = "http://localhost:8100/api/v1";

export const BACKEND_ENV = {
  APP_ENV: "development",
  API_PORT: "8100",
  DATABASE_URL: "postgresql+asyncpg://articulate:articulate@localhost:5432/articulate_e2e",
  REDIS_URL: "redis://localhost:6379/2",
  CORS_ORIGINS: WEB_URL,
  ALLOWED_HOSTS: "localhost,127.0.0.1",
  FRONTEND_URL: WEB_URL,
  LLM_PROVIDER: "fake",
  STT_PROVIDER: "fake",
  TTS_PROVIDER: "fake",
  PRONUNCIATION_PROVIDER: "fake",
  FAKE_PRONUNCIATION_LOW_WORDS: "cache",
};

export const WEB_ENV = {
  NEXT_DIST_DIR: ".next-e2e",
  NEXT_PUBLIC_API_URL: API_URL,
  NEXT_PUBLIC_WS_URL: "ws://localhost:8100/api/v1",
};
