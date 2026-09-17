import { useQuery } from "@tanstack/react-query";

import { getScenario } from "../api";
import { scenarioKeys } from "../query-keys";

export function useScenario(slug: string) {
  return useQuery({
    queryKey: scenarioKeys.detail(slug),
    queryFn: () => getScenario(slug),
  });
}
