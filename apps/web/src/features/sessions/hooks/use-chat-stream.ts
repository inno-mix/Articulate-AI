"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ApiError, errorMessage } from "@/lib/api/errors";
import type { MessageOut } from "@/lib/api/events";
import { postSse } from "@/lib/api/sse";

import { useSession } from "./use-session";

export type ChatStreamStatus = "idle" | "streaming" | "error";

export function useChatStream(sessionId: string) {
  const session = useSession(sessionId);
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [status, setStatus] = useState<ChatStreamStatus>("idle");
  const [turnsLeft, setTurnsLeft] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);
  const seeded = useRef(false);
  const lastContent = useRef<string | null>(null);
  const abortController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (session.data && !seeded.current) {
      seeded.current = true;
      setMessages(session.data.messages);
      setTurnsLeft(session.data.limits.max_user_turns - session.data.user_turns);
    }
  }, [session.data]);

  // Leaving the page (or switching sessions) aborts an in-flight stream.
  useEffect(() => () => abortController.current?.abort(), []);

  const send = useCallback(
    async (content: string) => {
      lastContent.current = content;
      setError(null);
      setStatus("streaming");
      setStreamingText("");
      const controller = new AbortController();
      abortController.current = controller;

      try {
        await postSse(
          `/api/v1/sessions/${sessionId}/messages`,
          { content },
          {
            signal: controller.signal,
            onEvent: (event) => {
              switch (event.event) {
                case "user_message":
                  setMessages((prev) => [...prev, event.data]);
                  break;
                case "delta":
                  setStreamingText((prev) => (prev ?? "") + event.data.text);
                  break;
                case "assistant_message":
                  setMessages((prev) => [...prev, event.data]);
                  setStreamingText(null);
                  break;
                case "done":
                  setTurnsLeft(event.data.turns_left);
                  setStatus("idle");
                  break;
                case "error":
                  setStreamingText(null);
                  setStatus("error");
                  setError(new ApiError(event.data.code, event.data.message, 0));
                  break;
              }
            },
          },
        );
      } catch (caught) {
        // A pre-stream failure (session_not_active, turn_limit_reached, reply_in_progress,
        // network_error, ...): the composer stays usable, so surface it as a toast rather than
        // the inline "Try again" treatment reserved for a failure mid-stream.
        setStreamingText(null);
        setStatus("idle");
        const apiError =
          caught instanceof ApiError
            ? caught
            : new ApiError("internal_error", errorMessage("internal_error"), 0);
        toast.error(errorMessage(apiError.code));
      }
    },
    [sessionId],
  );

  const retryLast = useCallback(async () => {
    if (lastContent.current !== null) {
      await send(lastContent.current);
    }
  }, [send]);

  const abort = useCallback(() => {
    abortController.current?.abort();
    setStatus("idle");
    setStreamingText(null);
  }, []);

  return { messages, streamingText, status, turnsLeft, error, send, retryLast, abort };
}
