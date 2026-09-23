import { afterEach, describe, expect, it, vi } from "vitest";

import { VoiceSocket } from "@/lib/audio/voice-socket";
import type { VoiceServerEvent } from "@/lib/audio/voice-socket";

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  url: string;
  binaryType = "blob";
  readyState = 0;
  sent: unknown[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: unknown): void {
    this.sent.push(data);
  }

  close(code = 1000): void {
    this.readyState = 3;
    this.onclose?.({ code });
  }

  triggerOpen(): void {
    this.readyState = 1;
    this.onopen?.();
  }

  triggerMessage(data: unknown): void {
    this.onmessage?.({ data });
  }
}

afterEach(() => {
  MockWebSocket.instances = [];
  vi.restoreAllMocks();
});

async function connectedSocket(): Promise<{ socket: VoiceSocket; mock: MockWebSocket }> {
  const socket = new VoiceSocket("ws://test/voice", MockWebSocket as unknown as typeof WebSocket);
  const connecting = socket.connect();
  const mock = MockWebSocket.instances[0];
  mock.triggerOpen();
  await connecting;
  return { socket, mock };
}

describe("VoiceSocket", () => {
  it("connects with a binary type of arraybuffer", async () => {
    const { mock } = await connectedSocket();

    expect(mock.url).toBe("ws://test/voice");
    expect(mock.binaryType).toBe("arraybuffer");
  });

  it("JSON-encodes client messages sent through send()", async () => {
    const { socket, mock } = await connectedSocket();

    socket.send({ type: "ptt_down" });

    expect(mock.sent).toEqual([JSON.stringify({ type: "ptt_down" })]);
  });

  it("parses JSON text frames into typed server events", async () => {
    const { socket, mock } = await connectedSocket();
    const events: VoiceServerEvent[] = [];
    socket.onEvent((e) => events.push(e));

    mock.triggerMessage(JSON.stringify({ type: "state", value: "listening" }));
    mock.triggerMessage(JSON.stringify({ type: "user_turn", message: { id: "1" } }));

    expect(events).toEqual([
      { type: "state", value: "listening" },
      { type: "user_turn", message: { id: "1" } },
    ]);
  });

  it("emits binary frames as audio events", async () => {
    const { socket, mock } = await connectedSocket();
    const events: VoiceServerEvent[] = [];
    socket.onEvent((e) => events.push(e));
    const buffer = new ArrayBuffer(4);

    mock.triggerMessage(buffer);

    expect(events).toEqual([{ type: "audio", data: buffer }]);
  });

  it("ignores unknown event types and logs a warning", async () => {
    const { socket, mock } = await connectedSocket();
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const events: VoiceServerEvent[] = [];
    socket.onEvent((e) => events.push(e));

    mock.triggerMessage(JSON.stringify({ type: "totally_unknown" }));

    expect(events).toEqual([]);
    expect(warn).toHaveBeenCalled();
  });

  it("sendAudio sends only the chunk's own bytes, not the whole backing buffer", async () => {
    const { socket, mock } = await connectedSocket();
    const backing = new ArrayBuffer(20);
    const view = new Int16Array(backing, 4, 3);
    view.set([1, 2, 3]);

    socket.sendAudio(view);

    expect(mock.sent).toHaveLength(1);
    const sent = mock.sent[0] as ArrayBuffer;
    expect(sent.byteLength).toBe(6);
    expect(new Int16Array(sent)).toEqual(new Int16Array([1, 2, 3]));
  });

  it("exposes the close code once the socket closes", async () => {
    const { socket, mock } = await connectedSocket();

    expect(socket.closeCode).toBeNull();
    mock.close(4409);

    expect(socket.closeCode).toBe(4409);
  });

  it("onEvent's unsubscribe function stops delivering events", async () => {
    const { socket, mock } = await connectedSocket();
    const events: VoiceServerEvent[] = [];
    const unsubscribe = socket.onEvent((e) => events.push(e));

    unsubscribe();
    mock.triggerMessage(JSON.stringify({ type: "pong" }));

    expect(events).toEqual([]);
  });
});
