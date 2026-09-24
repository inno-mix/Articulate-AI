import { WS_ORIGIN } from "@/lib/env";

export function voiceSocketUrl(sessionId: string): string {
  return `${WS_ORIGIN}/api/v1/sessions/${sessionId}/voice`;
}
