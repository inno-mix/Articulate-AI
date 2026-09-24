"use client";

import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useScenario } from "@/features/scenarios/hooks/use-scenario";
import { VoiceSessionView } from "@/features/voice/components/voice-session-view";
import { ApiError, errorMessage } from "@/lib/api/errors";

import { useSession } from "../hooks/use-session";
import { TextSessionView } from "./text-session-view";

function SessionSkeleton() {
  return (
    <div className="max-w-3xl space-y-4">
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-64 w-full" />
      <Skeleton className="h-20 w-full" />
    </div>
  );
}

/** Dispatches to the text or voice session UI once both the session and scenario are loaded. */
export function SessionView({ sessionId }: { sessionId: string }) {
  const session = useSession(sessionId);
  const scenarioSlug = session.data?.scenario.slug ?? "";
  const scenario = useScenario(scenarioSlug);

  if (session.isPending || (scenarioSlug && scenario.isPending)) {
    return <SessionSkeleton />;
  }
  if (session.isError || scenario.isError || !session.data || !scenario.data) {
    const failure = session.error ?? scenario.error;
    const code = failure instanceof ApiError ? failure.code : "internal_error";
    return (
      <ErrorState
        message={errorMessage(code)}
        onRetry={() => {
          void session.refetch();
          void scenario.refetch();
        }}
      />
    );
  }

  if (session.data.mode === "voice") {
    return (
      <VoiceSessionView sessionId={sessionId} session={session.data} scenario={scenario.data} />
    );
  }

  return <TextSessionView sessionId={sessionId} session={session.data} scenario={scenario.data} />;
}
