"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError, errorMessage } from "@/lib/api/errors";

import { deleteSession } from "../api";
import { sessionKeys } from "../query-keys";

export function useDeleteSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => deleteSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sessionKeys.all });
    },
    onError: (error) => {
      const code = error instanceof ApiError ? error.code : "internal_error";
      toast.error(errorMessage(code));
    },
  });
}
