from enum import StrEnum


class Dimension(StrEnum):
    CLARITY = "clarity"
    CONCISENESS = "conciseness"
    STRUCTURE = "structure"
    AUDIENCE_FIT = "audience_fit"
    TONE = "tone"
    CONFIDENCE = "confidence"
    GRAMMAR_VOCABULARY = "grammar_vocabulary"
    FLUENCY = "fluency"
    PRONUNCIATION = "pronunciation"


LLM_DIMENSIONS: tuple[Dimension, ...] = (
    Dimension.CLARITY,
    Dimension.CONCISENESS,
    Dimension.STRUCTURE,
    Dimension.AUDIENCE_FIT,
    Dimension.TONE,
    Dimension.CONFIDENCE,
    Dimension.GRAMMAR_VOCABULARY,
)
