import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // E2E runs its own server next to `pnpm dev`; separate build dirs keep them from clashing.
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  // The sidebar's health badge sits bottom-left, where the indicator would cover it.
  devIndicators: { position: "bottom-right" },
};

export default nextConfig;
