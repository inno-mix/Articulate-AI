export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(
    code: string,
    message: string,
    status: number,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

const MESSAGES: Record<string, string> = {
  internal_error: "Something went wrong on our side. Please try again.",
  network_error: "Can't reach the Articulate AI API. Make sure it's running with make dev.",
  validation_error: "Some fields need attention. Check them and try again.",
  not_found: "We couldn't find that.",
  local_user_missing: "The local user hasn't been created yet. Run make seed, then reload.",
  llm_unavailable: "The AI model isn't reachable. Check that Ollama is running, then try again.",
  llm_invalid_output:
    "The AI returned an unreadable report. Try again — it usually works on the second attempt.",
  report_not_ready: "This report can't be retried right now.",
  origin_not_allowed: "This request came from another site, so it was blocked.",
  invalid_host: "Open the app from localhost to use it.",
  mic_permission_denied:
    "Microphone access was denied. Open your browser's site settings for localhost:3000, allow the microphone, then reload.",
  connection_lost: "The voice connection was lost unexpectedly.",
  speech_unavailable: "Speech recognition isn't reachable right now. Try again in a moment.",
};

const FALLBACK_MESSAGE = "Something went wrong. Please try again.";

export function errorMessage(code: string): string {
  return MESSAGES[code] ?? FALLBACK_MESSAGE;
}

type ErrorEnvelope = {
  error: { code: string; message: string; details?: Record<string, unknown> };
};

function isEnvelope(body: unknown): body is ErrorEnvelope {
  if (typeof body !== "object" || body === null || !("error" in body)) return false;
  const error = (body as { error: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { code?: unknown }).code === "string" &&
    typeof (error as { message?: unknown }).message === "string"
  );
}

export function toApiError(status: number, body: unknown): ApiError {
  if (isEnvelope(body)) {
    const { code, message, details } = body.error;
    return new ApiError(code, message, status, details ?? {});
  }
  return new ApiError("internal_error", errorMessage("internal_error"), status);
}
