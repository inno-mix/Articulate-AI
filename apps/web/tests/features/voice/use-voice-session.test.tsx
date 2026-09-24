import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import type { UseVoiceSessionOptions } from "@/features/voice/hooks/use-voice-session";
import { useVoiceSession } from "@/features/voice/hooks/use-voice-session";
import { VoiceSocket } from "@/lib/audio/voice-socket";

import { MockWebSocket } from "../../lib/audio/mock-websocket";
import { DeniedAudioSource, FakeAudioSink, FakeAudioSource } from "./fakes";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function fakeSocketFactory() {
  return (url: string) => new VoiceSocket(url, MockWebSocket as unknown as typeof WebSocket);
}

async function setUpConnected(overrides: Partial<UseVoiceSessionOptions> = {}) {
  MockWebSocket.instances = [];
  const source = overrides.source ?? new FakeAudioSource();
  const sink = overrides.sink ?? new FakeAudioSink();

  const { result } = renderHook(
    () =>
      useVoiceSession({
        sessionId: "session-1",
        inputMode: "push_to_talk",
        socketFactory: fakeSocketFactory(),
        ...overrides,
        source,
        sink,
      }),
    { wrapper },
  );

  act(() => {
    void result.current.start();
  });
  await waitFor(() => expect(MockWebSocket.instances).toHaveLength(1));
  const mock = MockWebSocket.instances[0];
  act(() => mock.triggerOpen());
  await waitFor(() => expect(mock.sent).toHaveLength(1));
  act(() =>
    mock.triggerMessage(JSON.stringify({ type: "ready", state: "idle", stt_model: "nova-3" })),
  );
  await waitFor(() => expect(result.current.phase).toBe("ready"));

  return { result, mock, source: source as FakeAudioSource, sink: sink as FakeAudioSink };
}

describe("useVoiceSession", () => {
  it("sends start with the chosen input mode once connected", async () => {
    const { mock } = await setUpConnected({ inputMode: "hands_free" });

    expect(JSON.parse(mock.sent[0] as string)).toEqual({
      type: "start",
      input_mode: "hands_free",
    });
  });

  it("only forwards mic audio while the server says listening", async () => {
    const { mock, source } = await setUpConnected();
    const chunk = new Int16Array([1, 2, 3]);

    source.emit(chunk);
    expect(mock.sent).toHaveLength(1); // only the "start" message so far

    act(() => mock.triggerMessage(JSON.stringify({ type: "state", value: "listening" })));
    source.emit(chunk);

    expect(mock.sent).toHaveLength(2);
    expect(mock.sent[1]).toBeInstanceOf(ArrayBuffer);
  });

  it("appends user_turn and assistant_turn messages, clearing the assistant draft", async () => {
    const { result, mock } = await setUpConnected();

    act(() =>
      mock.triggerMessage(
        JSON.stringify({
          type: "user_turn",
          message: { id: "m1", seq: 1, role: "user", content: "hi", source: "voice" },
        }),
      ),
    );
    act(() => mock.triggerMessage(JSON.stringify({ type: "assistant_delta", text: "Hel" })));
    act(() => mock.triggerMessage(JSON.stringify({ type: "assistant_delta", text: "lo!" })));

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.assistantDraft).toBe("Hello!");

    act(() =>
      mock.triggerMessage(
        JSON.stringify({
          type: "assistant_turn",
          message: { id: "m2", seq: 2, role: "assistant", content: "Hello!", source: "voice" },
        }),
      ),
    );

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.assistantDraft).toBe("");
  });

  it("forwards binary frames to the audio sink", async () => {
    const { mock, sink } = await setUpConnected();
    const buffer = new ArrayBuffer(4);

    act(() => mock.triggerMessage(buffer));

    expect(sink.enqueued).toEqual([buffer]);
  });

  it("fails with a mic_permission_denied error when getting the mic fails", async () => {
    const { result } = renderHook(
      () =>
        useVoiceSession({
          sessionId: "session-1",
          inputMode: "push_to_talk",
          source: new DeniedAudioSource(),
          sink: new FakeAudioSink(),
          socketFactory: fakeSocketFactory(),
        }),
      { wrapper },
    );

    await act(async () => {
      await result.current.start();
    });

    expect(result.current.phase).toBe("failed");
    expect(result.current.error?.code).toBe("mic_permission_denied");
  });

  it("fails with connection_lost when the socket closes unexpectedly", async () => {
    const { result, mock } = await setUpConnected();

    act(() => mock.close(1006));

    expect(result.current.phase).toBe("failed");
    expect(result.current.error?.code).toBe("connection_lost");
  });

  it("does not report connection_lost after a graceful session_ended", async () => {
    const { result, mock } = await setUpConnected();

    act(() =>
      mock.triggerMessage(
        JSON.stringify({ type: "session_ended", status: "ended", report_status: "pending" }),
      ),
    );
    act(() => mock.close(1000));

    expect(result.current.phase).toBe("ended");
    expect(result.current.error).toBeNull();
  });

  it("tracks paused, and resume() sends a resume message", async () => {
    const { result, mock } = await setUpConnected();

    act(() => mock.triggerMessage(JSON.stringify({ type: "paused", reason: "no_speech" })));
    expect(result.current.paused).toBe(true);

    act(() => result.current.resume());

    expect(JSON.parse(mock.sent.at(-1) as string)).toEqual({ type: "resume" });
  });
});
