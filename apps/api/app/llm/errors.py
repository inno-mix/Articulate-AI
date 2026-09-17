"""LLM adapter errors, mapped to AppError codes by the services that call LLMService."""


class LLMError(Exception):
    """Base class for every LLM adapter error."""


class LLMUnavailableError(LLMError):
    """The provider is unreachable, timed out, or returned a 5xx (→ `llm_unavailable`)."""


class LLMInvalidOutputError(LLMError):
    """Structured output failed validation after retries (→ `llm_invalid_output`)."""


class LLMRateLimitedError(LLMError):
    """The provider (or our own per-user limit) rate-limited the request (→ `llm_rate_limited`)."""


class LLMAuthError(LLMError):
    """The provider rejected our credentials (→ `llm_auth_failed`, Phase 9)."""


class LLMNotConfiguredError(LLMError):
    """The user has no active LLM key configured (→ `llm_not_configured`, Phase 9)."""
