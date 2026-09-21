export const reportKeys = {
  all: ["reports"] as const,
  detail: (sessionId: string) => [...reportKeys.all, "detail", sessionId] as const,
};
