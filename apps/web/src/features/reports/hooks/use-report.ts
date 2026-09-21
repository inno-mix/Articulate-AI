"use client";

import { useQuery } from "@tanstack/react-query";

import { getReport } from "../api";
import { reportKeys } from "../query-keys";

const FAST_INTERVAL_MS = 2000;
const SLOW_INTERVAL_MS = 5000;
export const STILL_WORKING_AFTER_MS = 120_000;

export function useReport(sessionId: string) {
  return useQuery({
    queryKey: reportKeys.detail(sessionId),
    queryFn: () => getReport(sessionId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status !== "pending" && status !== "running") return false;
      const createdAt = query.state.data?.created_at;
      const elapsed = createdAt ? Date.now() - new Date(createdAt).getTime() : 0;
      return elapsed < STILL_WORKING_AFTER_MS ? FAST_INTERVAL_MS : SLOW_INTERVAL_MS;
    },
  });
}
