"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { type Health, useHealth } from "@/features/health/use-health";
import { cn } from "@/lib/utils";

const CHECK_LABELS: Record<keyof Health["checks"], string> = {
  database: "database",
  redis: "job queue (Redis)",
  llm: "AI model",
};

type Status = "checking" | "ok" | "degraded" | "offline";

const DOT: Record<Status, string> = {
  checking: "bg-muted-foreground/50",
  ok: "bg-primary",
  degraded: "bg-highlight",
  offline: "bg-destructive",
};

export function HealthBadge({ className }: { className?: string }) {
  const { data, isError, isPending } = useHealth();

  const status: Status = isPending ? "checking" : isError ? "offline" : data.status;
  const unavailable = data
    ? (Object.keys(data.checks) as (keyof Health["checks"])[])
        .filter((key) => data.checks[key] !== "ok")
        .map((key) => CHECK_LABELS[key])
    : [];

  const label =
    status === "degraded"
      ? `API degraded. Unavailable: ${unavailable.join(", ")}`
      : status === "offline"
        ? "API offline. Start it with make dev."
        : status === "ok"
          ? "API connected. Database, job queue and AI model are reachable."
          : "Checking the API";

  return (
    <Tooltip>
      <TooltipTrigger
        render={<span />}
        tabIndex={0}
        aria-label={label}
        className={cn(
          "inline-flex items-center gap-2 rounded-md px-2 py-1 text-sm text-muted-foreground",
          "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
          className,
        )}
      >
        <span aria-hidden className={cn("size-2 rounded-full", DOT[status])} />
        <span>{status === "checking" ? "API: checking…" : `API: ${status}`}</span>
      </TooltipTrigger>
      <TooltipContent side="top">{label}</TooltipContent>
    </Tooltip>
  );
}
