"""Crisis detection (security-privacy.md S10, F2). See `app/domain/safety_phrases.py` for the
phrase list and its accepted false-positive trade-off.
"""

from app.domain.safety_phrases import CRISIS_PHRASES

SAFETY_MESSAGE = (
    "I'm stepping out of the practice for a moment. It sounds like you might be going through "
    "something hard. If you're in danger or thinking about harming yourself, please contact "
    "local emergency services or a crisis line in your country right away. You can end this "
    "practice session any time."
)


def detect_crisis(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in CRISIS_PHRASES)
