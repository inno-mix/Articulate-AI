import { useQuery } from "@tanstack/react-query";

import { getSession } from "../api";
import { sessionKeys } from "../query-keys";

export function useSession(sessionId: string) {
  return useQuery({
    queryKey: sessionKeys.detail(sessionId),
    queryFn: () => getSession(sessionId),
  });
}
