import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ScenarioDetail } from "@/features/scenarios/api";
import type { ReportOut } from "@/features/reports/api";
import { ReportView } from "@/features/reports/components/report-view";
import type { SessionDetail } from "@/features/sessions/api";

import { API, server } from "../../msw";
import { renderWithProviders } from "../../render";

const { push, toastError } = vi.hoisted(() => ({ push: vi.fn(), toastError: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));
vi.mock("sonner", () => ({ toast: { error: toastError } }));

function session(overrides: Partial<SessionDetail> = {}): SessionDetail {
  return {
    id: "session-1",
    scenario: { slug: "code-review-give-feedback", title: "Give code review feedback" },
    mode: "text",
    status: "ended",
    started_at: "2026-09-22T10:00:00Z",
    ended_at: "2026-09-22T10:10:00Z",
    user_turns: 3,
    overall_score: 89,
    messages: [],
    limits: { max_user_turns: 20, max_message_chars: 1000 },
    ...overrides,
  };
}

function scenarioDetail(overrides: Partial<ScenarioDetail> = {}): ScenarioDetail {
  return {
    id: "scenario-1",
    slug: "code-review-give-feedback",
    title: "Give code review feedback",
    category: "code_review",
    difficulty: 1,
    summary: "Explain two problems in a PR kindly.",
    recommended_mode: "text",
    is_custom: false,
    persona: {
      name: "Sam",
      role: "Junior developer",
      personality: "Eager.",
      goals: "Get this PR merged.",
    },
    user_objective: "Explain two problems kindly.",
    opening_line: "Hey, thanks for reviewing my PR!",
    success_criteria: ["Names both problems"],
    ...overrides,
  };
}

const DIMENSIONS = [
  "clarity",
  "conciseness",
  "structure",
  "audience_fit",
  "tone",
  "confidence",
  "grammar_vocabulary",
];

function report(overrides: Partial<ReportOut> = {}): ReportOut {
  return {
    status: "ready",
    error_code: null,
    overall_score: 89,
    objective_met: true,
    summary: "Clear, kind, and specific feedback.",
    dimension_scores: DIMENSIONS.map((dimension) => ({
      dimension,
      score: 4,
      reason: `Good ${dimension.replace("_", " ")}.`,
    })),
    strengths: ["Named both problems specifically."],
    improvements: ["Could suggest a concrete fix."],
    highlights: [
      {
        message_id: "msg-1",
        quote: "thanks for the PR",
        issue: "Friendly but vague.",
        better_version: "Thanks for the PR — I have two things to flag.",
      },
    ],
    grammar_fixes: [],
    voice_metrics: null,
    rubric_version: "v1",
    llm_model: "llama3.2:latest",
    created_at: "2026-09-22T10:10:01Z",
    updated_at: "2026-09-22T10:10:01Z",
    completed_at: "2026-09-22T10:10:44Z",
    ...overrides,
  };
}

function mockSessionAndScenario() {
  server.use(
    http.get(`${API}/sessions/:id`, () => HttpResponse.json(session())),
    http.get(`${API}/scenarios/:slug`, () => HttpResponse.json(scenarioDetail())),
  );
}

beforeEach(() => {
  push.mockClear();
  toastError.mockClear();
});

describe("ReportView", () => {
  it("shows pending state text", async () => {
    mockSessionAndScenario();
    server.use(
      http.get(`${API}/sessions/:id/report`, () =>
        HttpResponse.json(
          report({
            status: "pending",
            overall_score: null,
            objective_met: null,
            summary: null,
            dimension_scores: null,
            strengths: null,
            improvements: null,
            highlights: null,
            grammar_fixes: null,
            completed_at: null,
          }),
        ),
      ),
    );

    renderWithProviders(<ReportView sessionId="session-1" />);

    expect(await screen.findByText(/Analysing your conversation/)).toBeInTheDocument();
  });

  it("shows Try again on a pending report whose updated_at is 6 minutes old", async () => {
    mockSessionAndScenario();
    const staleTimestamp = new Date(Date.now() - 6 * 60 * 1000).toISOString();
    server.use(
      http.get(`${API}/sessions/:id/report`, () =>
        HttpResponse.json(
          report({
            status: "pending",
            overall_score: null,
            objective_met: null,
            summary: null,
            dimension_scores: null,
            strengths: null,
            improvements: null,
            highlights: null,
            grammar_fixes: null,
            completed_at: null,
            created_at: staleTimestamp,
            updated_at: staleTimestamp,
          }),
        ),
      ),
    );

    renderWithProviders(<ReportView sessionId="session-1" />);

    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("switches to ready once the report is done", { timeout: 10000 }, async () => {
    mockSessionAndScenario();
    let callCount = 0;
    server.use(
      http.get(`${API}/sessions/:id/report`, () => {
        callCount += 1;
        if (callCount === 1) {
          return HttpResponse.json(
            report({
              status: "pending",
              overall_score: null,
              objective_met: null,
              summary: null,
              dimension_scores: null,
              strengths: null,
              improvements: null,
              highlights: null,
              grammar_fixes: null,
              completed_at: null,
            }),
          );
        }
        return HttpResponse.json(report());
      }),
    );

    renderWithProviders(<ReportView sessionId="session-1" />);
    await screen.findByText(/Analysing your conversation/);

    expect(
      await screen.findByText("Clear, kind, and specific feedback.", {}, { timeout: 8000 }),
    ).toBeInTheDocument();
  });

  it("shows mapped text for a failed report and retries on click", async () => {
    const user = userEvent.setup();
    mockSessionAndScenario();
    let retried = false;
    server.use(
      http.get(`${API}/sessions/:id/report`, () =>
        HttpResponse.json(
          retried
            ? report({ status: "pending", completed_at: null })
            : report({
                status: "failed",
                error_code: "llm_unavailable",
                overall_score: null,
                objective_met: null,
                summary: null,
                dimension_scores: null,
                strengths: null,
                improvements: null,
                highlights: null,
                grammar_fixes: null,
                completed_at: null,
              }),
        ),
      ),
      http.post(`${API}/sessions/:id/report/retry`, () => {
        retried = true;
        return HttpResponse.json({ status: "pending" }, { status: 202 });
      }),
    );

    renderWithProviders(<ReportView sessionId="session-1" />);

    expect(await screen.findByText(/The AI model isn't reachable/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(retried).toBe(true));
  });

  it("renders every ready-state section", async () => {
    mockSessionAndScenario();
    server.use(
      http.get(`${API}/sessions/:id/report`, () =>
        HttpResponse.json(
          report({
            grammar_fixes: [
              { original: "I am agree", corrected: "I agree", explanation: "Verb form." },
            ],
          }),
        ),
      ),
    );

    renderWithProviders(<ReportView sessionId="session-1" />);

    expect(await screen.findByText("Give code review feedback")).toBeInTheDocument();
    expect(screen.getByText("89")).toBeInTheDocument();
    expect(screen.getByText("Excellent")).toBeInTheDocument();
    expect(screen.getByText("Goal achieved")).toBeInTheDocument();
    expect(screen.getByText("Clear, kind, and specific feedback.")).toBeInTheDocument();
    expect(screen.getByText("Good clarity.")).toBeInTheDocument();
    expect(screen.getByText("Named both problems specifically.")).toBeInTheDocument();
    expect(screen.getByText("Could suggest a concrete fix.")).toBeInTheDocument();
    expect(screen.getByText(/thanks for the PR/)).toBeInTheDocument();
    expect(screen.getByText("Friendly but vague.")).toBeInTheDocument();
    expect(screen.getByText("I am agree")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Practise again" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Regenerate report" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to practice" })).toBeInTheDocument();
  });

  it("hides the grammar table when there are no fixes", async () => {
    mockSessionAndScenario();
    server.use(
      http.get(`${API}/sessions/:id/report`, () =>
        HttpResponse.json(report({ grammar_fixes: [] })),
      ),
    );

    renderWithProviders(<ReportView sessionId="session-1" />);
    await screen.findByText("Give code review feedback");

    expect(screen.queryByText("Grammar")).not.toBeInTheDocument();
  });

  it("labels a skill score for screen readers", async () => {
    mockSessionAndScenario();
    server.use(http.get(`${API}/sessions/:id/report`, () => HttpResponse.json(report())));

    renderWithProviders(<ReportView sessionId="session-1" />);
    await screen.findByText("Give code review feedback");

    expect(screen.getByLabelText("Clarity: 4 out of 5")).toBeInTheDocument();
  });

  it("practises again with the same scenario and mode", async () => {
    const user = userEvent.setup();
    mockSessionAndScenario();
    server.use(
      http.get(`${API}/sessions/:id/report`, () => HttpResponse.json(report())),
      http.post(`${API}/sessions`, async ({ request }) => {
        const body = (await request.json()) as { scenario_id: string; mode: string };
        expect(body.scenario_id).toBe("scenario-1");
        expect(body.mode).toBe("text");
        return HttpResponse.json({ id: "session-2" }, { status: 201 });
      }),
    );

    renderWithProviders(<ReportView sessionId="session-1" />);
    await screen.findByText("Give code review feedback");

    await user.click(screen.getByRole("button", { name: "Practise again" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/sessions/session-2"));
  });
});
