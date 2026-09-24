"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import type { ScenarioDetail } from "@/features/scenarios/api";
import { useSettings } from "@/features/settings/hooks/use-settings";
import type { SessionDetail } from "@/features/sessions/api";
import { EndSessionDialog } from "@/features/sessions/components/end-session-dialog";
import { MessageBubble } from "@/features/sessions/components/message-bubble";
import type { VoiceInputMode } from "@/lib/api/events";
import type { AudioSource } from "@/lib/audio/mic-capture";
import type { AudioSink } from "@/lib/audio/pcm-player";
import type { VoiceSocket } from "@/lib/audio/voice-socket";
import { cn } from "@/lib/utils";

import { useVoiceSession } from "../hooks/use-voice-session";
import { PttButton } from "./ptt-button";
import { VoiceStartScreen } from "./voice-start-screen";

const STATE_LABEL: Record<string, string> = {
  idle: "Ready — hold to talk",
  listening: "Listening…",
  thinking: "Thinking…",
  speaking: "Speaking…",
};

// The 20-minute session cap is server-enforced (voice-and-pronunciation.md §2.4) — not part of
// SessionLimits, so it's a fixed UI constant here rather than a value read from the API.
const SESSION_LIMIT_SECONDS = 20 * 60;

function formatMmSs(totalSeconds: number): string {
  const clamped = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(clamped / 60);
  const seconds = clamped % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function VoiceSessionView({
  sessionId,
  session,
  scenario,
  source,
  sink,
  socketFactory,
}: {
  sessionId: string;
  session: SessionDetail;
  scenario: ScenarioDetail;
  source?: AudioSource;
  sink?: AudioSink;
  socketFactory?: (url: string) => VoiceSocket;
}) {
  const settings = useSettings();
  const [chosenInputMode, setChosenInputMode] = useState<VoiceInputMode | null>(null);
  const inputMode = chosenInputMode ?? settings.data?.voice_input_mode ?? "push_to_talk";

  const voice = useVoiceSession({ sessionId, inputMode, source, sink, socketFactory });

  useEffect(() => {
    if (!voice.paused) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.code === "Space" && !event.repeat) {
        event.preventDefault();
        voice.resume();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- voice.resume is a stable callback
  }, [voice.paused, voice.resume]);

  const allMessages = [...session.messages, ...voice.messages];
  const userTurnsSoFar =
    session.user_turns + voice.messages.filter((m) => m.role === "user").length;
  const turnsLeft = Math.max(0, session.limits.max_user_turns - userTurnsSoFar);

  if (voice.phase === "not_started") {
    return (
      <VoiceStartScreen
        inputMode={inputMode}
        onInputModeChange={setChosenInputMode}
        onStart={() => void voice.start()}
        connecting={false}
      />
    );
  }

  if (voice.phase === "connecting" && voice.messages.length === 0) {
    return (
      <VoiceStartScreen
        inputMode={inputMode}
        onInputModeChange={setChosenInputMode}
        onStart={() => void voice.start()}
        connecting
      />
    );
  }

  if (voice.phase === "failed" && voice.error?.code === "mic_permission_denied") {
    return (
      <div className="mx-auto max-w-md space-y-4 py-12 text-center">
        <h1 className="font-heading text-xl font-semibold">Microphone access needed</h1>
        <p className="text-muted-foreground">{voice.error.message}</p>
        <Button type="button" onClick={() => void voice.start()}>
          Try again
        </Button>
      </div>
    );
  }

  if (voice.phase === "ended") {
    return (
      <div className="mx-auto max-w-md space-y-4 py-12 text-center">
        <h1 className="font-heading text-xl font-semibold">Session ended</h1>
        <p className="text-muted-foreground">Thanks for practising.</p>
        <div className="flex justify-center gap-2">
          <Button nativeButton={false} render={<Link href={`/sessions/${sessionId}/report`} />}>
            View your report
          </Button>
          <Button nativeButton={false} variant="outline" render={<Link href="/practice" />}>
            Back to practice
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-[calc(100dvh-8rem)] max-w-3xl flex-col">
      <header className="border-b pb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-heading text-xl font-semibold">{scenario.title}</h1>
            <p className="text-sm text-muted-foreground">
              {scenario.persona.name} · {scenario.persona.role}
            </p>
          </div>
          <span className="text-sm whitespace-nowrap text-muted-foreground">
            Turns left: {turnsLeft}
          </span>
        </div>
      </header>

      {voice.phase === "failed" && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive">
          <span>Connection lost.</span>
          <Button type="button" size="sm" variant="outline" onClick={() => void voice.reconnect()}>
            Reconnect
          </Button>
        </div>
      )}

      <div aria-live="polite" className="min-h-0 flex-1 overflow-y-auto py-4">
        <div className="flex flex-col gap-3">
          {allMessages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {voice.assistantDraft && (
            <div className="flex justify-start">
              <div className="max-w-[34rem] rounded-2xl bg-card px-4 py-2.5 text-sm leading-relaxed ring-1 ring-foreground/10">
                {voice.assistantDraft}
              </div>
            </div>
          )}
          {voice.interimText && (
            <div className="flex justify-end">
              <div className="max-w-[34rem] rounded-2xl bg-muted px-4 py-2.5 text-sm leading-relaxed text-muted-foreground">
                {voice.interimText}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-col items-center gap-3 border-t pt-4">
        <p aria-live="polite" className="text-sm font-medium">
          {STATE_LABEL[voice.state]}
        </p>

        {voice.paused ? (
          <Button type="button" size="lg" onClick={() => voice.resume()}>
            Paused — tap to continue
          </Button>
        ) : inputMode === "push_to_talk" ? (
          <PttButton
            active={voice.state === "listening"}
            disabled={voice.phase !== "ready"}
            onDown={() => voice.pttDown()}
            onUp={() => voice.pttUp()}
          />
        ) : (
          <div
            aria-hidden
            className={cn(
              "flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 text-xs text-muted-foreground transition-transform",
              voice.state === "listening" && "animate-pulse",
            )}
            style={{ transform: `scale(${1 + Math.min(voice.level, 1) * 0.3})` }}
          >
            Listening
          </div>
        )}

        <div className="flex w-full items-center justify-between text-xs text-muted-foreground">
          <span>
            {formatMmSs(voice.elapsedSeconds)} / {formatMmSs(SESSION_LIMIT_SECONDS)}
          </span>
          <EndSessionDialog
            userTurns={userTurnsSoFar}
            onConfirm={() => void voice.end()}
            disabled={voice.phase !== "ready"}
          />
        </div>
      </div>
    </div>
  );
}
