"use client";

import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError, errorMessage } from "@/lib/api/errors";

import { getHint } from "../api";

export function useHint(sessionId: string) {
  return useMutation({
    mutationFn: () => getHint(sessionId),
    onError: (error) => {
      const code = error instanceof ApiError ? error.code : "internal_error";
      toast.error(errorMessage(code));
    },
  });
}
