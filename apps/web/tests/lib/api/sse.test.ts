import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import type { ChatStreamEvent } from "@/lib/api/events";
import { postSse } from "@/lib/api/sse";

function streamResponse(chunks: string[], status = 200) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream, { status });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("postSse", () => {
  it("parses an event split across multiple chunks", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(streamResponse(["event: delta\nd", 'ata: {"text":"hi"}', "\n\n"])),
    );
    const events: ChatStreamEvent[] = [];

    await postSse("/sessions/1/messages", { content: "hi" }, { onEvent: (e) => events.push(e) });

    expect(events).toEqual([{ event: "delta", data: { text: "hi" } }]);
  });

  it("parses multiple events delivered in one chunk", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          streamResponse([
            'event: delta\ndata: {"text":"a"}\n\nevent: delta\ndata: {"text":"b"}\n\n',
          ]),
        ),
    );
    const events: ChatStreamEvent[] = [];

    await postSse("/sessions/1/messages", { content: "hi" }, { onEvent: (e) => events.push(e) });

    expect(events).toEqual([
      { event: "delta", data: { text: "a" } },
      { event: "delta", data: { text: "b" } },
    ]);
  });

  it("throws ApiError for a non-2xx JSON response instead of streaming", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ error: { code: "session_not_active", message: "Ended." } }),
            { status: 409 },
          ),
        ),
    );
    const onEvent = vi.fn();

    await expect(
      postSse("/sessions/1/messages", { content: "hi" }, { onEvent }),
    ).rejects.toMatchObject({
      code: "session_not_active",
      status: 409,
    } satisfies Partial<ApiError>);
    expect(onEvent).not.toHaveBeenCalled();
  });

  it("stops reading and does not throw when aborted", async () => {
    const controller = new AbortController();
    const encoder = new TextEncoder();
    let enqueueSecond: (() => void) | undefined;
    const stream = new ReadableStream<Uint8Array>({
      start(streamController) {
        streamController.enqueue(encoder.encode('event: delta\ndata: {"text":"a"}\n\n'));
        enqueueSecond = () => {
          streamController.enqueue(encoder.encode('event: delta\ndata: {"text":"b"}\n\n'));
          streamController.close();
        };
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream, { status: 200 })));
    const events: ChatStreamEvent[] = [];

    const promise = postSse(
      "/sessions/1/messages",
      { content: "hi" },
      { signal: controller.signal, onEvent: (e) => events.push(e) },
    );
    await vi.waitFor(() => expect(events).toHaveLength(1));
    controller.abort();
    enqueueSecond?.();

    await expect(promise).resolves.toBeUndefined();
    expect(events).toEqual([{ event: "delta", data: { text: "a" } }]);
  });
});
