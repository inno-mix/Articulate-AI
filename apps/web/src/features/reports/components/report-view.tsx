"use client";

import Link from "next/link";

import { ErrorState } from "@/components/error-state";
import { ScoreNumber } from "@/components/score-number";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useScenario } from "@/features/scenarios/hooks/use-scenario";
import { useStartSession } from "@/features/scenarios/hooks/use-start-session";
import { useSession } from "@/features/sessions/hooks/use-session";
import { ApiError, errorMessage } from "@/lib/api/errors";

import type { ReportOut } from "../api";
import { useNow } from "../hooks/use-now";
import { STILL_WORKING_AFTER_MS, useReport } from "../hooks/use-report";
import { useRetryReport } from "../hooks/use-retry-report";
import { GrammarTable } from "./grammar-table";
import { HighlightCard } from "./highlight-card";
import { SkillRow } from "./skill-row";
import { SpeakingStats } from "./speaking-stats";

const FIVE_MINUTES_MS = 5 * 60 * 1000;
const MODE_LABEL = { text: "Text", voice: "Voice" } as const;
const DATE_FORMAT = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });

function ReportSkeleton() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

function PendingState({
  report,
  onRetry,
  isRetrying,
}: {
  report: ReportOut;
  onRetry: () => void;
  isRetrying: boolean;
}) {
  const now = useNow();
  const elapsedMs = now - new Date(report.created_at).getTime();
  const staleMs = now - new Date(report.updated_at).getTime();
  const stillWorking = elapsedMs > STILL_WORKING_AFTER_MS;
  const stale = staleMs > FIVE_MINUTES_MS;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
      <p className="text-sm text-muted-foreground">
        Analysing your conversation… This can take up to a minute on a local model.
      </p>
      {stillWorking && (
        <p className="text-sm text-muted-foreground">
          Still working. Make sure the worker is running (<code>make dev</code>).
        </p>
      )}
      {stale && (
        <Button type="button" variant="outline" onClick={onRetry} disabled={isRetrying}>
          Try again
        </Button>
      )}
    </div>
  );
}

function FailedState({
  report,
  onRetry,
  isRetrying,
}: {
  report: ReportOut;
  onRetry: () => void;
  isRetrying: boolean;
}) {
  return (
    <div className="space-y-4">
      <p className="text-destructive">{errorMessage(report.error_code ?? "internal_error")}</p>
      <Button type="button" variant="outline" onClick={onRetry} disabled={isRetrying}>
        Try again
      </Button>
    </div>
  );
}

function ReadyState({
  report,
  scenarioId,
  mode,
  onRegenerate,
  isRegenerating,
}: {
  report: ReportOut;
  scenarioId: string;
  mode: "text" | "voice";
  onRegenerate: () => void;
  isRegenerating: boolean;
}) {
  const startSession = useStartSession();
  const scores = report.dimension_scores ?? [];
  const strengths = report.strengths ?? [];
  const improvements = report.improvements ?? [];
  const highlights = report.highlights ?? [];
  const grammarFixes = report.grammar_fixes ?? [];

  return (
    <div className="space-y-6">
      {report.summary && <p className="text-lg">{report.summary}</p>}

      {scores.length > 0 && (
        <section>
          <h2 className="font-heading text-lg font-semibold">Skills</h2>
          <div className="mt-2 divide-y divide-foreground/10">
            {scores.map((s) => (
              <SkillRow
                key={s.dimension}
                dimension={s.dimension}
                score={s.score}
                reason={s.reason}
              />
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-6 sm:grid-cols-2">
        <section>
          <h2 className="font-heading text-lg font-semibold">Strengths</h2>
          <ul className="mt-2 list-disc space-y-1.5 pl-4 text-sm">
            {strengths.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="font-heading text-lg font-semibold">Things to work on</h2>
          <ul className="mt-2 list-disc space-y-1.5 pl-4 text-sm">
            {improvements.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <SpeakingStats metrics={report.voice_metrics} />

      {highlights.length > 0 && (
        <section>
          <h2 className="font-heading text-lg font-semibold">Moments to improve</h2>
          <div className="mt-2 space-y-3">
            {highlights.map((highlight, index) => (
              <HighlightCard key={index} highlight={highlight} />
            ))}
          </div>
        </section>
      )}

      {grammarFixes.length > 0 && (
        <section>
          <h2 className="font-heading text-lg font-semibold">Grammar</h2>
          <div className="mt-2">
            <GrammarTable fixes={grammarFixes} />
          </div>
        </section>
      )}

      <div className="flex flex-wrap gap-2 border-t pt-4">
        <Button
          type="button"
          onClick={() => startSession.mutate({ scenarioId, mode })}
          disabled={startSession.isPending}
        >
          Practise again
        </Button>
        <Button type="button" variant="outline" onClick={onRegenerate} disabled={isRegenerating}>
          Regenerate report
        </Button>
        <Button nativeButton={false} variant="ghost" render={<Link href="/practice" />}>
          Back to practice
        </Button>
      </div>
    </div>
  );
}

export function ReportView({ sessionId }: { sessionId: string }) {
  const session = useSession(sessionId);
  const scenarioSlug = session.data?.scenario.slug ?? "";
  const scenario = useScenario(scenarioSlug);
  const report = useReport(sessionId);
  const retryReport = useRetryReport(sessionId);

  if (session.isPending || (scenarioSlug && scenario.isPending) || report.isPending) {
    return <ReportSkeleton />;
  }
  if (
    session.isError ||
    scenario.isError ||
    report.isError ||
    !session.data ||
    !scenario.data ||
    !report.data
  ) {
    const failure = session.error ?? scenario.error ?? report.error;
    const code = failure instanceof ApiError ? failure.code : "internal_error";
    return (
      <ErrorState
        message={errorMessage(code)}
        onRetry={() => {
          void session.refetch();
          void scenario.refetch();
          void report.refetch();
        }}
      />
    );
  }

  const data = report.data;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="border-b pb-4">
        <h1 className="font-heading text-2xl font-semibold">{scenario.data.title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {DATE_FORMAT.format(new Date(session.data.started_at))} · {MODE_LABEL[session.data.mode]}
        </p>
        {data.status === "ready" && (
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <ScoreNumber score={data.overall_score ?? 0} />
            <Badge variant={data.objective_met ? "default" : "secondary"}>
              {data.objective_met ? "Goal achieved" : "Goal not yet achieved"}
            </Badge>
          </div>
        )}
      </header>

      {(data.status === "pending" || data.status === "running") && (
        <PendingState
          report={data}
          onRetry={() => retryReport.mutate()}
          isRetrying={retryReport.isPending}
        />
      )}
      {data.status === "failed" && (
        <FailedState
          report={data}
          onRetry={() => retryReport.mutate()}
          isRetrying={retryReport.isPending}
        />
      )}
      {data.status === "ready" && (
        <ReadyState
          report={data}
          scenarioId={scenario.data.id}
          mode={session.data.mode}
          onRegenerate={() => retryReport.mutate()}
          isRegenerating={retryReport.isPending}
        />
      )}
    </div>
  );
}
