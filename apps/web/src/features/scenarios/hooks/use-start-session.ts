"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { api, unwrap } from "@/lib/api/client";
import { ApiError, errorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema";

type PracticeMode = components["schemas"]["PracticeMode"];
type SessionDetail = components["schemas"]["SessionDetail"];

export function useStartSession() {
  const router = useRouter();

  return useMutation<SessionDetail, ApiError, { scenarioId: string; mode: PracticeMode }>({
    mutationFn: ({ scenarioId, mode }) =>
      unwrap(api.POST("/api/v1/sessions", { body: { scenario_id: scenarioId, mode } })),
    onSuccess: (session) => {
      router.push(`/sessions/${session.id}`);
    },
    onError: (error) => {
      const code = error instanceof ApiError ? error.code : "internal_error";
      toast.error(errorMessage(code));
    },
  });
}
