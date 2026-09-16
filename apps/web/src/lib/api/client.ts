import createClient from "openapi-fetch";

import { API_ORIGIN } from "@/lib/env";

import { ApiError, errorMessage, toApiError } from "./errors";
import type { paths } from "./schema";

export const api = createClient<paths>({
  baseUrl: API_ORIGIN,
  credentials: "include",
  // Look fetch up at call time so test interceptors (MSW) patched after import still apply.
  fetch: (request) => globalThis.fetch(request),
});

type FetchResult<T> = { data?: T; error?: unknown; response: Response };

/** Returns the data of an openapi-fetch call, or throws an ApiError. */
export async function unwrap<T>(request: Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await request;
  } catch {
    throw new ApiError("network_error", errorMessage("network_error"), 0);
  }
  const { data, error, response } = result;
  if (error !== undefined || !response.ok) {
    throw toApiError(response.status, error);
  }
  return data as T;
}
