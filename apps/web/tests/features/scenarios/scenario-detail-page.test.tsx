import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ScenarioDetail } from "@/features/scenarios/api";
import { ScenarioDetailView } from "@/features/scenarios/components/scenario-detail-view";

import { API, server } from "../../msw";
import { renderWithProviders } from "../../render";

const { push, toastError } = vi.hoisted(() => ({ push: vi.fn(), toastError: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));
vi.mock("sonner", () => ({ toast: { error: toastError } }));

function detail(overrides: Partial<ScenarioDetail> = {}): ScenarioDetail {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    slug: "explain-tech-debt-to-pm",
    title: "Explain tech debt to your PM",
    category: "stakeholder_communication",
    difficulty: 2,
    summary: "Make the case for time to refactor the payments module.",
    recommended_mode: "either",
    is_custom: false,
    persona: {
      name: "Dana",
      role: "Product manager",
      personality: "Friendly but busy.",
      goals: "Ship features.",
    },
    user_objective: "Convince Dana to reserve time for refactoring.",
    opening_line: "Hey! You wanted to talk?",
    success_criteria: ["States the request clearly", "Explains the business impact"],
    ...overrides,
  };
}

function detailReturns(body: ScenarioDetail) {
  server.use(http.get(`${API}/scenarios/:slug`, () => HttpResponse.json(body)));
}

beforeEach(() => {
  push.mockClear();
  toastError.mockClear();
});

describe("ScenarioDetailView", () => {
  it("shows the persona and success criteria", async () => {
    detailReturns(detail());

    renderWithProviders(<ScenarioDetailView slug="explain-tech-debt-to-pm" />);

    expect(await screen.findByText("Dana")).toBeInTheDocument();
    expect(screen.getByText("Product manager")).toBeInTheDocument();
    expect(screen.getByText("States the request clearly")).toBeInTheDocument();
    expect(screen.getByText("Explains the business impact")).toBeInTheDocument();
    expect(screen.getByText("Convince Dana to reserve time for refactoring.")).toBeInTheDocument();
  });

  it("starts a text session and navigates to it", async () => {
    const user = userEvent.setup();
    detailReturns(detail());
    server.use(
      http.post(`${API}/sessions`, async ({ request }) => {
        const body = (await request.json()) as { scenario_id: string; mode: string };
        expect(body.mode).toBe("text");
        return HttpResponse.json({ id: "session-1" }, { status: 201 });
      }),
    );

    renderWithProviders(<ScenarioDetailView slug="explain-tech-debt-to-pm" />);
    await screen.findByText("Dana");

    await user.click(screen.getByRole("button", { name: "Start text practice" }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/sessions/session-1"));
  });

  it("shows a toast when starting a session fails", async () => {
    const user = userEvent.setup();
    detailReturns(detail());
    server.use(
      http.post(`${API}/sessions`, () =>
        HttpResponse.json({ error: { code: "not_found", message: "Not found." } }, { status: 404 }),
      ),
    );

    renderWithProviders(<ScenarioDetailView slug="explain-tech-debt-to-pm" />);
    await screen.findByText("Dana");

    await user.click(screen.getByRole("button", { name: "Start text practice" }));

    await vi.waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(push).not.toHaveBeenCalled();
  });

  it("starts a voice session and navigates to it", async () => {
    const user = userEvent.setup();
    detailReturns(detail());
    server.use(
      http.post(`${API}/sessions`, async ({ request }) => {
        const body = (await request.json()) as { scenario_id: string; mode: string };
        expect(body.mode).toBe("voice");
        return HttpResponse.json({ id: "session-2" }, { status: 201 });
      }),
    );

    renderWithProviders(<ScenarioDetailView slug="explain-tech-debt-to-pm" />);
    await screen.findByText("Dana");

    await user.click(screen.getByRole("button", { name: "Start voice practice" }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/sessions/session-2"));
  });
});
