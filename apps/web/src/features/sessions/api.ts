import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type SessionSummary = components["schemas"]["SessionSummary"];
export type SessionDetail = components["schemas"]["SessionDetail"];
export type SessionStatus = components["schemas"]["SessionStatus"];
export type SessionsPage = components["schemas"]["Page_SessionSummary_"];

export function getSession(sessionId: string): Promise<SessionDetail> {
  return unwrap(
    api.GET("/api/v1/sessions/{session_id}", { params: { path: { session_id: sessionId } } }),
  );
}

export function listSessions(params: {
  limit?: number;
  cursor?: string;
  status?: SessionStatus;
}): Promise<SessionsPage> {
  return unwrap(api.GET("/api/v1/sessions", { params: { query: params } }));
}

export function endSession(sessionId: string) {
  return unwrap(
    api.POST("/api/v1/sessions/{session_id}/end", { params: { path: { session_id: sessionId } } }),
  );
}

export function deleteSession(sessionId: string): Promise<void> {
  return unwrap(
    api.DELETE("/api/v1/sessions/{session_id}", { params: { path: { session_id: sessionId } } }),
  );
}

export function getHint(sessionId: string): Promise<{ hint: string }> {
  return unwrap(
    api.POST("/api/v1/sessions/{session_id}/hint", { params: { path: { session_id: sessionId } } }),
  );
}
