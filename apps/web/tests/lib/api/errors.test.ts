import { describe, expect, it } from "vitest";

import { ApiError, errorMessage, toApiError } from "@/lib/api/errors";

describe("toApiError", () => {
  it("reads the error envelope", () => {
    const error = toApiError(409, {
      error: { code: "session_not_active", message: "Ended.", details: { id: "1" } },
    });

    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("session_not_active");
    expect(error.message).toBe("Ended.");
    expect(error.status).toBe(409);
    expect(error.details).toEqual({ id: "1" });
  });

  it.each([["<html>Bad gateway</html>"], [null], [{ detail: "x" }]])(
    "falls back to internal_error for %j",
    (body) => {
      const error = toApiError(502, body);

      expect(error.code).toBe("internal_error");
      expect(error.status).toBe(502);
      expect(error.message).toBe(errorMessage("internal_error"));
    },
  );
});

describe("errorMessage", () => {
  it("returns friendly text for known codes", () => {
    expect(errorMessage("llm_unavailable")).toMatch(/Ollama/);
  });

  it("returns a generic message for unknown codes", () => {
    expect(errorMessage("something_new")).toBe("Something went wrong. Please try again.");
  });
});
