import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type Health = components["schemas"]["HealthOut"];

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => unwrap(api.GET("/api/v1/health")),
    refetchInterval: 30_000,
  });
}
