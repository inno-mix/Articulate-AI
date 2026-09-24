import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import type { ScenarioDetail } from "@/features/scenarios/api";
import type { SessionDetail } from "@/features/sessions/api";
import { VoiceSessionView } from "@/features/voice/components/voice-session-view";
import { VoiceSocket } from "@/lib/audio/voice-socket";

import { MockWebSocket } from "../../lib/audio/mock-websocket";
import { API, server } from "../../msw";
import { renderWithProviders } from "../../render";
import { DeniedAudioSource, FakeAudioSink, FakeAudioSource } from "./fakes";

function session(overrides: Partial<SessionDetail> = {}): SessionDetail {
  return {
    id: "session-1",
    scenario: { slug: "explain-tech-debt-to-pm", title: "Explain tech debt to your PM" },
    mode: "voice",
    status: "active",
    started_at: "2026-09-17T10:00:00Z",
    ended_at: null,
    user_turns: 0,
    messages: [],
    limits: { max_user_turns: 20, max_message_chars: 1000 },
    ...overrides,
  };
}

function scenario(overrides: Partial<ScenarioDetail> = {}): ScenarioDetail {
  return {
    id: "scenario-1",
    slug: "explain-tech-debt-to-pm",
    title: "Explain tech debt to your PM",
    category: "stakeholder_communication",
    difficulty: 2,
    summary: "Make the case for refactoring.",
    recommended_mode: "voice",
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

beforeEach(() => {
  server.use(
    http.get(`${API}/settings`, () =>
      HttpResponse.json({
        default_mode: "voice",
        tts_voice: "aura-2-thalia-en",
        voice_input_mode: "push_to_talk",
      }),
    ),
  );
});

async function startAndConnect() {
  MockWebSocket.instances = [];
  const source = new FakeAudioSource();
  const sink = new FakeAudioSink();
  const user = userEvent.setup();

  renderWithProviders(
    <VoiceSessionView
      sessionId="session-1"
      session={session()}
      scenario={scenario()}
      source={source}
      sink={sink}
      socketFactory={(url) => new VoiceSocket(url, MockWebSocket as unknown as typeof WebSocket)}
    />,
  );

  await user.click(await screen.findByRole("button", { name: "Start voice session" }));
  await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
  const mock = MockWebSocket.instances[0];
  act(() => mock.triggerOpen());
  act(() =>
    mock.triggerMessage(JSON.stringify({ type: "ready", state: "idle", stt_model: "nova-3" })),
  );
  await screen.findByText("Ready — hold to talk");

  return { mock, source, sink };
}

describe("VoiceSessionView", () => {
  it("shows the state indicator text changing as state events arrive", async () => {
    const { mock } = await startAndConnect();

    act(() => mock.triggerMessage(JSON.stringify({ type: "state", value: "thinking" })));
    expect(await screen.findByText("Thinking…")).toBeInTheDocument();

    act(() => mock.triggerMessage(JSON.stringify({ type: "state", value: "speaking" })));
    expect(await screen.findByText("Speaking…")).toBeInTheDocument();
  });

  it("shows a permission-denied message when the mic is unavailable", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <VoiceSessionView
        sessionId="session-1"
        session={session()}
        scenario={scenario()}
        source={new DeniedAudioSource()}
        sink={new FakeAudioSink()}
        socketFactory={(url) => new VoiceSocket(url, MockWebSocket as unknown as typeof WebSocket)}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "Start voice session" }));

    expect(await screen.findByText("Microphone access needed")).toBeInTheDocument();
    expect(screen.getByText(/Microphone access was denied/)).toBeInTheDocument();
  });

  it("shows Connection lost with a Reconnect button on an unexpected close", async () => {
    const { mock } = await startAndConnect();

    act(() => mock.close(1006));

    expect(await screen.findByText("Connection lost.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reconnect" })).toBeInTheDocument();
  });

  it("shows the report link once the session ends", async () => {
    const { mock } = await startAndConnect();

    act(() =>
      mock.triggerMessage(
        JSON.stringify({ type: "session_ended", status: "ended", report_status: "pending" }),
      ),
    );

    const link = await screen.findByRole("button", { name: "View your report" });
    expect(link).toHaveAttribute("href", "/sessions/session-1/report");
  });

  it("shows a continue button while paused, which sends resume", async () => {
    const { mock } = await startAndConnect();

    act(() => mock.triggerMessage(JSON.stringify({ type: "paused", reason: "no_speech" })));
    const continueButton = await screen.findByRole("button", { name: "Paused — tap to continue" });

    const user = userEvent.setup();
    await user.click(continueButton);

    expect(JSON.parse(mock.sent.at(-1) as string)).toEqual({ type: "resume" });
  });
});
