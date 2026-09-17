"use client";

import { SearchXIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import type { RecommendedMode, ScenarioCategory, ScenarioFilters } from "@/features/scenarios/api";
import { ScenarioCard } from "@/features/scenarios/components/scenario-card";
import {
  ScenarioFilters as ScenarioFiltersBar,
  type ScenarioFilterValues,
} from "@/features/scenarios/components/scenario-filters";
import { useScenarios } from "@/features/scenarios/hooks/use-scenarios";

function filtersFromSearchParams(params: URLSearchParams): ScenarioFilterValues {
  const difficulty = params.get("difficulty");
  return {
    category: (params.get("category") as ScenarioCategory | null) ?? "all",
    difficulty: difficulty === "1" || difficulty === "2" || difficulty === "3" ? difficulty : "all",
    mode: (params.get("mode") as RecommendedMode | null) ?? "all",
  };
}

function toApiFilters(value: ScenarioFilterValues): ScenarioFilters {
  return {
    ...(value.category !== "all" ? { category: value.category } : {}),
    ...(value.difficulty !== "all" ? { difficulty: Number(value.difficulty) } : {}),
    ...(value.mode !== "all" ? { mode: value.mode } : {}),
  };
}

export default function PracticePage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const filterValues = filtersFromSearchParams(searchParams);
  const { data: scenarios, isPending, isError, refetch } = useScenarios(toApiFilters(filterValues));

  function handleFilterChange(next: ScenarioFilterValues) {
    const params = new URLSearchParams();
    if (next.category !== "all") params.set("category", next.category);
    if (next.difficulty !== "all") params.set("difficulty", next.difficulty);
    if (next.mode !== "all") params.set("mode", next.mode);
    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  return (
    <div className="max-w-5xl">
      <header className="mb-8">
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Practice</h1>
        <p className="mt-2 text-muted-foreground">
          Pick a scenario and rehearse it with an AI partner, by text or by voice.
        </p>
      </header>

      <div className="mb-6">
        <ScenarioFiltersBar value={filterValues} onChange={handleFilterChange} />
      </div>

      {isPending && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-40 rounded-xl" />
          ))}
        </div>
      )}

      {isError && <ErrorState message="Couldn't load scenarios." onRetry={() => refetch()} />}

      {!isPending && !isError && scenarios && scenarios.length === 0 && (
        <EmptyState
          icon={SearchXIcon}
          title="No scenarios match these filters"
          description="Try a different category, difficulty or mode."
        />
      )}

      {!isPending && !isError && scenarios && scenarios.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {scenarios.map((scenario) => (
            <ScenarioCard key={scenario.id} scenario={scenario} />
          ))}
        </div>
      )}
    </div>
  );
}
