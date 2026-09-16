import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    env: {
      NEXT_PUBLIC_API_URL: "http://localhost:8000/api/v1",
      NEXT_PUBLIC_WS_URL: "ws://localhost:8000/api/v1",
    },
  },
});
