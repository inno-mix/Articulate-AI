import { useInfiniteQuery } from "@tanstack/react-query";

import { listSessions, type SessionStatus } from "../api";
import { sessionKeys } from "../query-keys";

export function useSessionsHistory(status?: SessionStatus) {
  return useInfiniteQuery({
    queryKey: sessionKeys.list({ status }),
    queryFn: ({ pageParam }: { pageParam: string | undefined }) =>
      listSessions({ limit: 20, cursor: pageParam, status }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });
}
