import { useQuery } from "@tanstack/react-query";

import { listScenarios, type ScenarioFilters } from "../api";
import { scenarioKeys } from "../query-keys";

export function useScenarios(filters: ScenarioFilters) {
  return useQuery({
    queryKey: scenarioKeys.list(filters),
    queryFn: () => listScenarios(filters),
  });
}
