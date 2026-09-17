"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import type { MessageOut } from "@/lib/api/events";

import type { ChatStreamStatus } from "../hooks/use-chat-stream";
import { MessageBubble } from "./message-bubble";

export function Transcript({
  messages,
  streamingText,
  status,
  errorText,
  onRetry,
}: {
  messages: MessageOut[];
  streamingText: string | null;
  status: ChatStreamStatus;
  errorText: string | null;
  onRetry: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  useEffect(() => {
    const el = containerRef.current;
    if (el && stickToBottom.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, streamingText]);

  function handleScroll() {
    const el = containerRef.current;
    if (!el) return;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      aria-live="polite"
      className="flex h-full flex-col gap-3 overflow-y-auto"
    >
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}

      {status === "streaming" && streamingText !== null && (
        <div className="flex justify-start">
          <div className="max-w-[34rem] rounded-2xl bg-card px-4 py-2.5 text-sm leading-relaxed ring-1 ring-foreground/10">
            {streamingText}
            <span
              aria-hidden
              className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-foreground align-middle"
            />
          </div>
        </div>
      )}

      {status === "error" && errorText && (
        <div className="flex justify-end">
          <div className="flex max-w-[34rem] flex-col items-end gap-1.5 text-sm">
            <p className="text-destructive">{errorText}</p>
            <Button type="button" variant="outline" size="sm" onClick={onRetry}>
              Try again
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
