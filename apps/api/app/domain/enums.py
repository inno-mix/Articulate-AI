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
