import type { SessionStatus } from "./api";

export const sessionKeys = {
  all: ["sessions"] as const,
  list: (filters: { status?: SessionStatus }) => [...sessionKeys.all, "list", filters] as const,
  detail: (id: string) => [...sessionKeys.all, "detail", id] as const,
};
