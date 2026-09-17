import { createParser } from "eventsource-parser";

import { API_ORIGIN } from "@/lib/env";

import { ApiError, errorMessage, toApiError } from "./errors";
import type { ChatStreamEvent } from "./events";

/**
 * POSTs to a streaming endpoint (api-contract.md §4) and calls `onEvent` for each SSE event.
 * Throws `ApiError` for a non-2xx response, parsed the same way as a normal JSON error. Resolves
 * quietly (no throw, no further `onEvent` calls) if `signal` is aborted, before or during the
 * stream.
 */
export async function postSse(
  path: string,
  body: unknown,
  opts: { signal?: AbortSignal; onEvent: (event: ChatStreamEvent) => void },
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_ORIGIN}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
      signal: opts.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return;
    throw new ApiError("network_error", errorMessage("network_error"), 0);
  }

  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => undefined);
    throw toApiError(response.status, payload);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = createParser({
    onEvent: (message) => {
      if (!message.event || opts.signal?.aborted) return;
      opts.onEvent({ event: message.event, data: JSON.parse(message.data) } as ChatStreamEvent);
    },
  });

  try {
    while (!opts.signal?.aborted) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.feed(decoder.decode(value, { stream: true }));
    }
  } catch (err) {
    if (opts.signal?.aborted) return;
    throw err;
  }
}
