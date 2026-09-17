import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type ScenarioSummary = components["schemas"]["ScenarioSummary"];
export type ScenarioDetail = components["schemas"]["ScenarioDetail"];
export type ScenarioCategory = components["schemas"]["ScenarioCategory"];
export type RecommendedMode = components["schemas"]["RecommendedMode"];

export type ScenarioFilters = {
  category?: ScenarioCategory;
  difficulty?: number;
  mode?: RecommendedMode;
};

export function listScenarios(filters: ScenarioFilters): Promise<ScenarioSummary[]> {
  return unwrap(api.GET("/api/v1/scenarios", { params: { query: filters } }));
}

export function getScenario(slug: string): Promise<ScenarioDetail> {
  return unwrap(api.GET("/api/v1/scenarios/{slug}", { params: { path: { slug } } }));
}
