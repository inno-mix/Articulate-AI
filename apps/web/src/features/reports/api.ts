import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type ReportOut = components["schemas"]["ReportOut"];
export type RetryOut = components["schemas"]["RetryOut"];
export type ReportStatus = components["schemas"]["ReportStatus"];

export function getReport(sessionId: string): Promise<ReportOut> {
  return unwrap(
    api.GET("/api/v1/sessions/{session_id}/report", {
      params: { path: { session_id: sessionId } },
    }),
  );
}

export function retryReport(sessionId: string): Promise<RetryOut> {
  return unwrap(
    api.POST("/api/v1/sessions/{session_id}/report/retry", {
      params: { path: { session_id: sessionId } },
    }),
  );
}
