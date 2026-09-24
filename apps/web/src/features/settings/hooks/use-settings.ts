import { useQuery } from "@tanstack/react-query";

import { getSettings } from "../api";

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: getSettings,
  });
}
