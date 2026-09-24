import { api, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type SettingsOut = components["schemas"]["SettingsOut"];

export function getSettings(): Promise<SettingsOut> {
  return unwrap(api.GET("/api/v1/settings"));
}
