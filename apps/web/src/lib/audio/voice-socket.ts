import type { VoiceClientMessage, VoiceServerJsonEvent } from "@/lib/api/events";

export type { VoiceClientMessage };
export type VoiceServerEvent = VoiceServerJsonEvent | { type: "audio"; data: ArrayBuffer };

const KNOWN_EVENT_TYPES = new Set<VoiceServerJsonEvent["type"]>([
  "ready",
  "state",
  "transcript",
  "user_turn",
  "assistant_delta",
  "assistant_turn",
  "audio_end",
  "limit",
  "error",
  "session_ended",
  "paused",
  "pong",
]);

function isKnownEvent(value: unknown): value is VoiceServerJsonEvent {
  return (
    typeof value === "object" &&
    value !== null &&
    "type" in value &&
    typeof (value as { type: unknown }).type === "string" &&
    KNOWN_EVENT_TYPES.has((value as { type: VoiceServerJsonEvent["type"] }).type)
  );
}

/** Thin wrapper over the voice WebSocket (voice-and-pronunciation.md §2). */
export class VoiceSocket {
  private ws: WebSocket | null = null;
  private readonly listeners = new Set<(event: VoiceServerEvent) => void>();
  closeCode: number | null = null;

  constructor(
    private readonly url: string,
    private readonly WebSocketImpl: typeof WebSocket = WebSocket,
  ) {}

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const ws = new this.WebSocketImpl(this.url);
      ws.binaryType = "arraybuffer";
      ws.onopen = () => resolve();
      ws.onerror = () => reject(new Error("Voice socket connection failed."));
      ws.onmessage = (event) => this.handleMessage(event);
      ws.onclose = (event) => {
        this.closeCode = event.code;
      };
      this.ws = ws;
    });
  }

  private handleMessage(event: MessageEvent): void {
    if (event.data instanceof ArrayBuffer) {
      this.notify({ type: "audio", data: event.data });
      return;
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(event.data as string);
    } catch {
      console.warn("voice socket: received a non-JSON text frame", event.data);
      return;
    }

    if (!isKnownEvent(parsed)) {
      console.warn("voice socket: ignoring unknown event", parsed);
      return;
    }

    this.notify(parsed);
  }

  private notify(event: VoiceServerEvent): void {
    for (const listener of this.listeners) listener(event);
  }

  send(message: VoiceClientMessage): void {
    this.ws?.send(JSON.stringify(message));
  }

  /** Sends only `chunk`'s own bytes, never the whole (possibly shared) backing buffer. */
  sendAudio(chunk: Int16Array): void {
    const bytes = new Uint8Array(chunk.buffer, chunk.byteOffset, chunk.byteLength);
    this.ws?.send(bytes.slice().buffer);
  }

  onEvent(cb: (event: VoiceServerEvent) => void): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  close(): void {
    this.ws?.close();
  }
}
