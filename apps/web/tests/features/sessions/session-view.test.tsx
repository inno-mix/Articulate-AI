import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ScenarioDetail } from "@/features/scenarios/api";
import type { SessionDetail } from "@/features/sessions/api";
import { SessionView } from "@/features/sessions/components/session-view";

import { API, server } from "../../msw";
import { renderWithProviders } from "../../render";

function sseResponse(chunks: string[], status = 200) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream, { status, headers: { "Content-Type": "text/event-stream" } });
}

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function session(overrides: Partial<SessionDetail> = {}): SessionDetail {
  return {
    id: "session-1",
    scenario: { slug: "explain-tech-debt-to-pm", title: "Explain tech debt to your PM" },
    mode: "text",
    status: "active",
    started_at: "2026-09-17T10:00:00Z",
    ended_at: null,
    user_turns: 0,
    messages: [
      {
        id: "msg-0",
        seq: 0,
        role: "assistant",
        content: "Hey! You wanted to talk?",
        source: "text",
        created_at: "2026-09-17T10:00:00Z",
      },
    ],
    limits: { max_user_turns: 20, max_message_chars: 1000 },
    ...overrides,
  };
}

function scenarioDetail(overrides: Partial<ScenarioDetail> = {}): ScenarioDetail {
  return {
    id: "scenario-1",
    slug: "explain-tech-debt-to-pm",
    title: "Explain tech debt to your PM",
    category: "stakeholder_communication",
    difficulty: 2,
    summary: "Make the case for refactoring.",
    recommended_mode: "either",
    is_custom: false,
    persona: {
      name: "Dana",
      role: "Product manager",
      personality: "Friendly but busy.",
      goals: "Ship features.",
    },
    user_objective: "Convince Dana.",
    opening_line: "Hey! You wanted to talk?",
    success_criteria: ["States the request clearly"],
    ...overrides,
  };
}

function mockSessionAndScenario(sessionOverrides: Partial<SessionDetail> = {}) {
  server.use(
    http.get(`${API}/sessions/:id`, () => HttpResponse.json(session(sessionOverrides))),
    http.get(`${API}/scenarios/:slug`, () => HttpResponse.json(scenarioDetail())),
  );
}

beforeEach(() => {
  vi.stubGlobal("scrollTo", vi.fn());
});

describe("SessionView", () => {
  it("shows streaming text incrementally, then a saved message, and disables the composer meanwhile", async () => {
    const user = userEvent.setup();
    mockSessionAndScenario();
    server.use(
      http.post(`${API}/sessions/:id/messages`, () =>
        sseResponse([
          sse("user_message", {
            id: "msg-1",
            seq: 1,
            role: "user",
            content: "Hi Dana",
            source: "text",
            created_at: "2026-09-17T10:01:00Z",
          }),
          sse("delta", { text: "Sure, " }),
          sse("delta", { text: "go ahead." }),
          sse("assistant_message", {
            id: "msg-2",
            seq: 2,
            role: "assistant",
            content: "Sure, go ahead.",
            source: "text",
            created_at: "2026-09-17T10:01:05Z",
          }),
          sse("done", { user_turns: 1, turns_left: 19 }),
        ]),
      ),
    );

    renderWithProviders(<SessionView sessionId="session-1" />);
    const composer = await screen.findByRole("textbox", { name: "Message" });
    await user.type(composer, "Hi Dana");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(/Sure, go ahead\./)).toBeInTheDocument();
    expect(composer).not.toBeDisabled();
    expect(screen.getByText("Turns left: 19")).toBeInTheDocument();
  });

  it("sends on Enter and inserts a newline on Shift+Enter", async () => {
    const user = userEvent.setup();
    mockSessionAndScenario();
    let requestCount = 0;
    server.use(
      http.post(`${API}/sessions/:id/messages`, () => {
        requestCount += 1;
        return sseResponse([
          sse("user_message", {
            id: "msg-1",
            seq: 1,
            role: "user",
            content: "hi",
            source: "text",
            created_at: "2026-09-17T10:01:00Z",
          }),
          sse("assistant_message", {
            id: "msg-2",
            seq: 2,
            role: "assistant",
            content: "ok",
            source: "text",
            created_at: "2026-09-17T10:01:05Z",
          }),
          sse("done", { user_turns: 1, turns_left: 19 }),
        ]);
      }),
    );

    renderWithProviders(<SessionView sessionId="session-1" />);
    const composer = await screen.findByRole("textbox", { name: "Message" });

    await user.type(composer, "line one");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    expect(composer).toHaveValue("line one\n");
    expect(requestCount).toBe(0);

    await user.type(composer, "{Enter}");
    await waitFor(() => expect(requestCount).toBe(1));
  });

  it("shows Try again on a stream error, and resends the same content", async () => {
    const user = userEvent.setup();
    mockSessionAndScenario();
    const received: string[] = [];
    server.use(
      http.post(`${API}/sessions/:id/messages`, async ({ request }) => {
        const body = (await request.json()) as { content: string };
        received.push(body.content);
        if (received.length === 1) {
          return sseResponse([
            sse("user_message", {
              id: "msg-1",
              seq: 1,
              role: "user",
              content: body.content,
              source: "text",
              created_at: "2026-09-17T10:01:00Z",
            }),
            sse("error", { code: "llm_unavailable", message: "The AI model is unavailable." }),
          ]);
        }
        return sseResponse([
          sse("user_message", {
            id: "msg-3",
            seq: 3,
            role: "user",
            content: body.content,
            source: "text",
            created_at: "2026-09-17T10:02:00Z",
          }),
          sse("assistant_message", {
            id: "msg-4",
            seq: 4,
            role: "assistant",
            content: "Got it now.",
            source: "text",
            created_at: "2026-09-17T10:02:05Z",
          }),
          sse("done", { user_turns: 2, turns_left: 18 }),
        ]);
      }),
    );

    renderWithProviders(<SessionView sessionId="session-1" />);
    const composer = await screen.findByRole("textbox", { name: "Message" });
    await user.type(composer, "Hi Dana{Enter}");

    const retry = await screen.findByRole("button", { name: "Try again" });
    await user.click(retry);

    expect(await screen.findByText("Got it now.")).toBeInTheDocument();
    expect(received).toEqual(["Hi Dana", "Hi Dana"]);
  });

  it("fills the composer when the hint's 'Use this' is clicked", async () => {
    const user = userEvent.setup();
    mockSessionAndScenario();
    server.use(
      http.post(`${API}/sessions/:id/hint`, () =>
        HttpResponse.json({ hint: "Ask if now is a good time." }),
      ),
    );

    renderWithProviders(<SessionView sessionId="session-1" />);
    await user.click(await screen.findByRole("button", { name: "Hint" }));

    const useThis = await screen.findByRole("button", { name: "Use this" });
    await user.click(useThis);

    expect(screen.getByRole("textbox", { name: "Message" })).toHaveValue(
      "Ask if now is a good time.",
    );
  });

  it("warns that a short session won't get a report before ending", async () => {
    const user = userEvent.setup();
    mockSessionAndScenario({ user_turns: 1 });

    renderWithProviders(<SessionView sessionId="session-1" />);
    await user.click(await screen.findByRole("button", { name: "End session" }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText(/No feedback report will be created for very short sessions/),
    ).toBeInTheDocument();
  });

  it("disables the composer for an already-ended session", async () => {
    mockSessionAndScenario({ status: "ended", ended_at: "2026-09-17T10:05:00Z" });

    renderWithProviders(<SessionView sessionId="session-1" />);

    const composer = await screen.findByRole("textbox", { name: "Message" });
    expect(composer).toBeDisabled();
    expect(screen.getByText(/Session ended/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "End session" })).not.toBeInTheDocument();
  });
});
