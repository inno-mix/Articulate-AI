"use client";

import { ChevronDownIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import type { ScenarioDetail } from "@/features/scenarios/api";
import { cn } from "@/lib/utils";

import type { SessionDetail } from "../api";

export function SessionHeader({
  session,
  scenario,
  turnsLeft,
}: {
  session: SessionDetail;
  scenario: ScenarioDetail;
  turnsLeft: number;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
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
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        className="mt-3 flex items-center gap-1 text-sm text-primary outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        <ChevronDownIcon
          className={cn("size-4 transition-transform", expanded && "rotate-180")}
          aria-hidden
        />
        Your goal
      </button>
      {expanded && (
        <div className="mt-2 space-y-2 text-sm text-muted-foreground">
          <p>{scenario.user_objective}</p>
          <ul className="space-y-1">
            {scenario.success_criteria.map((criterion) => (
              <li key={criterion}>• {criterion}</li>
            ))}
          </ul>
        </div>
      )}
      {session.status !== "active" && (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium text-muted-foreground">This session has ended.</p>
          {session.status === "ended" && (
            <Button
              nativeButton={false}
              size="sm"
              variant="outline"
              render={<Link href={`/sessions/${session.id}/report`} />}
            >
              View your report
            </Button>
          )}
        </div>
      )}
    </header>
  );
}
