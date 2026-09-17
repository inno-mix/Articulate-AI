"""Crisis phrases (security-privacy.md S10).

Plain, case-insensitive substring matching. This can flag harmless sentences that happen to
contain a listed phrase (e.g. a longer message quoting one of these out of context); that
trade-off is accepted deliberately — safety first.
"""

CRISIS_PHRASES: tuple[str, ...] = (
    "kill myself",
    "kill herself",
    "kill himself",
    "kill themselves",
    "suicide",
    "suicidal",
    "end my life",
    "ending my life",
    "end it all",
    "hurt myself",
    "hurting myself",
    "self harm",
    "self-harm",
    "don't want to live",
    "do not want to live",
    "not want to live anymore",
    "want to die",
    "better off dead",
)
