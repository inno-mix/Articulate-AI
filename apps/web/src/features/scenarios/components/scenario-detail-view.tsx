"use client";

import { CheckIcon, Loader2Icon } from "lucide-react";

import { DifficultyBadge } from "@/components/difficulty-badge";
import { ErrorState } from "@/components/error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import { useScenario } from "../hooks/use-scenario";
import { useStartSession } from "../hooks/use-start-session";
import { CATEGORY_LABELS } from "../labels";

function DetailSkeleton() {
  return (
    <div className="max-w-3xl space-y-4">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-9 w-96" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

export function ScenarioDetailView({ slug }: { slug: string }) {
  const { data: scenario, isPending, isError, refetch } = useScenario(slug);
  const startSession = useStartSession();

  if (isPending) return <DetailSkeleton />;
  if (isError) {
    return <ErrorState message="Couldn't load this scenario." onRetry={() => refetch()} />;
  }

  const voiceIsPrimary = scenario.recommended_mode === "voice";
  const startingText = startSession.isPending && startSession.variables?.mode === "text";

  return (
    <div className="max-w-3xl">
      <p className="text-sm text-muted-foreground">{CATEGORY_LABELS[scenario.category]}</p>
      <h1 className="mt-1 font-heading text-3xl font-semibold tracking-tight text-balance">
        {scenario.title}
      </h1>
      <div className="mt-3">
        <DifficultyBadge difficulty={scenario.difficulty as 1 | 2 | 3} />
      </div>
      <p className="mt-4 text-muted-foreground">{scenario.summary}</p>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>{scenario.persona.name}</CardTitle>
          <CardDescription>{scenario.persona.role}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{scenario.persona.personality}</p>
        </CardContent>
      </Card>

      <section className="mt-8">
        <h2 className="font-heading text-lg font-medium">Your goal</h2>
        <p className="mt-1.5 text-muted-foreground">{scenario.user_objective}</p>
      </section>

      <section className="mt-6">
        <h2 className="font-heading text-lg font-medium">What good looks like</h2>
        <ul className="mt-2 space-y-1.5">
          {scenario.success_criteria.map((criterion) => (
            <li key={criterion} className="flex gap-2 text-sm text-muted-foreground">
              <CheckIcon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              {criterion}
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-10 flex flex-wrap gap-3">
        <Button
          variant={voiceIsPrimary ? "outline" : "default"}
          disabled={startSession.isPending}
          onClick={() => startSession.mutate({ scenarioId: scenario.id, mode: "text" })}
        >
          {startingText && <Loader2Icon className="animate-spin" aria-hidden />}
          Start text practice
        </Button>
        <Tooltip>
          <TooltipTrigger render={<span tabIndex={0} className="inline-block" />}>
            <Button variant={voiceIsPrimary ? "default" : "outline"} disabled>
              Start voice practice
            </Button>
          </TooltipTrigger>
          <TooltipContent side="top">Voice practice arrives in Phase 3</TooltipContent>
        </Tooltip>
      </div>
    </div>
  );
}
