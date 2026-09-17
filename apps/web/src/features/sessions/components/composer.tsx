"use client";

import { SendHorizonalIcon } from "lucide-react";
import type { KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function Composer({
  value,
  onValueChange,
  onSend,
  disabled,
  maxChars,
}: {
  value: string;
  onValueChange: (value: string) => void;
  onSend: (content: string) => void;
  disabled: boolean;
  maxChars: number;
}) {
  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    onValueChange("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Textarea
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        maxLength={maxChars}
        placeholder="Type your reply…"
        aria-label="Message"
        rows={2}
      />
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {value.length}/{maxChars}
        </span>
        <Button type="button" onClick={submit} disabled={disabled || !value.trim()}>
          Send
          <SendHorizonalIcon aria-hidden />
        </Button>
      </div>
    </div>
  );
}
