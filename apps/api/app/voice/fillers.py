"""Filler-word detection for speaking stats (voice-and-pronunciation.md §3)."""

import string

FILLER_TOKENS: frozenset[str] = frozenset(
    {"uh", "um", "uhm", "erm", "er", "ah", "hmm", "mhm", "mm"}
)


def is_filler(token: str, *, provider_flag: bool | None = None) -> bool:
    """Whether `token` is a filler word. The provider's own flag wins when given."""
    if provider_flag is not None:
        return provider_flag
    return token.strip(string.punctuation).lower() in FILLER_TOKENS
