import type { ScenarioFilters } from "./api";

export const scenarioKeys = {
  all: ["scenarios"] as const,
  list: (filters: ScenarioFilters) => [...scenarioKeys.all, "list", filters] as const,
  detail: (slug: string) => [...scenarioKeys.all, "detail", slug] as const,
};
