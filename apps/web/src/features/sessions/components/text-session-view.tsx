"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { ScenarioDetail } from "@/features/scenarios/api";
import { errorMessage } from "@/lib/api/errors";

import type { SessionDetail } from "../api";
import { useChatStream } from "../hooks/use-chat-stream";
import { useEndSession } from "../hooks/use-end-session";
import { useHint } from "../hooks/use-hint";
import { Composer } from "./composer";
import { EndSessionDialog } from "./end-session-dialog";
import { HintCallout } from "./hint-callout";
import { SessionHeader } from "./session-header";
import { Transcript } from "./transcript";

export function TextSessionView({
  sessionId,
  session,
  scenario,
}: {
  sessionId: string;
  session: SessionDetail;
  scenario: ScenarioDetail;
}) {
  const chat = useChatStream(sessionId);
  const endSessionMutation = useEndSession(sessionId);
  const hintMutation = useHint(sessionId);
  const [draft, setDraft] = useState("");
  const [hintText, setHintText] = useState<string | null>(null);

  const isActive = session.status === "active";
  const composerDisabled = !isActive || chat.status === "streaming";

  async function handleHint() {
    const result = await hintMutation.mutateAsync();
    setHintText(result.hint);
  }

  return (
    <div className="mx-auto flex h-[calc(100dvh-8rem)] max-w-3xl flex-col">
      <SessionHeader session={session} scenario={scenario} turnsLeft={chat.turnsLeft} />

      <div className="min-h-0 flex-1 py-4">
        <Transcript
          messages={chat.messages}
          streamingText={chat.streamingText}
          status={chat.status}
          errorText={chat.error ? errorMessage(chat.error.code) : null}
          onRetry={() => void chat.retryLast()}
        />
      </div>

      <div className="flex flex-col gap-2 border-t pt-3">
        {!isActive && (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted px-3.5 py-2.5 text-sm">
            <span>
              Session ended. Thanks for practising
              {session.user_turns < 2 ? " — this one was too short for a feedback report." : "."}
            </span>
            <div className="flex items-center gap-2">
              {session.status === "ended" && (
                <Button
                  nativeButton={false}
                  size="sm"
                  variant="outline"
                  render={<Link href={`/sessions/${sessionId}/report`} />}
                >
                  View your report
                </Button>
              )}
              <Button nativeButton={false} size="sm" render={<Link href="/practice" />}>
                Back to practice
              </Button>
            </div>
          </div>
        )}

        {isActive && hintText && (
          <HintCallout
            hint={hintText}
            onUse={() => {
              setDraft(hintText);
              setHintText(null);
            }}
            onDismiss={() => setHintText(null)}
          />
        )}

        {isActive && (
          <div className="flex items-center justify-between">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => void handleHint()}
              disabled={hintMutation.isPending || composerDisabled}
            >
              Hint
            </Button>
            <EndSessionDialog
              userTurns={session.user_turns}
              onConfirm={() => endSessionMutation.mutate()}
              disabled={endSessionMutation.isPending}
            />
          </div>
        )}

        <Composer
          value={draft}
          onValueChange={setDraft}
          onSend={(content) => void chat.send(content)}
          disabled={composerDisabled}
          maxChars={session.limits.max_message_chars}
        />
      </div>
    </div>
  );
}
