"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError, errorMessage } from "@/lib/api/errors";

import { endSession } from "../api";
import { sessionKeys } from "../query-keys";

export function useEndSession(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => endSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sessionKeys.detail(sessionId) });
    },
    onError: (error) => {
      const code = error instanceof ApiError ? error.code : "internal_error";
      toast.error(errorMessage(code));
    },
  });
}
