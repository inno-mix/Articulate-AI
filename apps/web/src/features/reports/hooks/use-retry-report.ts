"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError, errorMessage } from "@/lib/api/errors";

import { retryReport } from "../api";
import { reportKeys } from "../query-keys";

export function useRetryReport(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => retryReport(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: reportKeys.detail(sessionId) });
    },
    onError: (error) => {
      const code = error instanceof ApiError ? error.code : "internal_error";
      toast.error(errorMessage(code));
    },
  });
}
