from enum import StrEnum


class Seniority(StrEnum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF_PLUS = "staff_plus"
    MANAGER = "manager"


class EnglishLevel(StrEnum):
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class PracticeMode(StrEnum):
    TEXT = "text"
    VOICE = "voice"


class VoiceInputMode(StrEnum):
    PUSH_TO_TALK = "push_to_talk"
    HANDS_FREE = "hands_free"


class Goal(StrEnum):
    INTERVIEWS = "interviews"
    MEETINGS = "meetings"
    STAKEHOLDERS = "stakeholders"
    CODE_REVIEW = "code_review"
    PRESENTATIONS = "presentations"
    WRITING = "writing"


class ScenarioCategory(StrEnum):
    STATUS_UPDATES = "status_updates"
    STAKEHOLDER_COMMUNICATION = "stakeholder_communication"
    INTERVIEWS = "interviews"
    CODE_REVIEW = "code_review"
    NEGOTIATION = "negotiation"
    MEETINGS = "meetings"
    CAREER = "career"


class RecommendedMode(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    EITHER = "either"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"
    ABANDONED = "abandoned"


class SessionPurpose(StrEnum):
    PRACTICE = "practice"
    ASSESSMENT = "assessment"


class MessageRole(StrEnum):
    ASSISTANT = "assistant"
    USER = "user"


class MessageSource(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    SYSTEM = "system"


class UsageKind(StrEnum):
    LLM = "llm"
    STT = "stt"
    TTS = "tts"
    PRONUNCIATION = "pronunciation"
