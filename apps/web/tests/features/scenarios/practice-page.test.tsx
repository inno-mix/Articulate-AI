import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PracticePage from "@/app/practice/page";
import type { ScenarioSummary } from "@/features/scenarios/api";

import { API, server } from "../../msw";
import { renderWithProviders } from "../../render";

const { push, mockSearchParams } = vi.hoisted(() => ({
  push: vi.fn(),
  mockSearchParams: { current: new URLSearchParams() },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/practice",
  useSearchParams: () => mockSearchParams.current,
}));

function scenario(overrides: Partial<ScenarioSummary> = {}): ScenarioSummary {
  return {
    id: crypto.randomUUID(),
    slug: "explain-tech-debt-to-pm",
    title: "Explain tech debt to your PM",
    category: "stakeholder_communication",
    difficulty: 2,
    summary: "Make the case for time to refactor the payments module.",
    recommended_mode: "either",
    is_custom: false,
    ...overrides,
  };
}

function scenariosReturn(body: ScenarioSummary[]) {
  server.use(http.get(`${API}/scenarios`, () => HttpResponse.json(body)));
}

beforeEach(() => {
  push.mockClear();
  mockSearchParams.current = new URLSearchParams();
});

describe("PracticePage", () => {
  it("renders a card for every scenario", async () => {
    scenariosReturn([
      scenario({ slug: "one", title: "First scenario" }),
      scenario({ slug: "two", title: "Second scenario" }),
    ]);

    renderWithProviders(<PracticePage />);

    expect(await screen.findByText("First scenario")).toBeInTheDocument();
    expect(screen.getByText("Second scenario")).toBeInTheDocument();
  });

  it("refetches with the category query when the filter changes", async () => {
    const user = userEvent.setup();
    scenariosReturn([scenario()]);

    renderWithProviders(<PracticePage />);
    await screen.findByText("Explain tech debt to your PM");

    await user.click(screen.getByRole("combobox", { name: "Category" }));
    await user.click(await screen.findByRole("option", { name: "Career" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/practice?category=career"));
  });

  it("shows an empty state when no scenarios match", async () => {
    scenariosReturn([]);

    renderWithProviders(<PracticePage />);

    expect(await screen.findByText("No scenarios match these filters")).toBeInTheDocument();
  });

  it("shows an error state with a retry button on failure", async () => {
    const user = userEvent.setup();
    let calls = 0;
    server.use(
      http.get(`${API}/scenarios`, () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({ error: { code: "internal_error", message: "x" } }, { status: 500 })
          : HttpResponse.json([scenario()]);
      }),
    );

    renderWithProviders(<PracticePage />);

    const retry = await screen.findByRole("button", { name: "Try again" });
    await user.click(retry);

    expect(await screen.findByText("Explain tech debt to your PM")).toBeInTheDocument();
  });
});
