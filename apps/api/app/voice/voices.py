"""Curated Deepgram Aura-2 voices (voice-and-pronunciation.md §7, verified in ADR-0013)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Voice:
    id: str
    label: str


VOICES: tuple[Voice, ...] = (
    Voice(id="aura-2-thalia-en", label="Thalia (US, female)"),
    Voice(id="aura-2-asteria-en", label="Asteria (US, female)"),
    Voice(id="aura-2-andromeda-en", label="Andromeda (US, female)"),
    Voice(id="aura-2-apollo-en", label="Apollo (US, male)"),
    Voice(id="aura-2-arcas-en", label="Arcas (US, male)"),
    Voice(id="aura-2-helena-en", label="Helena (US, female)"),
)

_VOICE_IDS = frozenset(voice.id for voice in VOICES)


def is_known_voice(voice_id: str) -> bool:
    return voice_id in _VOICE_IDS
