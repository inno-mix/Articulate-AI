import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { HealthBadge } from "@/components/health-badge";
import type { Health } from "@/features/health/use-health";

import { API, server } from "../msw";
import { renderWithProviders } from "../render";

function healthReturns(body: Health) {
  server.use(http.get(`${API}/health`, () => HttpResponse.json(body)));
}

describe("HealthBadge", () => {
  it("shows ok when every check passes", async () => {
    healthReturns({ status: "ok", checks: { database: "ok", redis: "ok", llm: "ok" } });

    renderWithProviders(<HealthBadge />);

    expect(await screen.findByText("API: ok")).toBeInTheDocument();
  });

  it("shows degraded and names the unavailable checks", async () => {
    healthReturns({
      status: "degraded",
      checks: { database: "ok", redis: "ok", llm: "unavailable" },
    });

    renderWithProviders(<HealthBadge />);

    const badge = await screen.findByText("API: degraded");
    expect(badge.closest("[aria-label]")).toHaveAttribute(
      "aria-label",
      "API degraded. Unavailable: AI model",
    );
  });

  it("shows offline when the API can't be reached", async () => {
    server.use(http.get(`${API}/health`, () => HttpResponse.error()));

    renderWithProviders(<HealthBadge />);

    expect(await screen.findByText("API: offline")).toBeInTheDocument();
  });
});
